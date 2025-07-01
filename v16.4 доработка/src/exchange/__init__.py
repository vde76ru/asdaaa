"""
Exchange модули для работы с биржами - ИСПРАВЛЕННАЯ ВЕРСИЯ
Файл: src/exchange/__init__.py

✅ ИСПРАВЛЕНО: Убраны fallback импорты, добавлена четкая диагностика
"""
import logging
from typing import Dict, Tuple

try:
    from ..logging import get_logger
    logger = get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

# ✅ ПРЯМОЙ ИМПОРТ ОСНОВНОГО МОДУЛЯ с четкой диагностикой
try:
    from .unified_exchange import (
        UnifiedExchangeClient,
        BaseExchangeClient, 
        ExchangeClientFactory,
        get_real_exchange_client,
        get_exchange_client
    )
    logger.info("✅ Unified Exchange модули импортированы успешно")
    UNIFIED_AVAILABLE = True
except ImportError as e:
    error_msg = f"❌ Критический модуль unified_exchange недоступен: {e}"
    logger.critical(error_msg)
    logger.critical("💡 Проверьте файл src/exchange/unified_exchange.py")
    logger.critical("💡 Убедитесь что все зависимости установлены: pip install ccxt")
    raise ImportError("Критический модуль unified_exchange не может быть импортирован. "
                     "Система не может работать без базового клиента биржи.") from e

# ✅ ПРОВЕРКА ДОСТУПНОСТИ CCXT
def _check_exchange_dependencies() -> dict:
    """Проверка доступности зависимостей для работы с биржами"""
    dependencies = {
        'ccxt': False,
        'websocket': False,
        'aiohttp': False,
        'requests': False,
    }
    
    try:
        import ccxt
        dependencies['ccxt'] = True
        logger.info(f"✅ CCXT версия: {ccxt.__version__}")
    except ImportError:
        logger.critical("❌ CCXT не установлен - критическая зависимость!")
    
    try:
        import websocket
        dependencies['websocket'] = True
    except ImportError:
        logger.warning("⚠️ websocket-client не установлен - WebSocket функции недоступны")
    
    try:
        import aiohttp
        dependencies['aiohttp'] = True
    except ImportError:
        logger.warning("⚠️ aiohttp не установлен - асинхронные HTTP запросы могут быть ограничены")
    
    try:
        import requests
        dependencies['requests'] = True
    except ImportError:
        logger.warning("⚠️ requests не установлен - HTTP функции ограничены")
    
    return dependencies

# ✅ СОЗДАНИЕ АЛИАСОВ ДЛЯ ОБРАТНОЙ СОВМЕСТИМОСТИ
ExchangeClient = UnifiedExchangeClient

# ✅ ИМПОРТ ДОПОЛНИТЕЛЬНЫХ МОДУЛЕЙ с четкой диагностикой
def _import_optional_exchange_module(module_name: str, class_names: list):
    """Импорт опциональных exchange модулей"""
    try:
        # ✅ ИСПРАВЛЕНО: правильный синтаксис __import__
        module = __import__(f"{__name__}.{module_name}", fromlist=class_names)
        components = {}
        for class_name in class_names:
            try:
                components[class_name] = getattr(module, class_name)
                logger.info(f"✅ {class_name} импортирован из {module_name}")
            except AttributeError:
                logger.warning(f"⚠️ Класс {class_name} не найден в модуле {module_name}")
                components[class_name] = None
        return components
    except ImportError as e:
        logger.warning(f"⚠️ Опциональный модуль {module_name} недоступен: {e}")
        return {class_name: None for class_name in class_names}
        
# Импортируем остальные модули
logger.info("🔍 Импортируем дополнительные exchange модули...")

position_components = _import_optional_exchange_module(
    'position_manager', 
    ['PositionManager', 'get_position_manager']
)

execution_components = _import_optional_exchange_module(
    'execution_engine', 
    ['OrderExecutionEngine', 'get_execution_engine']
)

# ✅ BYBIT V5 ИНТЕГРАЦИЯ - НОВОЕ
logger.info("🔍 Проверяем доступность Bybit V5 модулей...")

bybit_v5_components = _import_optional_exchange_module(
    'bybit_client_v5',
    ['BybitClientV5', 'create_bybit_client_from_env']
)

bybit_integration_components = _import_optional_exchange_module(
    'bybit_integration',
    ['BybitIntegrationManager', 'EnhancedUnifiedExchangeClient', 'upgrade_existing_client']
)

# Извлекаем компоненты
PositionManager = position_components['PositionManager']
get_position_manager = position_components['get_position_manager']
OrderExecutionEngine = execution_components['OrderExecutionEngine']
get_execution_engine = execution_components['get_execution_engine']

# Bybit V5 компоненты
BybitClientV5 = bybit_v5_components['BybitClientV5']
create_bybit_client_from_env = bybit_v5_components['create_bybit_client_from_env']
BybitIntegrationManager = bybit_integration_components['BybitIntegrationManager']
EnhancedUnifiedExchangeClient = bybit_integration_components['EnhancedUnifiedExchangeClient']
upgrade_existing_client = bybit_integration_components['upgrade_existing_client']

# Флаги доступности Bybit V5
BYBIT_V5_AVAILABLE = BybitClientV5 is not None
BYBIT_INTEGRATION_AVAILABLE = BybitIntegrationManager is not None

# ✅ ФУНКЦИЯ ДЛЯ ПОЛУЧЕНИЯ ENHANCED КЛИЕНТА
def get_enhanced_exchange_client():
    """Получение enhanced клиента если доступен"""
    if BYBIT_INTEGRATION_AVAILABLE:
        return EnhancedUnifiedExchangeClient()
    else:
        logger.info("🔄 Enhanced клиент недоступен, используем стандартный")
        return get_real_exchange_client()

def check_bybit_v5_capabilities() -> Dict[str, bool]:
    """Проверка возможностей Bybit V5"""
    return {
        'v5_client_available': BYBIT_V5_AVAILABLE,
        'integration_available': BYBIT_INTEGRATION_AVAILABLE,
        'enhanced_features': BYBIT_V5_AVAILABLE and BYBIT_INTEGRATION_AVAILABLE
    }

# ✅ ФУНКЦИЯ ПРОВЕРКИ EXCHANGE ВОЗМОЖНОСТЕЙ
def check_exchange_capabilities() -> dict:
    """
    Проверка доступности exchange возможностей
    
    Returns:
        dict: Подробный статус exchange компонентов
    """
    deps = _check_exchange_dependencies()
    bybit_caps = check_bybit_v5_capabilities()
    
    capabilities = {
        # Зависимости
        'dependencies': deps,
        
        # Основные компоненты
        'unified_client': UnifiedExchangeClient is not None,
        'base_client': BaseExchangeClient is not None,
        'client_factory': ExchangeClientFactory is not None,
        
        # Дополнительные компоненты
        'position_manager': PositionManager is not None,
        'execution_engine': OrderExecutionEngine is not None,
        
        # Bybit V5 компоненты
        'bybit_v5_client': BYBIT_V5_AVAILABLE,
        'bybit_integration': BYBIT_INTEGRATION_AVAILABLE,
        'enhanced_client': BYBIT_INTEGRATION_AVAILABLE,
        
        # Общий статус
        'basic_trading': all([
            deps['ccxt'],
            UnifiedExchangeClient is not None
        ]),
        'advanced_trading': all([
            deps['ccxt'],
            deps['websocket'],
            UnifiedExchangeClient is not None,
            PositionManager is not None,
            OrderExecutionEngine is not None
        ]),
        'bybit_v5_trading': all([
            deps['ccxt'],
            BYBIT_V5_AVAILABLE,
            BYBIT_INTEGRATION_AVAILABLE
        ]),
        'full_exchange_stack': all([
            deps['ccxt'],
            deps['websocket'],
            deps['aiohttp'],
            UnifiedExchangeClient is not None,
            PositionManager is not None,
            OrderExecutionEngine is not None,
            BYBIT_V5_AVAILABLE,
            BYBIT_INTEGRATION_AVAILABLE
        ])
    }
    
    logger.info("📈 Доступность Exchange возможностей:")
    logger.info(f"   ✅ Базовая торговля: {capabilities['basic_trading']}")
    logger.info(f"   🔬 Продвинутая торговля: {capabilities['advanced_trading']}")
    logger.info(f"   🎯 Bybit V5 торговля: {capabilities['bybit_v5_trading']}")
    logger.info(f"   🚀 Полный Exchange стек: {capabilities['full_exchange_stack']}")
    
    return capabilities

def get_exchange_recommendation() -> str:
    """Получить рекомендации по улучшению Exchange возможностей"""
    caps = check_exchange_capabilities()
    
    if caps['full_exchange_stack']:
        return "🎉 Полный Exchange стек с Bybit V5 доступен - все торговые возможности активны!"
    elif caps['bybit_v5_trading']:
        return "🎯 Bybit V5 торговля работает! Для полного стека установите aiohttp и websocket-client"
    elif caps['advanced_trading']:
        return "🔬 Продвинутая торговля доступна. Для Bybit V5 добавьте соответствующие модули"
    elif caps['basic_trading']:
        return "⚡ Базовая торговля работает. Для WebSocket установите websocket-client"
    else:
        return "❌ Торговые возможности ограничены. Установите ccxt: pip install ccxt"

# Экспорт
__all__ = [
    # Основные классы
    'UnifiedExchangeClient',
    'BaseExchangeClient',
    'ExchangeClientFactory',
    
    # Алиасы для совместимости
    'ExchangeClient',
    
    # Функции
    'get_real_exchange_client',
    'get_exchange_client',
    'get_position_manager',
    'get_execution_engine',
    'get_enhanced_exchange_client',
    
    # Дополнительные классы
    'PositionManager',
    'OrderExecutionEngine',
    
    # Bybit V5 классы (если доступны)
    'BybitClientV5',
    'create_bybit_client_from_env',
    'BybitIntegrationManager',
    'EnhancedUnifiedExchangeClient',
    'upgrade_existing_client',
    
    # Флаги доступности
    'BYBIT_V5_AVAILABLE',
    'BYBIT_INTEGRATION_AVAILABLE',
    
    # Диагностические функции
    'check_exchange_capabilities',
    'check_bybit_v5_capabilities',
    'get_exchange_recommendation'
]

try:
    from .unified_exchange import UnifiedExchangeClient
    # Создаем псевдонимы
    class unified_exchange_client:
        UnifiedExchangeClient = UnifiedExchangeClient
        
    # Добавляем в globals для импорта
    import sys
    sys.modules[f'{__name__}.unified_exchange_client'] = unified_exchange_client
    
except ImportError:
    pass

# ✅ АВТОМАТИЧЕСКАЯ ПРОВЕРКА ПРИ ИМПОРТЕ
logger.info("📈 Инициализация Exchange модулей...")
_dependencies = _check_exchange_dependencies()

if not _dependencies['ccxt']:
    raise ImportError("❌ CCXT не установлен! Установите: pip install ccxt")

_capabilities = check_exchange_capabilities()
_recommendation = get_exchange_recommendation()
logger.info(_recommendation)

if not _capabilities['basic_trading']:
    raise ImportError("❌ Базовые торговые компоненты недоступны!")

# Лог статуса Bybit V5
if BYBIT_V5_AVAILABLE:
    logger.info("🎯 Bybit V5 клиент готов к использованию")
if BYBIT_INTEGRATION_AVAILABLE:
    logger.info("🔗 Bybit интеграция активна")
if BYBIT_V5_AVAILABLE and BYBIT_INTEGRATION_AVAILABLE:
    logger.info("✨ Enhanced Exchange клиент доступен через get_enhanced_exchange_client()")