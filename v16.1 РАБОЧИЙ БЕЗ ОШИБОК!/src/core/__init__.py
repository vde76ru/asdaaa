#!/usr/bin/env python3
"""
ИСПРАВЛЕННЫЙ Core модуль - центральное место для всех базовых компонентов
=======================================================================

🔧 ИСПРАВЛЕНИЯ v6.8.8:
✅ Добавлен импорт unified_config как config для совместимости
✅ Безопасные импорты с обработкой ошибок
✅ Правильные алиасы для обратной совместимости
✅ Экспорт всех необходимых компонентов

Путь: src/core/__init__.py
"""

import logging
logger = logging.getLogger(__name__)

# =================================================================
# ИМПОРТ МОДЕЛЕЙ - БЕЗОПАСНО
# =================================================================

try:
    # Импортируем все модели из models.py (ЕДИНСТВЕННЫЙ ИСТОЧНИК МОДЕЛЕЙ)
    from .models import (
        Base,
        # Enums
        TradeStatus,
        OrderSide,
        OrderType,
        SignalAction,
        # Models
        User,
        BotSettings,
        BotState,
        Balance,
        TradingPair,
        Signal,
        Trade,
        Order,
        Candle,
        MarketCondition,
        StrategyPerformance,
        MLModel,
        MLPrediction,
        TradeMLPrediction,
        NewsAnalysis,
        SocialSignal,
        TradingLog
    )
    MODELS_AVAILABLE = True
    logger.info("✅ Модели базы данных импортированы успешно")
except ImportError as e:
    logger.warning(f"⚠️ Ошибка импорта моделей: {e}")
    MODELS_AVAILABLE = False
    # Создаем заглушки для критически важных моделей
    Base = None
    TradeStatus = OrderSide = OrderType = SignalAction = None
    User = BotSettings = BotState = Balance = TradingPair = None
    Signal = Trade = Order = Candle = MarketCondition = None
    StrategyPerformance = MLModel = MLPrediction = TradeMLPrediction = None
    NewsAnalysis = SocialSignal = TradingLog = None

# =================================================================
# ИМПОРТ БАЗЫ ДАННЫХ - БЕЗОПАСНО
# =================================================================

try:
    # Импортируем компоненты базы данных
    from .database import (
        Database,
        db,
        engine,
        SessionLocal,
        get_db,
        get_session,
        create_session,
        transaction
    )
    DATABASE_AVAILABLE = True
    logger.info("✅ Компоненты базы данных импортированы успешно")
except ImportError as e:
    logger.warning(f"⚠️ Ошибка импорта базы данных: {e}")
    DATABASE_AVAILABLE = False
    # Создаем заглушки
    Database = db = engine = SessionLocal = None
    get_db = get_session = create_session = transaction = None

# =================================================================
# ИМПОРТ КОНФИГУРАЦИИ - ИСПРАВЛЕНО
# =================================================================

try:
    # ✅ ИСПРАВЛЕНИЕ: Импортируем unified_config
    from .unified_config import unified_config
    
    # ✅ ИСПРАВЛЕНИЕ: Создаем алиасы для обратной совместимости
    config = unified_config
    settings = unified_config
    
    CONFIG_AVAILABLE = True
    logger.info("✅ Конфигурация импортирована успешно")
    logger.info(f"📋 Режим работы: {getattr(unified_config, 'ENVIRONMENT', 'unknown')}")
    
except ImportError as e:
    logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА: Не удалось импортировать unified_config: {e}")
    CONFIG_AVAILABLE = False
    
    # Создаем минимальную заглушку конфигурации
    class MinimalConfig:
        """Минимальная заглушка конфигурации для аварийного режима"""
        ENVIRONMENT = "emergency"
        TESTNET = True
        PAPER_TRADING = True
        LIVE_TRADING = False
        
        def __getattr__(self, name):
            logger.warning(f"⚠️ Попытка доступа к отсутствующей конфигурации: {name}")
            return None
    
    unified_config = MinimalConfig()
    config = unified_config
    settings = unified_config

# =================================================================
# ДОПОЛНИТЕЛЬНЫЕ ИМПОРТЫ
# =================================================================

# Попытка импорта bybit_config (опциональный)
try:
    from .bybit_config import bybit_config
    BYBIT_CONFIG_AVAILABLE = True
    logger.info("✅ Bybit конфигурация доступна")
except ImportError:
    bybit_config = None
    BYBIT_CONFIG_AVAILABLE = False
    logger.info("ℹ️ Bybit конфигурация недоступна (не критично)")

# =================================================================
# ФУНКЦИИ ПРОВЕРКИ ДОСТУПНОСТИ
# =================================================================

def check_core_components() -> dict:
    """
    Проверка доступности основных компонентов core модуля
    
    Returns:
        dict: Статус каждого компонента
    """
    status = {
        'models': MODELS_AVAILABLE,
        'database': DATABASE_AVAILABLE, 
        'config': CONFIG_AVAILABLE,
        'bybit_config': BYBIT_CONFIG_AVAILABLE,
        'critical_components': MODELS_AVAILABLE and DATABASE_AVAILABLE and CONFIG_AVAILABLE
    }
    
    # Логируем статус
    for component, available in status.items():
        if component != 'critical_components':
            emoji = "✅" if available else "❌"
            logger.info(f"   {emoji} {component}: {available}")
    
    return status

def get_db_session():
    """
    Безопасное получение сессии БД
    
    Returns:
        Session или None при ошибке
    """
    if not DATABASE_AVAILABLE or not SessionLocal:
        logger.warning("⚠️ База данных недоступна")
        return None
        
    try:
        return SessionLocal()
    except Exception as e:
        logger.error(f"❌ Ошибка создания сессии БД: {e}")
        return None

def get_config_value(key: str, default=None):
    """
    Безопасное получение значения конфигурации
    
    Args:
        key: Название параметра
        default: Значение по умолчанию
        
    Returns:
        Значение конфигурации или default
    """
    if not CONFIG_AVAILABLE:
        logger.warning(f"⚠️ Конфигурация недоступна для ключа: {key}")
        return default
        
    try:
        return getattr(unified_config, key, default)
    except Exception as e:
        logger.warning(f"⚠️ Ошибка получения конфигурации {key}: {e}")
        return default

# =================================================================
# ДИАГНОСТИЧЕСКИЕ ФУНКЦИИ
# =================================================================

def diagnose_core_issues():
    """Диагностика проблем в core модуле"""
    issues = []
    
    if not MODELS_AVAILABLE:
        issues.append("❌ Модели базы данных недоступны - проверьте src/core/models.py")
    
    if not DATABASE_AVAILABLE:
        issues.append("❌ База данных недоступна - проверьте src/core/database.py")
        
    if not CONFIG_AVAILABLE:
        issues.append("❌ Конфигурация недоступна - проверьте src/core/unified_config.py")
    
    if issues:
        logger.error("🚨 ОБНАРУЖЕНЫ ПРОБЛЕМЫ В CORE МОДУЛЕ:")
        for issue in issues:
            logger.error(f"   {issue}")
    else:
        logger.info("✅ Все компоненты core модуля работают корректно")
    
    return issues

# =================================================================
# ЭКСПОРТ ВСЕХ КОМПОНЕНТОВ
# =================================================================

__all__ = [
    # Статус компонентов
    'MODELS_AVAILABLE',
    'DATABASE_AVAILABLE', 
    'CONFIG_AVAILABLE',
    'BYBIT_CONFIG_AVAILABLE',
    
    # База данных (если доступна)
    'Base',
    
    # Enums (если доступны)
    'TradeStatus',
    'OrderSide', 
    'OrderType',
    'SignalAction',
    
    # Models (если доступны)
    'User',
    'BotSettings',
    'BotState',
    'Balance',
    'TradingPair',
    'Signal',
    'Trade',
    'Order',
    'Candle',
    'MarketCondition',
    'StrategyPerformance',
    'MLModel',
    'MLPrediction',
    'TradeMLPrediction',
    'NewsAnalysis',
    'SocialSignal',
    'TradingLog',
    
    # Database (если доступна)
    'Database',
    'db',
    'engine',
    'SessionLocal',
    'get_db',
    'get_session',
    'create_session',
    'transaction',
    
    # Config (ИСПРАВЛЕНО)
    'unified_config',
    'config',           # ✅ Алиас для совместимости
    'settings',         # ✅ Алиас для совместимости
    'bybit_config',     # ✅ Опциональная конфигурация Bybit
    
    # Функции
    'check_core_components',
    'get_db_session',
    'get_config_value',
    'diagnose_core_issues'
]

# =================================================================
# АВТОМАТИЧЕСКАЯ ПРОВЕРКА ПРИ ИМПОРТЕ
# =================================================================

# Проверяем статус компонентов при импорте
logger.info("🔍 Проверка компонентов core модуля...")
component_status = check_core_components()

if component_status['critical_components']:
    logger.info("✅ Все критически важные компоненты доступны")
else:
    logger.warning("⚠️ Некоторые критически важные компоненты недоступны")
    diagnose_core_issues()

# Показываем краткую сводку
logger.info(f"📊 Core статус: Models={MODELS_AVAILABLE}, DB={DATABASE_AVAILABLE}, Config={CONFIG_AVAILABLE}")

# ✅ ИСПРАВЛЕНИЕ: Убеждаемся что config доступен для импорта
if not CONFIG_AVAILABLE:
    logger.error("🚨 КРИТИЧЕСКАЯ ОШИБКА: unified_config недоступен!")
    logger.error("💡 Убедитесь что файл src/core/unified_config.py существует и не содержит ошибок")
else:
    logger.info("✅ unified_config доступен как 'config' для совместимости")