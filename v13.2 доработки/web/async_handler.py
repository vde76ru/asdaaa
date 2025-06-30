"""
AsyncRouteHandler - Менеджер для корректной интеграции asyncio с Flask

Модуль: Управление асинхронными вызовами в синхронном Flask приложении
Статус: ВОССТАНОВЛЕННАЯ версия с улучшениями совместимости
Критичность: ВЫСОКАЯ - устраняет основную причину нестабильности системы

Архитектурное решение:
1. Единый постоянный event loop в отдельном потоке
2. ThreadPoolExecutor для безопасного выполнения корутин
3. Автоматическое восстановление при сбоях loop
4. Централизованная обработка таймаутов и ошибок
5. ✅ ВОССТАНОВЛЕНО: Полная функциональность + версионная совместимость
"""

import asyncio
import threading
import logging
import time
import sys
from functools import wraps
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from typing import Callable, Any, Optional
from datetime import datetime
from flask import jsonify

logger = logging.getLogger(__name__)

class AsyncRouteHandler:
    """
    Менеджер для безопасного выполнения async кода в Flask маршрутах
    
    Решает проблемы:
    - Event loop is closed
    - Конфликты между sync/async кодом  
    - Некорректное управление lifecycle event loop
    
    ВОССТАНОВЛЕННАЯ ФУНКЦИОНАЛЬНОСТЬ:
    - async_route декоратор (был потерян!)
    - Автоматическая инициализация
    - Версионная совместимость Python 3.7+
    """
    
    def __init__(self, max_workers: int = 4, default_timeout: int = 30):
        """
        Инициализация AsyncRouteHandler
        
        Args:
            max_workers: Количество рабочих потоков
            default_timeout: Таймаут по умолчанию для async операций
        """
        self.max_workers = max_workers
        self.default_timeout = default_timeout
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.loop_thread: Optional[threading.Thread] = None
        
        # ✅ ВОССТАНОВЛЕНО: Версионная совместимость
        self.python_version = sys.version_info
        self.supports_timeout = self.python_version >= (3, 9)
        
        # ✅ УЛУЧШЕНО: Версионно-совместимый ThreadPoolExecutor
        self.executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="AsyncRoute"
        )
        
        self._shutdown_event = threading.Event()
        self._loop_ready = threading.Event()
        
        # ✅ ВОССТАНОВЛЕНО: Полная статистика для мониторинга
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'timeout_requests': 0,
            'last_restart': None,
            'initialization_time': datetime.utcnow(),
            'average_execution_time': 0
        }
        
        # ✅ ВОССТАНОВЛЕНО: Автоматическая инициализация
        self._init_async_loop()
        
        logger.info(f"✅ AsyncRouteHandler инициализирован")
        logger.info(f"   Python версия: {self.python_version.major}.{self.python_version.minor}")
        logger.info(f"   ThreadPoolExecutor timeout support: {self.supports_timeout}")
        logger.info(f"   Workers: {max_workers}, timeout: {default_timeout}s")
    
    def _init_async_loop(self):
        """
        ✅ ВОССТАНОВЛЕНО: Инициализация постоянного event loop в отдельном потоке
        """
        def run_event_loop():
            """Функция для запуска event loop в отдельном потоке"""
            try:
                # Создаем новый event loop для потока
                self.loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.loop)
                
                logger.info("🔄 Event loop запущен в отдельном потоке")
                self._loop_ready.set()  # Сигнализируем о готовности
                
                # Запускаем loop до получения сигнала остановки
                self.loop.run_forever()
                
            except Exception as e:
                logger.error(f"❌ Критическая ошибка в event loop: {e}")
                self._loop_ready.set()  # Освобождаем ожидание даже при ошибке
            finally:
                if self.loop and not self.loop.is_closed():
                    self.loop.close()
                logger.info("🛑 Event loop остановлен")
        
        # Запускаем поток с event loop
        self.loop_thread = threading.Thread(
            target=run_event_loop, 
            name="AsyncEventLoop",
            daemon=True
        )
        self.loop_thread.start()
        
        # Ждем готовности loop (максимум 5 секунд)
        if not self._loop_ready.wait(timeout=5.0):
            raise RuntimeError("❌ Не удалось инициализировать event loop")
        
        # Проверяем что loop корректно создан
        if self.loop is None or self.loop.is_closed():
            raise RuntimeError("❌ Event loop не был корректно создан")
    
    def initialize(self):
        """
        ✅ ДОБАВЛЕНО: Дополнительный метод инициализации для совместимости
        (В основном уже выполнено в __init__, но может быть полезно для переинициализации)
        """
        if self.loop_thread is not None and self.loop_thread.is_alive():
            logger.warning("⚠️ AsyncRouteHandler уже инициализирован")
            return
        
        logger.info("🔄 Переинициализация AsyncRouteHandler...")
        self._loop_ready.clear()
        self._shutdown_event.clear()
        self._init_async_loop()
        logger.info("✅ AsyncRouteHandler переинициализирован")
    
    def _get_python_version(self) -> tuple:
        """✅ ВОССТАНОВЛЕНО: Получение версии Python для compatibility checks"""
        return sys.version_info[:2]
    
    def _supports_executor_timeout(self) -> bool:
        """✅ ВОССТАНОВЛЕНО: Проверка поддержки timeout parameter в ThreadPoolExecutor.shutdown()"""
        # timeout parameter добавлен в Python 3.9
        return self.supports_timeout
    
    def _safe_executor_shutdown(self, timeout: Optional[float] = None):
        """
        ✅ ДОБАВЛЕНО: Безопасная остановка ThreadPoolExecutor с учетом версии Python
        
        Args:
            timeout: Таймаут ожидания (игнорируется в Python < 3.9)
        """
        try:
            if self._supports_executor_timeout() and timeout is not None:
                logger.debug(f"Используем executor shutdown с timeout={timeout}")
                self.executor.shutdown(wait=True, timeout=timeout)
            else:
                logger.debug("Используем executor shutdown без timeout (Python < 3.9)")
                self.executor.shutdown(wait=True)
                
            logger.info("✅ ThreadPoolExecutor корректно остановлен")
            
        except TypeError as e:
            # Fallback для неожиданных проблем совместимости
            if "timeout" in str(e):
                logger.warning(f"⚠️ Проблема с timeout параметром: {e}")
                try:
                    self.executor.shutdown(wait=True)
                    logger.info("✅ ThreadPoolExecutor остановлен (fallback режим)")
                except Exception as fallback_error:
                    logger.error(f"❌ Критическая ошибка остановки executor: {fallback_error}")
            else:
                raise
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка при остановке executor: {e}")
    
    def _ensure_loop_healthy(self) -> bool:
        """
        ✅ ВОССТАНОВЛЕНО: Проверка здоровья event loop и автоматическое восстановление
        
        Returns:
            bool: True если loop здоров или восстановлен, False если критическая ошибка
        """
        if self.loop is None or self.loop.is_closed() or not self.loop.is_running():
            logger.warning("⚠️ Event loop нездоров, попытка восстановления...")
            
            try:
                # Останавливаем старый loop если он существует
                if self.loop and not self.loop.is_closed():
                    self.loop.call_soon_threadsafe(self.loop.stop)
                    time.sleep(0.5)
                
                # Ждем завершения старого потока
                if self.loop_thread and self.loop_thread.is_alive():
                    self.loop_thread.join(timeout=2.0)
                
                # Сбрасываем события
                self._loop_ready.clear()
                self._shutdown_event.clear()
                
                # Создаем новый loop
                self._init_async_loop()
                self.stats['last_restart'] = datetime.utcnow()
                
                logger.info("✅ Event loop успешно восстановлен")
                return True
                
            except Exception as e:
                logger.error(f"❌ Не удалось восстановить event loop: {e}")
                return False
        
        return True
    
    def async_route(self, timeout: Optional[int] = None) -> Callable:
        """
        ✅ ВОССТАНОВЛЕНО: Декоратор для Flask маршрутов с async функциями
        
        Args:
            timeout: Таймаут для операции (если None, используется default_timeout)
            
        Returns:
            Декорированная функция
            
        Example:
            @app.route('/api/bot/start', methods=['POST'])
            @async_handler.async_route(timeout=30)
            async def start_bot():
                result = await bot_controller.start_bot()
                return jsonify(result)
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                operation_start = time.time()
                operation_timeout = timeout or self.default_timeout
                
                # Обновляем статистику
                self.stats['total_requests'] += 1
                
                try:
                    # Проверяем здоровье event loop
                    if not self._ensure_loop_healthy():
                        self.stats['failed_requests'] += 1
                        return jsonify({
                            'success': False, 
                            'error': 'Event loop unavailable'
                        }), 500
                    
                    # Выполняем async функцию через event loop
                    future = asyncio.run_coroutine_threadsafe(
                        func(*args, **kwargs), 
                        self.loop
                    )
                    
                    # Ждем результат с таймаутом
                    result = future.result(timeout=operation_timeout)
                    
                    # ✅ УЛУЧШЕНО: Обновляем статистику успеха
                    execution_time = time.time() - operation_start
                    self.stats['successful_requests'] += 1
                    
                    # Обновляем среднее время выполнения
                    total_successful = self.stats['successful_requests']
                    current_avg = self.stats['average_execution_time']
                    self.stats['average_execution_time'] = (
                        (current_avg * (total_successful - 1) + execution_time) / total_successful
                    )
                    
                    logger.debug(f"✅ Async route {func.__name__} выполнен за {execution_time:.2f}с")
                    return result
                    
                except FutureTimeoutError:
                    self.stats['timeout_requests'] += 1
                    self.stats['failed_requests'] += 1
                    logger.error(f"⏰ Таймаут async операции: {func.__name__} (>{operation_timeout}s)")
                    return jsonify({
                        'success': False, 
                        'error': f'Operation timeout ({operation_timeout}s)'
                    }), 408
                    
                except asyncio.CancelledError:
                    self.stats['failed_requests'] += 1
                    logger.warning(f"🚫 Async операция отменена: {func.__name__}")
                    return jsonify({
                        'success': False, 
                        'error': 'Operation cancelled'
                    }), 499
                    
                except Exception as e:
                    self.stats['failed_requests'] += 1
                    logger.error(f"❌ Ошибка в async маршруте {func.__name__}: {e}")
                    return jsonify({
                        'success': False, 
                        'error': str(e)
                    }), 500
            
            return wrapper
        return decorator
    
    async def execute_async(self, func: Callable, *args, timeout: Optional[float] = None, **kwargs) -> Any:
        """
        ✅ ДОБАВЛЕНО: Выполнение асинхронной функции с обработкой ошибок
        
        Args:
            func: Асинхронная функция для выполнения
            *args: Позиционные аргументы
            timeout: Таймаут выполнения
            **kwargs: Именованные аргументы
            
        Returns:
            Результат выполнения функции
        """
        if not self._ensure_loop_healthy():
            raise RuntimeError("Event loop недоступен")
        
        timeout = timeout or self.default_timeout
        
        try:
            # Выполняем функцию в event loop
            future = asyncio.run_coroutine_threadsafe(
                func(*args, **kwargs), 
                self.loop
            )
            
            # Ждем результат с таймаутом
            result = future.result(timeout=timeout)
            return result
            
        except asyncio.TimeoutError:
            logger.error(f"⏰ Таймаут выполнения асинхронной функции {func.__name__}")
            raise
        except Exception as e:
            logger.error(f"❌ Ошибка выполнения асинхронной функции {func.__name__}: {e}")
            raise
    
    def execute_sync(self, func: Callable, *args, timeout: Optional[float] = None, **kwargs) -> Any:
        """
        ✅ ДОБАВЛЕНО: Выполнение синхронной функции в ThreadPoolExecutor
        
        Args:
            func: Синхронная функция для выполнения
            *args: Позиционные аргументы
            timeout: Таймаут выполнения
            **kwargs: Именованные аргументы
            
        Returns:
            Результат выполнения функции
        """
        timeout = timeout or self.default_timeout
        
        try:
            # Отправляем задачу в ThreadPoolExecutor
            future = self.executor.submit(func, *args, **kwargs)
            
            # Ждем результат с таймаутом
            result = future.result(timeout=timeout)
            return result
            
        except TimeoutError:
            logger.error(f"⏰ Таймаут выполнения синхронной функции {func.__name__}")
            raise
        except Exception as e:
            logger.error(f"❌ Ошибка выполнения синхронной функции {func.__name__}: {e}")
            raise
    
    def get_stats(self) -> dict:
        """✅ ВОССТАНОВЛЕНО: Получить статистику работы handler'а"""
        if self.stats['total_requests'] > 0:
            success_rate = (self.stats['successful_requests'] / self.stats['total_requests']) * 100
        else:
            success_rate = 0.0
            
        return {
            **self.stats,
            'success_rate': round(success_rate, 2),
            'loop_status': {
                'running': self.loop is not None and self.loop.is_running(),
                'closed': self.loop is None or self.loop.is_closed(),
                'thread_alive': self.loop_thread is not None and self.loop_thread.is_alive()
            },
            'python_version': f"{self.python_version.major}.{self.python_version.minor}",
            'supports_timeout': self.supports_timeout
        }
    
    def get_status(self) -> dict:
        """
        ✅ ДОПОЛНЕНО: Получение детального статуса обработчика
        
        Returns:
            Словарь с информацией о состоянии
        """
        return {
            'initialized': self.loop is not None,
            'loop_running': self.loop is not None and self.loop.is_running(),
            'loop_closed': self.loop is None or self.loop.is_closed(),
            'thread_alive': self.loop_thread is not None and self.loop_thread.is_alive(),
            'shutdown_signaled': self._shutdown_event.is_set(),
            'python_version': f"{self.python_version.major}.{self.python_version.minor}",
            'supports_timeout': self.supports_timeout,
            'max_workers': self.max_workers,
            'default_timeout': self.default_timeout,
            'stats': self.get_stats()
        }
    
    def shutdown(self):
        """✅ УЛУЧШЕНО: Версионно-совместимое завершение работы handler'а"""
        logger.info("🛑 Остановка AsyncRouteHandler...")
        
        try:
            # Сигнализируем о завершении
            self._shutdown_event.set()
            
            # Останавливаем event loop
            if self.loop and not self.loop.is_closed():
                self.loop.call_soon_threadsafe(self.loop.stop)
            
            # Ждем завершения потока
            if self.loop_thread and self.loop_thread.is_alive():
                self.loop_thread.join(timeout=5.0)
                
            # ✅ УЛУЧШЕНО: Версионно-совместимый executor shutdown
            self._safe_executor_shutdown(timeout=5.0)
                
            logger.info("✅ AsyncRouteHandler корректно остановлен")
            
        except Exception as e:
            logger.error(f"❌ Ошибка при остановке AsyncRouteHandler: {e}")

# Глобальный экземпляр для использования в приложении
async_handler = AsyncRouteHandler()

# Функция для получения handler'а (если нужно кастомизировать)
def get_async_handler(max_workers: int = 4, timeout: int = 30) -> AsyncRouteHandler:
    """
    Фабрика для создания кастомного AsyncRouteHandler
    
    Args:
        max_workers: Количество рабочих потоков
        timeout: Таймаут по умолчанию
        
    Returns:
        Настроенный AsyncRouteHandler
    """
    return AsyncRouteHandler(max_workers=max_workers, default_timeout=timeout)

# Экспорт основных компонентов
__all__ = ['AsyncRouteHandler', 'async_handler', 'get_async_handler']