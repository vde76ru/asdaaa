"""
ИСПРАВЛЕННЫЙ Analysis модуль для торгового бота
==============================================
Файл: src/analysis/__init__.py

🔧 КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ:
✅ Правильные импорты NewsAnalyzer и SocialAnalyzer
✅ Убраны fallback импорты, добавлена четкая диагностика
✅ Полная совместимость с тестами
"""
import logging

logger = logging.getLogger(__name__)

# ✅ ПРЯМЫЕ ИМПОРТЫ с четкими сообщениями об ошибках
def _import_with_clear_error(module_name: str, class_name: str):
    """Импорт с понятным сообщением об ошибке"""
    try:
        # ✅ ИСПРАВЛЕНО: правильный синтаксис __import__
        module = __import__(f"{__name__}.{module_name}", fromlist=[class_name])
        return getattr(module, class_name)
    except ImportError as e:
        error_msg = f"❌ Модуль '{module_name}' недоступен: {e}"
        logger.error(error_msg)
        raise ImportError(f"Критический модуль analysis.{module_name} не найден. "
                         f"Проверьте файл src/analysis/{module_name}.py") from e
    except AttributeError as e:
        error_msg = f"❌ Класс '{class_name}' не найден в модуле '{module_name}': {e}"
        logger.error(error_msg)
        raise ImportError(f"Класс {class_name} отсутствует в модуле analysis.{module_name}. "
                         f"Проверьте определение класса.") from e

# ✅ ИМПОРТ ОСНОВНОГО КОМПОНЕНТА (КРИТИЧЕСКИЙ)
try:
    MarketAnalyzer = _import_with_clear_error('market_analyzer', 'MarketAnalyzer')
    logger.info("✅ MarketAnalyzer импортирован успешно")
    MARKET_ANALYZER_AVAILABLE = True
except ImportError:
    logger.critical("❌ MarketAnalyzer не может быть импортирован - это критический компонент!")
    raise

# ✅ ИМПОРТ ДОПОЛНИТЕЛЬНЫХ КОМПОНЕНТОВ (НЕ КРИТИЧЕСКИЕ)
# NewsAnalyzer - теперь должен быть доступен
try:
    NewsAnalyzer = _import_with_clear_error('news', 'NewsAnalyzer')
    logger.info("✅ NewsAnalyzer импортирован успешно")
    NEWS_ANALYZER_AVAILABLE = True
except ImportError as e:
    logger.error(f"❌ Класс 'NewsAnalyzer' не найден в модуле 'news': {e}")
    logger.warning("⚠️ NewsAnalyzer недоступен - анализ новостей будет отключен")
    NewsAnalyzer = None
    NEWS_ANALYZER_AVAILABLE = False

# SocialAnalyzer - теперь должен быть доступен  
try:
    SocialAnalyzer = _import_with_clear_error('social', 'SocialAnalyzer')
    logger.info("✅ SocialAnalyzer импортирован успешно")
    SOCIAL_ANALYZER_AVAILABLE = True
except ImportError as e:
    logger.error(f"❌ Класс 'SocialAnalyzer' не найден в модуле 'social': {e}")
    logger.warning("⚠️ SocialAnalyzer недоступен - социальный анализ будет отключен")
    SocialAnalyzer = None
    SOCIAL_ANALYZER_AVAILABLE = False

# ✅ ДОБАВЛЯЕМ ПРОВЕРКУ ДОСТУПНОСТИ ФУНКЦИЙ
def check_analysis_capabilities() -> dict:
    """
    Проверка доступности аналитических возможностей
    
    Returns:
        dict: Статус доступности компонентов
    """
    capabilities = {
        'market_analysis': MARKET_ANALYZER_AVAILABLE,
        'news_analysis': NEWS_ANALYZER_AVAILABLE,
        'social_analysis': SOCIAL_ANALYZER_AVAILABLE,
        'full_functionality': all([
            MARKET_ANALYZER_AVAILABLE,
            NEWS_ANALYZER_AVAILABLE,
            SOCIAL_ANALYZER_AVAILABLE
        ])
    }
    
    logger.info("📊 Доступность аналитических модулей:")
    for capability, available in capabilities.items():
        status = "✅" if available else "❌"
        logger.info(f"   {status} {capability}: {available}")
    
    return capabilities

# ✅ ФУНКЦИЯ ДИАГНОСТИКИ
def diagnose_analysis_issues():
    """Диагностика проблем в analysis модуле"""
    issues = []
    
    if not MARKET_ANALYZER_AVAILABLE:
        issues.append("❌ MarketAnalyzer недоступен - проверьте src/analysis/market_analyzer.py")
    
    if not NEWS_ANALYZER_AVAILABLE:
        issues.append("❌ NewsAnalyzer недоступен - проверьте src/analysis/news/__init__.py")
        
    if not SOCIAL_ANALYZER_AVAILABLE:
        issues.append("❌ SocialAnalyzer недоступен - проверьте src/analysis/social/__init__.py")
    
    if issues:
        logger.error("🚨 ОБНАРУЖЕНЫ ПРОБЛЕМЫ В ANALYSIS МОДУЛЕ:")
        for issue in issues:
            logger.error(f"   {issue}")
    else:
        logger.info("✅ Все аналитические компоненты работают корректно")
    
    return issues

# ✅ ЭКСПОРТ ВСЕХ ДОСТУПНЫХ КОМПОНЕНТОВ
__all__ = [
    'MarketAnalyzer',
    'NewsAnalyzer', 
    'SocialAnalyzer',
    'check_analysis_capabilities',
    'diagnose_analysis_issues'
]

# Создаем алиасы для обратной совместимости
market_analyzer = MarketAnalyzer if MARKET_ANALYZER_AVAILABLE else None
news_analyzer = NewsAnalyzer if NEWS_ANALYZER_AVAILABLE else None
social_analyzer = SocialAnalyzer if SOCIAL_ANALYZER_AVAILABLE else None

# ✅ АВТОМАТИЧЕСКАЯ ПРОВЕРКА ПРИ ИМПОРТЕ
logger.info("🔍 Проверяем доступность аналитических модулей...")
_capabilities = check_analysis_capabilities()

if not _capabilities['market_analysis']:
    raise ImportError("❌ Критический модуль MarketAnalyzer недоступен! "
                     "Система не может работать без базового анализа рынка.")

if not _capabilities['full_functionality']:
    logger.warning("⚠️ Не все аналитические модули доступны. "
                   "Некоторые функции будут ограничены.")
    diagnose_analysis_issues()
else:
    logger.info("🎉 Все аналитические модули успешно загружены!")