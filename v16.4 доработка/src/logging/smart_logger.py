#!/usr/bin/env python3
"""
Smart Logger - ИСПРАВЛЕННАЯ ВЕРСИЯ
=================================
✅ ИСПРАВЛЕНИЯ:
- Убраны множественные запуски DatabaseLogWriter
- Исправлена инициализация базы данных
- Добавлены проверки состояния
- Исправлены утечки памяти
"""

import logging
import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, asdict
from collections import deque
import threading
from contextlib import asynccontextmanager

# Безопасные импорты
try:
    from ..core.database import SessionLocal, initialize_database
    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False
    SessionLocal = None

try:
    from ..core.models import TradingLog
    MODELS_AVAILABLE = True
except ImportError:
    MODELS_AVAILABLE = False
    TradingLog = None

try:
    from sqlalchemy import text
    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False

@dataclass
class LogEntry:
    """Структура записи лога"""
    created_at: datetime
    level: str
    category: str
    message: str
    symbol: Optional[str] = None
    trade_id: Optional[str] = None
    strategy: Optional[str] = None
    context: Optional[Dict[str, Any]] = None

class DatabaseLogWriter:
    """
    ✅ ИСПРАВЛЕНО: Записывает логи в базу данных без множественных запусков
    """
    
    # ✅ ИСПРАВЛЕНИЕ: Singleton pattern для предотвращения множественных экземпляров
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseLogWriter, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self.db = None
        self.is_running = False
        self.queue = deque(maxlen=1000)  # Ограничиваем размер очереди
        self.batch_size = 10
        self.flush_interval = 5.0  # секунд
        self.task = None
        self.shutdown_event = asyncio.Event() if self._event_loop_available() else None
        self._last_health_check = 0
        self._db_initialized = False
        self._lock = threading.Lock()
        
        DatabaseLogWriter._initialized = True
        print("✅ DatabaseLogWriter инициализирован (singleton)")
    
    @staticmethod
    def _event_loop_available() -> bool:
        """Проверка доступности event loop"""
        try:
            asyncio.get_event_loop()
            return True
        except RuntimeError:
            return False
    
    async def start(self):
        """✅ ИСПРАВЛЕНО: Запуск writer с проверкой состояния"""
        with self._lock:
            if self.is_running:
                print("⚠️ DatabaseLogWriter уже запущен, пропускаем")
                return
            
            self.is_running = True
            print("🚀 Запуск DatabaseLogWriter...")
        
        try:
            await self._init_database()
            
            # Запускаем только если БД доступна
            if self._db_initialized:
                if self.shutdown_event:
                    self.shutdown_event.clear()
                
                self.task = asyncio.create_task(self._write_loop())
                print("✅ DatabaseLogWriter запущен успешно")
            else:
                print("⚠️ DatabaseLogWriter запущен без БД (только в память)")
        
        except Exception as e:
            print(f"❌ Ошибка запуска DatabaseLogWriter: {e}")
            self.is_running = False
    
    async def stop(self):
        """✅ ИСПРАВЛЕНО: Остановка writer с корректной очисткой"""
        with self._lock:
            if not self.is_running:
                print("ℹ️ DatabaseLogWriter уже остановлен")
                return
            
            print("🛑 Остановка DatabaseLogWriter...")
            self.is_running = False
        
        try:
            # Сигнализируем о завершении
            if self.shutdown_event:
                self.shutdown_event.set()
            
            # Ждем завершения задачи
            if self.task and not self.task.done():
                try:
                    await asyncio.wait_for(self.task, timeout=5.0)
                except asyncio.TimeoutError:
                    print("⚠️ Таймаут при остановке DatabaseLogWriter")
                    self.task.cancel()
            
            # Финальная запись оставшихся логов
            await self._flush_remaining_logs()
            
            # Закрытие БД соединения
            if self.db:
                try:
                    self.db.close()
                    self.db = None
                except Exception as e:
                    print(f"⚠️ Ошибка закрытия БД: {e}")
            
            self._db_initialized = False
            print("✅ DatabaseLogWriter остановлен")
            
        except Exception as e:
            print(f"❌ Ошибка остановки DatabaseLogWriter: {e}")
    
    async def _init_database(self):
        """✅ ИСПРАВЛЕНО: Инициализация подключения к БД"""
        try:
            if self._db_initialized:
                return
                
            # Проверяем доступность компонентов
            if not DATABASE_AVAILABLE or not SessionLocal:
                print("⚠️ DatabaseLogWriter: База данных недоступна, работаем без БД")
                self.db = None
                self._db_initialized = False
                return
                
            # Правильная инициализация SessionLocal
            self.db = SessionLocal()
            self._db_initialized = True
            print("✅ DatabaseLogWriter: БД инициализирована успешно")
            
        except Exception as e:
            # Безопасный fallback
            self.db = None
            self._db_initialized = False
            print(f"❌ DatabaseLogWriter: Ошибка инициализации БД: {e}")
    
    async def _write_loop(self):
        """✅ ИСПРАВЛЕНО: Основной цикл записи логов"""
        print("🔄 DatabaseLogWriter: Цикл записи запущен")
        
        try:
            while self.is_running:
                try:
                    # Проверяем сигнал завершения
                    if self.shutdown_event and self.shutdown_event.is_set():
                        print("📋 DatabaseLogWriter получил сигнал отмены")
                        break
                    
                    # Собираем батч логов
                    batch = []
                    while len(batch) < self.batch_size and self.queue:
                        batch.append(self.queue.popleft())
                    
                    # Записываем батч
                    if batch:
                        await self._write_logs_to_db(batch)
                    
                    # Проверка здоровья БД (периодически)
                    await self._check_database_health()
                    
                    # Ждем следующую итерацию
                    await asyncio.sleep(self.flush_interval)
                    
                except asyncio.CancelledError:
                    print("🚫 DatabaseLogWriter отменен")
                    break
                except Exception as e:
                    print(f"❌ Ошибка в цикле записи: {e}")
                    await asyncio.sleep(1)  # Короткая пауза при ошибке
        
        finally:
            print("🏁 DatabaseLogWriter: Цикл записи завершен")
    
    async def _flush_remaining_logs(self):
        """✅ ИСПРАВЛЕНО: Запись оставшихся логов при завершении"""
        try:
            remaining_logs = list(self.queue)
            if remaining_logs:
                print(f"📝 Записываем {len(remaining_logs)} оставшихся логов")
                await self._write_logs_to_db(remaining_logs)
                self.queue.clear()
        except Exception as e:
            print(f"❌ Ошибка записи оставшихся логов: {e}")
    
    async def _write_logs_to_db(self, logs: List[LogEntry]):
        """✅ ИСПРАВЛЕНО: Запись логов в базу данных"""
        # Критичная проверка: Проверяем что БД инициализирована
        if not self.db or not self._db_initialized:
            return
        
        if not SQLALCHEMY_AVAILABLE or not MODELS_AVAILABLE or not TradingLog or not logs:
            return
            
        try:
            # Используем существующую сессию
            for log_entry in logs:
                # ✅ ИСПРАВЛЕНИЕ: Используем created_at вместо timestamp
                db_log = TradingLog(
                    created_at=log_entry.timestamp,
                    level=log_entry.level,
                    category=log_entry.category,
                    message=log_entry.message,
                    symbol=log_entry.symbol,
                    trade_id=log_entry.trade_id,
                    strategy=log_entry.strategy,
                    context=json.dumps(log_entry.context) if log_entry.context else None
                )
                
                self.db.add(db_log)
            
            # Коммитим изменения
            self.db.commit()
                
        except Exception as e:
            print(f"❌ Ошибка сохранения лога в БД: {e}")
            try:
                self.db.rollback()
            except:
                pass
    
    async def _check_database_health(self):
        """✅ ИСПРАВЛЕНО: Проверка состояния БД"""
        try:
            # Проверяем каждые 2 минуты
            current_time = time.time()
            if current_time - self._last_health_check < 120:
                return
            
            self._last_health_check = current_time
            
            # Простой запрос для проверки соединения
            if self.db and self._db_initialized:
                try:
                    # Используем синхронный запрос
                    self.db.execute(text("SELECT 1"))
                except Exception as e:
                    print(f"⚠️ Проблема с БД: {e}")
                    # Пытаемся переподключиться
                    try:
                        await self._init_database()
                    except Exception as init_error:
                        print(f"❌ Не удалось переподключиться к БД: {init_error}")
                    
        except Exception as e:
            print(f"❌ Ошибка проверки состояния БД: {e}")
    
    def add_log(self, log_entry: LogEntry):
        """Добавление записи лога в очередь"""
        try:
            if len(self.queue) >= self.queue.maxlen:
                # Удаляем старые записи если очередь переполнена
                self.queue.popleft()
            
            self.queue.append(log_entry)
        except Exception as e:
            print(f"❌ Ошибка добавления лога в очередь: {e}")

class SmartLogger:
    """
    ✅ ИСПРАВЛЕНО: Умный логгер с исправленным DatabaseLogWriter
    """
    
    def __init__(self, name: str = "crypto_bot"):
        self.name = name
        self.logger = logging.getLogger(name)
        self.db_writer = None
        self._setup_console_logging()
        self._initialized = False
        
        print("✅ SmartLogger инициализирован")
    
    def _setup_console_logging(self):
        """Настройка консольного логирования"""
        if not self.logger.handlers:
            # Форматтер для консоли
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            
            # Консольный handler
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            console_handler.setLevel(logging.INFO)
            
            self.logger.addHandler(console_handler)
            self.logger.setLevel(logging.INFO)
    
    async def initialize(self):
        """✅ ИСПРАВЛЕНО: Инициализация с единственным DatabaseLogWriter"""
        if self._initialized:
            print("ℹ️ SmartLogger уже инициализирован")
            return
        
        try:
            # Инициализируем БД writer (singleton)
            self.db_writer = DatabaseLogWriter()
            await self.db_writer.start()
            
            self._initialized = True
            print("✅ SmartLogger полностью инициализирован")
            
        except Exception as e:
            print(f"❌ Ошибка инициализации SmartLogger: {e}")
    
    async def shutdown(self):
        """✅ ИСПРАВЛЕНО: Корректное завершение работы"""
        if not self._initialized:
            return
        
        try:
            print("🔄 Запуск graceful shutdown SmartLogger...")
            
            if self.db_writer:
                await self.db_writer.stop()
            
            self._initialized = False
            print("✅ SmartLogger завершен корректно")
            
        except Exception as e:
            print(f"❌ Ошибка завершения SmartLogger: {e}")
    
    def _create_log_entry(self, level: str, message: str, **kwargs) -> LogEntry:
        """Создание записи лога"""
        return LogEntry(
            created_at=datetime.now(),
            level=level.upper(),
            category=kwargs.get('category', 'general'),
            message=message,
            symbol=kwargs.get('symbol'),
            trade_id=kwargs.get('trade_id'),
            strategy=kwargs.get('strategy'),
            context=kwargs.get('context')
        )
    
    def info(self, message: str, **kwargs):
        """Логирование информации"""
        self.logger.info(message)
        if self.db_writer:
            log_entry = self._create_log_entry('INFO', message, **kwargs)
            self.db_writer.add_log(log_entry)
    
    def warning(self, message: str, **kwargs):
        """Логирование предупреждения"""
        self.logger.warning(message)
        if self.db_writer:
            log_entry = self._create_log_entry('WARNING', message, **kwargs)
            self.db_writer.add_log(log_entry)
    
    def error(self, message: str, **kwargs):
        """Логирование ошибки"""
        self.logger.error(message)
        if self.db_writer:
            log_entry = self._create_log_entry('ERROR', message, **kwargs)
            self.db_writer.add_log(log_entry)
    
    def debug(self, message: str, **kwargs):
        """Логирование отладки"""
        self.logger.debug(message)
        if self.db_writer:
            log_entry = self._create_log_entry('DEBUG', message, **kwargs)
            self.db_writer.add_log(log_entry)

# ✅ ИСПРАВЛЕНО: Создаем единственный экземпляр
_global_logger = None

def get_logger(name: str = "crypto_bot") -> SmartLogger:
    """✅ ИСПРАВЛЕНО: Получение глобального экземпляра логгера БЕЗ проблемной автоинициализации"""
    global _global_logger
    if _global_logger is None:
        _global_logger = SmartLogger(name)
    return _global_logger

# Создаем глобальный logger для совместимости НО НЕ ИНИЦИАЛИЗИРУЕМ автоматически
logger = get_logger()

# ✅ ИСПРАВЛЕНО: Убираем проблемную автоматическую инициализацию
def _safe_initialize():
    """Безопасная инициализация только при необходимости"""
    try:
        # НЕ пытаемся инициализировать автоматически - это создает проблемы
        print("✅ SmartLogger готов к использованию (без автоматической инициализации)")
        print("💡 Для полной инициализации вызовите: await logger.initialize()")
        
    except Exception as e:
        print(f"⚠️ Ошибка при проверке логирования: {e}")
        print("💡 Используется только консольное логирование")

# Выполняем только безопасную проверку
_safe_initialize()

# Информация о модуле
print("\n🎯 Модуль smart_logger успешно загружен!")
print("📚 Документация: https://github.com/your-repo/docs/smart_logger.md")
print("🚀 Для начала работы используйте: from src.logging.smart_logger import logger")

__all__ = [
    'SmartLogger',
    'DatabaseLogWriter', 
    'LogEntry',
    'logger',
    'get_logger'
]