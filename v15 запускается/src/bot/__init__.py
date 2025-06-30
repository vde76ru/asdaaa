"""
Bot модули для торгового бота - ИСПРАВЛЕННАЯ ВЕРСИЯ
Файл: src/bot/__init__.py

✅ ИСПРАВЛЕНО: Убраны fallback импорты, добавлена четкая диагностика
"""
import logging

logger = logging.getLogger(__name__)

# ✅ ПРЯМОЙ ИМПОРТ ОСНОВНЫХ КОМПОНЕНТОВ с четкой диагностикой
def _import_bot_component(module_name: str, class_name: str, required: bool = True):
    """Импорт bot компонента с понятными сообщениями"""
    try:
        # ✅ ИСПРАВЛЕНО: правильный синтаксис __import__
        module = __import__(f"{__name__}.{module_name}", fromlist=[class_name])
        component = getattr(module, class_name)
        logger.info(f"✅ {class_name} импортирован успешно из {module_name}")
        return component
    except ImportError as e:
        error_msg = f"Модуль 'bot.{module_name}' недоступен: {e}"
        if required:
            logger.critical(f"❌ {error_msg}")
            logger.critical(f"💡 Проверьте файл src/bot/{module_name}.py")
            raise ImportError(f"Критический bot модуль {module_name} не найден. "
                             f"Проверьте файл src/bot/{module_name}.py") from e
        else:
            logger.warning(f"⚠️ {error_msg}")
            return None
    except AttributeError as e:
        error_msg = f"Класс '{class_name}' не найден в модуле 'bot.{module_name}': {e}"
        if required:
            logger.critical(f"❌ {error_msg}")
            raise ImportError(f"Класс {class_name} отсутствует в модуле bot.{module_name}") from e
        else:
            logger.warning(f"⚠️ {error_msg}")
            return None

# ✅ ИМПОРТ ОСНОВНЫХ BOT КОМПОНЕНТОВ
logger.info("🤖 Импортируем основные bot компоненты...")

# BotManager - критический компонент
BotManager = _import_bot_component('manager', 'BotManager', required=True)

# Trader - опциональный компонент для торговли (есть альтернативы)
Trader = _import_bot_component('trader', 'Trader', required=False)

# Если Trader недоступен, используем TradingBotWithRealTrading как альтернативу
if not Trader:
    try:
        from .trading_integration import TradingBotWithRealTrading
        logger.info("✅ Используем TradingBotWithRealTrading как альтернативу Trader")
    except ImportError:
        logger.warning("⚠️ Ни Trader, ни TradingBotWithRealTrading недоступны")
        TradingBotWithRealTrading = None

# ✅ ПРОВЕРКА АЛЬТЕРНАТИВНЫХ ФАЙЛОВ
def _check_alternative_bot_files() -> dict:
    """Проверка наличия альтернативных bot файлов"""
    alternatives = {
        'bot_manager.py': False,
        'manager.py': False,
        'trader.py': False,
        'trading_bot.py': False,
    }
    
    import os
    bot_dir = os.path.dirname(__file__)
    
    for filename in alternatives.keys():
        filepath = os.path.join(bot_dir, filename)
        alternatives[filename] = os.path.exists(filepath)
    
    return alternatives

# ✅ СОЗДАНИЕ АЛИАСОВ ДЛЯ ОБРАТНОЙ СОВМЕСТИМОСТИ
# Проверяем есть ли альтернативный BotManager
alt_files = _check_alternative_bot_files()

if alt_files['bot_manager.py'] and not BotManager:
    logger.info("🔄 Пытаемся импортировать из альтернативного файла bot_manager.py")
    try:
        BotManagerAlt = _import_bot_component('bot_manager', 'BotManager', required=False)
        if BotManagerAlt:
            BotManager = BotManagerAlt
            logger.info("✅ BotManager импортирован из bot_manager.py")
    except:
        pass

# ✅ ФУНКЦИЯ ПРОВЕРКИ BOT ВОЗМОЖНОСТЕЙ
def check_bot_capabilities() -> dict:
    """
    Проверка доступности bot возможностей
    
    Returns:
        dict: Подробный статус bot компонентов
    """
    capabilities = {
        # Основные компоненты
        'bot_manager': BotManager is not None,
        'trader': Trader is not None,
        
        # Альтернативные файлы
        'alternative_files': alt_files,
        
        # Общий статус
        'basic_bot': BotManager is not None,
        'full_trading': any([
            all([BotManager is not None, Trader is not None]),
            'TradingBotWithRealTrading' in locals()
        ])
    }
    
    logger.info("🤖 Доступность Bot возможностей:")
    logger.info(f"   ✅ BotManager: {capabilities['bot_manager']}")
    logger.info(f"   ✅ Trader: {capabilities['trader']}")
    logger.info(f"   🎯 Базовый бот: {capabilities['basic_bot']}")
    logger.info(f"   🚀 Полная торговля: {capabilities['full_trading']}")
    
    # Показываем альтернативные файлы
    logger.info("📁 Альтернативные файлы:")
    for filename, exists in alt_files.items():
        status = "✅" if exists else "❌"
        logger.info(f"   {status} {filename}: {exists}")
    
    return capabilities

def get_bot_recommendation() -> str:
    """Получить рекомендации по bot компонентам"""
    caps = check_bot_capabilities()
    
    if caps['full_trading']:
        return "🎉 Полная торговая система доступна - все bot компоненты активны!"
    elif caps['basic_bot']:
        return "⚡ Базовый бот работает. Проверьте доступность Trader для полной функциональности"
    else:
        return "❌ Bot компоненты недоступны. Проверьте файлы manager.py и trader.py"

def create_bot_manager(**kwargs):
    """
    Фабрика для создания BotManager с проверками
    
    Args:
        **kwargs: Параметры для BotManager
        
    Returns:
        Экземпляр BotManager
    """
    if not BotManager:
        raise RuntimeError("BotManager недоступен - проверьте импорты")
    
    try:
        logger.info("🏭 Создаем экземпляр BotManager...")
        bot_instance = BotManager(**kwargs)
        logger.info("✅ BotManager создан успешно")
        return bot_instance
    except Exception as e:
        logger.error(f"❌ Ошибка создания BotManager: {e}")
        raise

def create_trader(exchange_client, **kwargs):
    """
    Фабрика для создания Trader с проверками
    
    Args:
        exchange_client: Клиент биржи
        **kwargs: Дополнительные параметры
        
    Returns:
        Экземпляр Trader
    """
    if not Trader:
        raise RuntimeError("Trader недоступен - проверьте импорты")
    
    if not exchange_client:
        raise ValueError("exchange_client обязателен для создания Trader")
    
    try:
        logger.info("🏭 Создаем экземпляр Trader...")
        trader_instance = Trader(exchange_client, **kwargs)
        logger.info("✅ Trader создан успешно")
        return trader_instance
    except Exception as e:
        logger.error(f"❌ Ошибка создания Trader: {e}")
        raise

# Экспорт
__all__ = [
    # Основные классы
    'BotManager',
    'Trader',
    
    # Фабричные функции
    'create_bot_manager',
    'create_trader',
    
    # Диагностические функции
    'check_bot_capabilities',
    'get_bot_recommendation'
]

# ✅ АВТОМАТИЧЕСКАЯ ПРОВЕРКА ПРИ ИМПОРТЕ
logger.info("🤖 Инициализация Bot модулей...")
_capabilities = check_bot_capabilities()
_recommendation = get_bot_recommendation()
logger.info(_recommendation)

if not _capabilities['basic_bot']:
    raise ImportError("❌ Базовые bot компоненты недоступны! "
                     "Проверьте наличие файла src/bot/manager.py")

if not _capabilities['full_trading']:
    logger.warning("⚠️ Не все bot компоненты доступны. "
                   "Торговые функции могут быть ограничены.")