#!/usr/bin/env python3
"""
Database module с поддержкой SessionLocal - ИСПРАВЛЕННАЯ ВЕРСИЯ
===============================================================
✅ ИСПРАВЛЕНИЯ:
- Правильная инициализация SessionLocal
- Исправлена работа с PyMySQL
- Добавлены проверки подключения
- Исправлена работа с unified_config
"""
import os
from contextlib import contextmanager
from sqlalchemy import create_engine, MetaData, text
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import QueuePool
from dotenv import load_dotenv
import logging

# Загружаем переменные окружения
for env_path in ['/etc/crypto/config/.env', '.env']:
    if os.path.exists(env_path):
        load_dotenv(env_path)
        break

logger = logging.getLogger(__name__)

class Database:
    """Singleton класс для работы с базой данных - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    
    _instance = None
    _engine = None
    _metadata = None
    _SessionLocal = None
    _Session = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
        return cls._instance
        
    def test_connection(self) -> bool:
        """
        ✅ ИСПРАВЛЕНО: Тестирует подключение к базе данных
        
        Returns:
            bool: True если подключение успешно, False в противном случае
        """
        try:
            # Пробуем выполнить простой запрос
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                result.fetchone()
            
            logger.info("✅ Тест подключения к БД успешен")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка тестирования БД: {e}")
            return False
    
    def __init__(self):
        """✅ ИСПРАВЛЕНО: Инициализация подключения к БД"""
        if self._engine is None:
            self.database_url = self._get_database_url()
            self._create_engine()
            self._create_session_factory()
            
    def _get_database_url(self) -> str:
        """✅ ИСПРАВЛЕНО: Получение URL базы данных с правильными приоритетами"""
        
        # 1. Пробуем получить из unified_config
        try:
            from .unified_config import unified_config
            database_url = unified_config.get_database_url()
            if database_url and database_url != 'sqlite:///./crypto_bot.db':
                logger.info("📋 URL БД получен из unified_config")
                return database_url
        except ImportError:
            logger.warning("⚠️ unified_config недоступен, используем переменные окружения")
        
        # 2. Проверяем переменную окружения DATABASE_URL
        database_url = os.getenv('DATABASE_URL')
        if database_url:
            # Исправляем URL для PyMySQL
            if database_url.startswith('mysql://'):
                database_url = database_url.replace('mysql://', 'mysql+pymysql://')
                logger.info("🔧 URL БД исправлен: mysql:// → mysql+pymysql://")
            elif 'mysql+mysqldb://' in database_url:
                database_url = database_url.replace('mysql+mysqldb://', 'mysql+pymysql://')
                logger.info("🔧 URL БД исправлен: MySQLdb → PyMySQL")
                
            logger.info("📋 URL БД получен из DATABASE_URL")
            return database_url
        
        # 3. Формируем URL из отдельных параметров
        db_host = os.getenv('DB_HOST', 'localhost')
        db_port = os.getenv('DB_PORT', '3306')
        db_user = os.getenv('DB_USER')
        db_pass = os.getenv('DB_PASSWORD')
        db_name = os.getenv('DB_NAME')
        
        if db_user and db_pass and db_name:
            database_url = f"mysql+pymysql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}?charset=utf8mb4"
            logger.info("📋 URL БД сформирован из отдельных параметров")
            return database_url
        elif db_name:  # Без пароля
            database_url = f"mysql+pymysql://{db_user or 'root'}@{db_host}:{db_port}/{db_name}?charset=utf8mb4"
            logger.info("📋 URL БД сформирован без пароля")
            return database_url
        
        # 4. Fallback на SQLite
        database_url = "sqlite:///./crypto_bot.db"
        logger.warning("⚠️ Используется SQLite база данных (fallback)")
        return database_url
    
    def _create_engine(self):
        """✅ ИСПРАВЛЕНО: Создание engine с правильными настройками"""
        try:
            # Настройки для разных типов БД
            engine_kwargs = {
                'pool_pre_ping': True,
                'echo': False,
                'pool_recycle': 3600,  # Переподключение каждый час
            }
            
            # Дополнительные настройки для MySQL
            if 'mysql' in self.database_url:
                engine_kwargs.update({
                    'poolclass': QueuePool,
                    'pool_size': 10,
                    'max_overflow': 20,
                    'pool_timeout': 30,
                    'connect_args': {
                        'charset': 'utf8mb4',
                        'autocommit': False,
                    }
                })
            
            self._engine = create_engine(self.database_url, **engine_kwargs)
            logger.info("✅ Database engine создан успешно")
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания engine: {e}")
            # Fallback на SQLite
            self.database_url = "sqlite:///./crypto_bot.db"
            self._engine = create_engine(self.database_url, pool_pre_ping=True)
            logger.warning("⚠️ Переключен на SQLite из-за ошибки подключения к MySQL")
    
    def _create_session_factory(self):
        """✅ ИСПРАВЛЕНО: Создание фабрики сессий"""
        try:
            # Создаем sessionmaker
            self._Session = sessionmaker(bind=self._engine, expire_on_commit=False)
            
            # ✅ КРИТИЧНОЕ ИСПРАВЛЕНИЕ: Создаем SessionLocal для совместимости
            self._SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self._engine,
                expire_on_commit=False
            )
            
            # Создаем scoped_session для thread-safety
            self.Session = scoped_session(self._Session)
            
            logger.info("✅ Session factories созданы успешно")
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания session factories: {e}")
            raise
    
    @property
    def engine(self):
        """Получить engine"""
        return self._engine
        
    def create_tables(self):
        """Создать все таблицы в базе данных"""
        try:
            from .models import Base
            Base.metadata.create_all(bind=self._engine)
            logger.info("✅ Таблицы созданы успешно")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка создания таблиц: {e}")
            return False
    
    @property
    def metadata(self):
        """Получить metadata"""
        if self._metadata is None:
            self._metadata = MetaData()
        return self._metadata
    
    @contextmanager
    def get_session(self):
        """Контекстный менеджер для сессии"""
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Ошибка в сессии БД: {e}")
            raise
        finally:
            session.close()
    
    def create_session(self):
        """✅ ИСПРАВЛЕНО: Создать новую сессию через SessionLocal"""
        if self._SessionLocal:
            return self._SessionLocal()
        else:
            logger.warning("⚠️ SessionLocal не инициализирован, используем Session")
            return self.Session()
    
    def get_session_local(self):
        """✅ НОВЫЙ МЕТОД: Получить SessionLocal фабрику"""
        return self._SessionLocal
    
    def close(self):
        """Закрыть все соединения"""
        try:
            if hasattr(self, 'Session'):
                self.Session.remove()
            if self._engine:
                self._engine.dispose()
            logger.info("✅ Соединения с БД закрыты")
        except Exception as e:
            logger.error(f"❌ Ошибка закрытия соединений: {e}")

# ✅ ИСПРАВЛЕНО: Создаем глобальный экземпляр
db = Database()

# ✅ ИСПРАВЛЕНО: Экспортируем все необходимые компоненты для обратной совместимости
engine = db.engine
metadata = db.metadata
get_session = db.get_session
create_session = db.create_session

# ✅ КРИТИЧНОЕ ИСПРАВЛЕНИЕ: Правильный экспорт SessionLocal
SessionLocal = db.get_session_local()

# Дополнительные функции для совместимости
def get_db():
    """Генератор сессий для FastAPI"""
    if SessionLocal:
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()
    else:
        logger.error("❌ SessionLocal не инициализирован")
        return None

# Декоратор для транзакций
def transaction(func):
    """Декоратор для выполнения функции в транзакции"""
    def wrapper(*args, **kwargs):
        if SessionLocal:
            session = SessionLocal()
            try:
                result = func(session, *args, **kwargs)
                session.commit()
                return result
            except Exception as e:
                session.rollback()
                raise
            finally:
                session.close()
        else:
            logger.error("❌ SessionLocal не инициализирован для транзакции")
            return None
    return wrapper

# ✅ ИСПРАВЛЕНО: Функция инициализации для внешнего вызова
def initialize_database():
    """Инициализация базы данных (можно вызывать из других модулей)"""
    try:
        # Проверяем подключение
        if db.test_connection():
            logger.info("✅ База данных инициализирована и протестирована")
            return True
        else:
            logger.error("❌ Не удалось подключиться к базе данных")
            return False
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации БД: {e}")
        return False

# ✅ ИСПРАВЛЕНО: Функция диагностики
def diagnose_database():
    """Диагностика состояния базы данных"""
    diagnostics = {
        'engine_created': db._engine is not None,
        'session_factory_created': db._SessionLocal is not None,
        'sessionlocal_available': SessionLocal is not None,
        'connection_test': False,
        'database_url': db.database_url if hasattr(db, 'database_url') else 'Unknown'
    }
    
    # Тест подключения
    try:
        diagnostics['connection_test'] = db.test_connection()
    except Exception as e:
        diagnostics['connection_error'] = str(e)
    
    # Логируем результаты
    logger.info("🔍 ДИАГНОСТИКА БАЗЫ ДАННЫХ:")
    for key, value in diagnostics.items():
        status = "✅" if value else "❌"
        logger.info(f"   {status} {key}: {value}")
    
    return diagnostics
    
def test_database_connection():
    """Проверка подключения к базе данных"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
        logger.info("✅ Подключение к БД успешно")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка подключения к БД: {e}")
        return False

__all__ = [
    'Database',
    'db',
    'engine',
    'metadata',
    'get_session',
    'create_session',
    'SessionLocal',
    'get_db',
    'transaction',
    'initialize_database',
    'diagnose_database'
]