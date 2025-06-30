"""
Модуль совместимости для ThreadPoolExecutor и системных компонентов
Обеспечивает совместимость с различными версиями Python
Путь: src/utils/threading_compat.py
"""
import asyncio
import sys
import threading
import logging
import subprocess
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Any, Callable
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

class CompatibleThreadPoolExecutor:
    """
    Обертка над ThreadPoolExecutor с поддержкой разных версий Python
    Решает проблему с timeout параметром в shutdown()
    """
    
    def __init__(self, max_workers: int = 4, thread_name_prefix: str = 'ThreadPool'):
        """
        Инициализация пула потоков
        
        Args:
            max_workers: Максимальное количество потоков
            thread_name_prefix: Префикс для имен потоков
        """
        self.max_workers = max_workers
        self.thread_name_prefix = thread_name_prefix
        self._executor: Optional[ThreadPoolExecutor] = None
        self._shutdown = False
        
        # Определяем версию Python для совместимости
        self.python_version = sys.version_info
        self.supports_timeout = self.python_version >= (3, 9)
        
        logger.info(f"✅ CompatibleThreadPoolExecutor инициализирован "
                   f"(Python {self.python_version.major}.{self.python_version.minor}, "
                   f"timeout support: {self.supports_timeout})")
    
    def start(self):
        """Запуск пула потоков"""
        if self._executor is None:
            self._executor = ThreadPoolExecutor(
                max_workers=self.max_workers,
                thread_name_prefix=self.thread_name_prefix
            )
            self._shutdown = False
            logger.info(f"🚀 ThreadPool запущен с {self.max_workers} потоками")
    
    def shutdown(self, wait: bool = True, timeout: Optional[float] = None):
        """
        Безопасная остановка пула потоков с учетом версии Python
        
        Args:
            wait: Ждать завершения выполняющихся задач
            timeout: Таймаут ожидания (поддерживается с Python 3.9+)
        """
        if self._executor is None or self._shutdown:
            return
            
        try:
            if self.supports_timeout and timeout is not None:
                # Python 3.9+ поддерживает timeout
                self._executor.shutdown(wait=wait, timeout=timeout)
                logger.info(f"🛑 ThreadPool остановлен с timeout={timeout}s")
            else:
                # Для старых версий Python
                self._executor.shutdown(wait=wait)
                logger.info("🛑 ThreadPool остановлен (без timeout)")
                
        except TypeError as e:
            # Fallback для несовместимых версий
            logger.warning(f"⚠️ Проблема с shutdown параметрами: {e}")
            try:
                self._executor.shutdown(wait=wait)
                logger.info("🛑 ThreadPool остановлен (fallback режим)")
            except Exception as fallback_error:
                logger.error(f"❌ Критическая ошибка остановки ThreadPool: {fallback_error}")
        
        finally:
            self._shutdown = True
            self._executor = None
    
    def submit(self, fn: Callable, *args, **kwargs):
        """
        Отправка задачи в пул потоков
        
        Args:
            fn: Функция для выполнения
            *args: Позиционные аргументы
            **kwargs: Именованные аргументы
            
        Returns:
            Future объект
        """
        if self._executor is None:
            raise RuntimeError("ThreadPool не запущен. Вызовите start() сначала.")
            
        return self._executor.submit(fn, *args, **kwargs)
    
    def map(self, fn: Callable, *iterables, timeout: Optional[float] = None, chunksize: int = 1):
        """
        Применение функции к итерируемым объектам
        
        Args:
            fn: Функция для применения
            *iterables: Итерируемые объекты
            timeout: Таймаут
            chunksize: Размер чанка
            
        Returns:
            Итератор результатов
        """
        if self._executor is None:
            raise RuntimeError("ThreadPool не запущен. Вызовите start() сначала.")
            
        return self._executor.map(fn, *iterables, timeout=timeout, chunksize=chunksize)
    
    @property
    def is_running(self) -> bool:
        """Проверка состояния пула"""
        return self._executor is not None and not self._shutdown
    
    def __enter__(self):
        """Context manager entry"""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.shutdown(wait=True, timeout=30)

class AsyncRouteHandler:
    """
    Улучшенный асинхронный обработчик маршрутов
    Исправляет проблемы с ThreadPoolExecutor
    """
    
    def __init__(self, max_workers: int = 4, request_timeout: float = 30.0):
        """
        Инициализация обработчика
        
        Args:
            max_workers: Количество рабочих потоков
            request_timeout: Таймаут обработки запросов
        """
        self.max_workers = max_workers
        self.request_timeout = request_timeout
        self.executor = CompatibleThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix='AsyncRoute'
        )
        self._running = False
        
        logger.info(f"✅ AsyncRouteHandler инициализирован "
                   f"(workers: {max_workers}, timeout: {request_timeout}s)")
    
    async def start(self):
        """Запуск обработчика"""
        if not self._running:
            self.executor.start()
            self._running = True
            logger.info("🚀 AsyncRouteHandler запущен")
    
    async def stop(self):
        """Остановка обработчика"""
        if self._running:
            logger.info("🛑 Остановка AsyncRouteHandler...")
            
            try:
                # Безопасная остановка с учетом версии Python
                self.executor.shutdown(wait=True, timeout=self.request_timeout)
                logger.info("✅ AsyncRouteHandler остановлен успешно")
                
            except Exception as e:
                logger.error(f"❌ Ошибка при остановке AsyncRouteHandler: {e}")
                
            finally:
                self._running = False
    
    async def execute_in_thread(self, func: Callable, *args, **kwargs) -> Any:
        """
        Выполнение функции в отдельном потоке
        
        Args:
            func: Функция для выполнения
            *args: Позиционные аргументы
            **kwargs: Именованные аргументы
            
        Returns:
            Результат выполнения функции
        """
        if not self._running:
            await self.start()
        
        loop = asyncio.get_event_loop()
        
        try:
            # Выполняем в пуле потоков с таймаутом
            future = self.executor.submit(func, *args, **kwargs)
            result = await asyncio.wait_for(
                loop.run_in_executor(None, future.result),
                timeout=self.request_timeout
            )
            return result
            
        except asyncio.TimeoutError:
            logger.error(f"⏰ Таймаут выполнения функции {func.__name__}")
            raise
        except Exception as e:
            logger.error(f"❌ Ошибка выполнения {func.__name__}: {e}")
            raise
    
    @asynccontextmanager
    async def managed_execution(self):
        """Context manager для безопасного выполнения"""
        await self.start()
        try:
            yield self
        finally:
            await self.stop()

class SystemdCompatibleService:
    """
    Сервис совместимый с systemd для автоматического восстановления
    """
    
    def __init__(self, service_name: str = "crypto-trading-bot"):
        """
        Инициализация сервиса
        
        Args:
            service_name: Имя сервиса
        """
        self.service_name = service_name
        self.is_running = False
        self.shutdown_event = threading.Event()
        
    def create_systemd_service_file(self) -> str:
        """
        Создание файла systemd сервиса
        
        Returns:
            Содержимое .service файла
        """
        # Определяем пути
        work_dir = os.getcwd()
        python_path = sys.executable
        script_path = os.path.join(work_dir, "main.py")
        
        service_content = f"""[Unit]
Description=Crypto Trading Bot v3.0
After=network.target
Wants=network.target

[Service]
Type=simple
User=root
Group=root
WorkingDirectory={work_dir}
Environment=PATH={os.environ.get('PATH', '')}
Environment=PYTHONPATH={work_dir}
ExecStart={python_path} {script_path} web
ExecReload=/bin/kill -HUP $MAINPID
KillMode=mixed
Restart=always
RestartSec=10
TimeoutStopSec=30

# Логирование
StandardOutput=journal
StandardError=journal
SyslogIdentifier={self.service_name}

# Безопасность
NoNewPrivileges=yes
PrivateTmp=yes

# Лимиты ресурсов
LimitNOFILE=65536
MemoryMax=2G
CPUQuota=200%

[Install]
WantedBy=multi-user.target
"""
        return service_content
    
    def install_systemd_service(self) -> bool:
        """
        Установка systemd сервиса
        
        Returns:
            True если успешно установлен
        """
        try:
            # Создаем файл сервиса
            service_content = self.create_systemd_service_file()
            service_file_path = f"/etc/systemd/system/{self.service_name}.service"
            
            # Записываем файл
            with open(service_file_path, 'w') as f:
                f.write(service_content)
            
            # Перезагружаем systemd
            subprocess.run(['systemctl', 'daemon-reload'], check=True)
            
            # Включаем автозапуск
            subprocess.run(['systemctl', 'enable', self.service_name], check=True)
            
            logger.info(f"✅ Systemd сервис {self.service_name} успешно установлен")
            logger.info(f"📁 Файл сервиса: {service_file_path}")
            logger.info("🔧 Команды управления:")
            logger.info(f"   sudo systemctl start {self.service_name}")
            logger.info(f"   sudo systemctl stop {self.service_name}")
            logger.info(f"   sudo systemctl status {self.service_name}")
            logger.info(f"   sudo journalctl -u {self.service_name} -f")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка установки systemd сервиса: {e}")
            return False
    
    def setup_auto_recovery(self) -> bool:
        """
        Настройка автоматического восстановления
        
        Returns:
            True если настройка успешна
        """
        try:
            # Создаем скрипт мониторинга
            monitor_script = self.create_monitoring_script()
            monitor_path = "/opt/crypto-bot/monitor.py"
            
            # Создаем директорию если нужно
            os.makedirs(os.path.dirname(monitor_path), exist_ok=True)
            
            with open(monitor_path, 'w') as f:
                f.write(monitor_script)
            
            # Делаем исполняемым
            os.chmod(monitor_path, 0o755)
            
            # Создаем cron задачу
            cron_job = f"*/2 * * * * /usr/bin/python3 {monitor_path} >> /var/log/crypto-bot-monitor.log 2>&1\n"
            
            logger.info(f"✅ Скрипт мониторинга создан: {monitor_path}")
            logger.info("⏰ Добавьте в crontab:")
            logger.info(f"   echo '{cron_job.strip()}' | crontab -")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка настройки автовосстановления: {e}")
            return False
    
    def create_monitoring_script(self) -> str:
        """
        Создание скрипта мониторинга состояния
        
        Returns:
            Содержимое скрипта мониторинга
        """
        script_content = f"""#!/usr/bin/env python3
\"\"\"
Скрипт мониторинга и автовосстановления для Crypto Trading Bot
\"\"\"
import subprocess
import time
import sys
import logging
import requests
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

SERVICE_NAME = "{self.service_name}"
HEALTH_CHECK_URL = "http://localhost:8000/api/health"
MAX_RESTART_ATTEMPTS = 3
RESTART_DELAY = 30

def check_service_status():
    \"\"\"Проверка статуса systemd сервиса\"\"\"
    try:
        result = subprocess.run(
            ['systemctl', 'is-active', SERVICE_NAME],
            capture_output=True,
            text=True
        )
        return result.stdout.strip() == 'active'
    except Exception as e:
        logger.error(f"Ошибка проверки статуса сервиса: {{e}}")
        return False

def check_health_endpoint():
    \"\"\"Проверка health endpoint\"\"\"
    try:
        response = requests.get(HEALTH_CHECK_URL, timeout=10)
        return response.status_code == 200
    except Exception as e:
        logger.warning(f"Health check недоступен: {{e}}")
        return False

def restart_service():
    \"\"\"Перезапуск сервиса\"\"\"
    try:
        subprocess.run(['systemctl', 'restart', SERVICE_NAME], check=True)
        logger.info(f"Сервис {{SERVICE_NAME}} перезапущен")
        return True
    except Exception as e:
        logger.error(f"Ошибка перезапуска сервиса: {{e}}")
        return False

def main():
    \"\"\"Основная логика мониторинга\"\"\"
    logger.info("🔍 Проверка состояния Crypto Trading Bot...")
    
    # Проверяем systemd статус
    service_running = check_service_status()
    logger.info(f"Systemd сервис: {{'активен' if service_running else 'неактивен'}}")
    
    # Проверяем health endpoint
    health_ok = check_health_endpoint()
    logger.info(f"Health endpoint: {{'доступен' if health_ok else 'недоступен'}}")
    
    # Принимаем решение о перезапуске
    needs_restart = not service_running or not health_ok
    
    if needs_restart:
        logger.warning("⚠️ Обнаружена проблема, выполняется перезапуск...")
        
        if restart_service():
            # Ждем запуска
            time.sleep(RESTART_DELAY)
            
            # Проверяем результат
            if check_service_status() and check_health_endpoint():
                logger.info("✅ Сервис успешно восстановлен")
            else:
                logger.error("❌ Не удалось восстановить сервис")
        else:
            logger.error("❌ Ошибка перезапуска сервиса")
    else:
        logger.info("✅ Все системы работают нормально")

if __name__ == "__main__":
    main()
"""
        return script_content

# Утилиты для миграции существующего кода
def safe_executor_shutdown(executor: ThreadPoolExecutor, 
                         timeout: Optional[float] = None) -> bool:
    """
    Безопасная остановка ThreadPoolExecutor
    
    Args:
        executor: Экземпляр ThreadPoolExecutor
        timeout: Таймаут ожидания
        
    Returns:
        True если остановка прошла успешно
    """
    try:
        compatible_executor = CompatibleThreadPoolExecutor(max_workers=1)
        compatible_executor._executor = executor
        compatible_executor.shutdown(wait=True, timeout=timeout)
        return True
    except Exception as e:
        logger.error(f"Ошибка остановки executor: {e}")
        return False

# Декоратор для автоматической обработки ThreadPool ошибок
def handle_threadpool_errors(func):
    """
    Декоратор для обработки ошибок ThreadPool
    """
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except TypeError as e:
            if "timeout" in str(e):
                logger.warning(f"Проблема с timeout параметром в {func.__name__}: {e}")
                # Попробуем без timeout
                return func(*args, **{k: v for k, v in kwargs.items() if k != 'timeout'})
            else:
                raise
        except Exception as e:
            logger.error(f"Ошибка в {func.__name__}: {e}")
            raise
    return wrapper