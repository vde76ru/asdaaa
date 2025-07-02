"""
Модуль торговых стратегий
========================
Файл: src/strategies/__init__.py

✅ ИСПРАВЛЕННАЯ ВЕРСИЯ с учетом РЕАЛЬНЫХ файлов
"""

import logging
from typing import Dict, Type, Optional, List

logger = logging.getLogger(__name__)

# =================================================================
# БАЗОВЫЕ КОМПОНЕНТЫ
# =================================================================

# Базовая стратегия и типы
try:
    from .base import BaseStrategy
    from ..common.types import UnifiedTradingSignal as TradingSignal
    BASE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"⚠️ Базовые компоненты недоступны: {e}")
    BaseStrategy = None
    TradingSignal = None
    BASE_AVAILABLE = False

# =================================================================
# ОСНОВНЫЕ СТРАТЕГИИ (ВСЕ СУЩЕСТВУЮТ)
# =================================================================

# Multi-Indicator стратегия
try:
    from .multi_indicator import MultiIndicatorStrategy
    MULTI_INDICATOR_AVAILABLE = True
except ImportError:
    logger.warning("⚠️ MultiIndicatorStrategy недоступна")
    MultiIndicatorStrategy = None
    MULTI_INDICATOR_AVAILABLE = False

# Momentum стратегия
try:
    from .momentum import MomentumStrategy
    MOMENTUM_AVAILABLE = True
except ImportError:
    logger.warning("⚠️ MomentumStrategy недоступна")
    MomentumStrategy = None
    MOMENTUM_AVAILABLE = False

# Mean Reversion стратегия
try:
    from .mean_reversion import MeanReversionStrategy
    MEAN_REVERSION_AVAILABLE = True
except ImportError:
    logger.warning("⚠️ MeanReversionStrategy недоступна")
    MeanReversionStrategy = None
    MEAN_REVERSION_AVAILABLE = False

# Scalping стратегия
try:
    from .scalping import ScalpingStrategy
    SCALPING_AVAILABLE = True
except ImportError:
    logger.warning("⚠️ ScalpingStrategy недоступна")
    ScalpingStrategy = None
    SCALPING_AVAILABLE = False

# Breakout стратегия
try:
    from .breakout import BreakoutStrategy
    BREAKOUT_AVAILABLE = True
except ImportError:
    logger.warning("⚠️ BreakoutStrategy недоступна")
    BreakoutStrategy = None
    BREAKOUT_AVAILABLE = False

# Swing стратегия - ФАЙЛ СУЩЕСТВУЕТ!
try:
    from .swing import SwingStrategy
    SWING_AVAILABLE = True
except ImportError:
    logger.warning("⚠️ SwingStrategy недоступна")
    SwingStrategy = None
    SWING_AVAILABLE = False

# =================================================================
# ДОПОЛНИТЕЛЬНЫЕ СТРАТЕГИИ
# =================================================================

# Conservative стратегия
try:
    from .conservative import ConservativeStrategy
    CONSERVATIVE_AVAILABLE = True
except ImportError:
    logger.warning("⚠️ ConservativeStrategy недоступна")
    ConservativeStrategy = None
    CONSERVATIVE_AVAILABLE = False

# Safe Multi-Indicator стратегия
try:
    from .safe_multi_indicator import SafeMultiIndicatorStrategy
    SAFE_MULTI_INDICATOR_AVAILABLE = True
except ImportError:
    logger.warning("⚠️ SafeMultiIndicatorStrategy недоступна")
    SafeMultiIndicatorStrategy = None
    SAFE_MULTI_INDICATOR_AVAILABLE = False

# =================================================================
# СТРАТЕГИИ, КОТОРЫХ НЕТ (заглушки для совместимости)
# =================================================================

# Grid стратегия - НЕ РЕАЛИЗОВАНА
GridStrategy = None
GRID_AVAILABLE = False

# Arbitrage стратегия - НЕ РЕАЛИЗОВАНА
ArbitrageStrategy = None
ARBITRAGE_AVAILABLE = False

# =================================================================
# СЕЛЕКТОРЫ И ФАБРИКИ
# =================================================================

# Auto Strategy Selector
try:
    from .auto_strategy_selector import AutoStrategySelector, auto_strategy_selector
    AUTO_SELECTOR_AVAILABLE = True
except ImportError:
    logger.warning("⚠️ AutoStrategySelector недоступен")
    AutoStrategySelector = None
    auto_strategy_selector = None
    AUTO_SELECTOR_AVAILABLE = False

# Strategy Selector
try:
    from .strategy_selector import StrategySelector, get_strategy_selector
    SELECTOR_AVAILABLE = True
except ImportError:
    logger.warning("⚠️ StrategySelector недоступен")
    StrategySelector = None
    get_strategy_selector = None
    SELECTOR_AVAILABLE = False

# Strategy Factory
try:
    from .factory import StrategyFactory, strategy_factory
    FACTORY_AVAILABLE = True
except ImportError:
    logger.warning("⚠️ StrategyFactory недоступна")
    StrategyFactory = None
    strategy_factory = None
    FACTORY_AVAILABLE = False

# =================================================================
# КАРТА СТРАТЕГИЙ
# =================================================================

# Создаем карту доступных стратегий
STRATEGY_MAP: Dict[str, Optional[Type[BaseStrategy]]] = {}

# Добавляем основные стратегии
if MULTI_INDICATOR_AVAILABLE:
    STRATEGY_MAP['multi_indicator'] = MultiIndicatorStrategy
    
if MOMENTUM_AVAILABLE:
    STRATEGY_MAP['momentum'] = MomentumStrategy
    
if MEAN_REVERSION_AVAILABLE:
    STRATEGY_MAP['mean_reversion'] = MeanReversionStrategy
    
if SCALPING_AVAILABLE:
    STRATEGY_MAP['scalping'] = ScalpingStrategy
    
if BREAKOUT_AVAILABLE:
    STRATEGY_MAP['breakout'] = BreakoutStrategy

if SWING_AVAILABLE:
    STRATEGY_MAP['swing'] = SwingStrategy

# Добавляем дополнительные стратегии
if CONSERVATIVE_AVAILABLE:
    STRATEGY_MAP['conservative'] = ConservativeStrategy
    
if SAFE_MULTI_INDICATOR_AVAILABLE:
    STRATEGY_MAP['safe_multi_indicator'] = SafeMultiIndicatorStrategy

# Добавляем заглушки для несуществующих стратегий
STRATEGY_MAP['grid'] = None  # GridStrategy
STRATEGY_MAP['arbitrage'] = None  # ArbitrageStrategy

# =================================================================
# ФУНКЦИИ-ПОМОЩНИКИ
# =================================================================

def get_available_strategies() -> List[str]:
    """Получить список доступных стратегий"""
    return [name for name, cls in STRATEGY_MAP.items() if cls is not None]

def is_strategy_available(strategy_name: str) -> bool:
    """Проверить доступность стратегии"""
    return STRATEGY_MAP.get(strategy_name) is not None

def create_strategy(strategy_name: str, config: Optional[Dict] = None) -> Optional[BaseStrategy]:
    """
    Создать экземпляр стратегии
    
    Args:
        strategy_name: Название стратегии
        config: Конфигурация стратегии
        
    Returns:
        Экземпляр стратегии или None
    """
    strategy_class = STRATEGY_MAP.get(strategy_name)
    if strategy_class:
        try:
            return strategy_class(strategy_name=strategy_name, config=config)
        except Exception as e:
            logger.error(f"❌ Ошибка создания стратегии {strategy_name}: {e}")
    return None

def get_strategy_info() -> Dict[str, Dict]:
    """Получить информацию о всех стратегиях"""
    info = {}
    for name, cls in STRATEGY_MAP.items():
        if cls:
            info[name] = {
                'available': True,
                'class_name': cls.__name__,
                'has_analyze': hasattr(cls, 'analyze'),
                'has_backtest': hasattr(cls, 'backtest')
            }
        else:
            info[name] = {
                'available': False,
                'class_name': None,
                'has_analyze': False,
                'has_backtest': False
            }
    return info

# =================================================================
# ИНИЦИАЛИЗАЦИЯ И ДИАГНОСТИКА
# =================================================================

def _log_strategy_status():
    """Логирование статуса стратегий"""
    available = get_available_strategies()
    total = len(STRATEGY_MAP)
    
    logger.info("="*60)
    logger.info("📊 СТАТУС ТОРГОВЫХ СТРАТЕГИЙ")
    logger.info(f"✅ Доступно: {len(available)}/{total}")
    logger.info(f"📋 Список: {', '.join(available)}")
    
    # Детальный статус
    for name, cls in STRATEGY_MAP.items():
        if cls:
            logger.info(f"   ✅ {name}: {cls.__name__}")
        else:
            logger.info(f"   ❌ {name}: Не реализована")
    
    # Статус компонентов
    logger.info("🔧 КОМПОНЕНТЫ:")
    logger.info(f"   {'✅' if FACTORY_AVAILABLE else '❌'} StrategyFactory")
    logger.info(f"   {'✅' if AUTO_SELECTOR_AVAILABLE else '❌'} AutoStrategySelector")
    logger.info(f"   {'✅' if SELECTOR_AVAILABLE else '❌'} StrategySelector")
    logger.info("="*60)

# Выполняем диагностику при импорте
_log_strategy_status()

# =================================================================
# ЭКСПОРТЫ
# =================================================================

__all__ = [
    # Базовые компоненты
    'BaseStrategy',
    'TradingSignal',
    
    # Основные стратегии
    'MultiIndicatorStrategy',
    'MomentumStrategy',
    'MeanReversionStrategy',
    'ScalpingStrategy',
    'BreakoutStrategy',
    'SwingStrategy',  # ✅ РАСКОММЕНТИРОВАНО - файл существует!
    
    # Дополнительные стратегии
    'ConservativeStrategy',
    'SafeMultiIndicatorStrategy',
    
    # Несуществующие (для совместимости)
    'GridStrategy',
    'ArbitrageStrategy',
    
    # Селекторы и фабрики
    'AutoStrategySelector',
    'auto_strategy_selector',
    'StrategySelector',
    'get_strategy_selector',
    'StrategyFactory',
    'strategy_factory',
    
    # Карта и функции
    'STRATEGY_MAP',
    'get_available_strategies',
    'is_strategy_available',
    'create_strategy',
    'get_strategy_info'
]

# =================================================================
# ПРОВЕРКА КРИТИЧЕСКИХ КОМПОНЕНТОВ
# =================================================================

if not BASE_AVAILABLE:
    raise ImportError(
        "❌ КРИТИЧЕСКАЯ ОШИБКА: Базовые компоненты стратегий недоступны! "
        "Проверьте файлы base.py и common/types.py"
    )

if len(get_available_strategies()) == 0:
    raise ImportError(
        "❌ КРИТИЧЕСКАЯ ОШИБКА: Ни одна стратегия не доступна! "
        "Проверьте файлы стратегий в директории src/strategies/"
    )

# Минимальная проверка
required_strategies = ['multi_indicator', 'momentum']
missing = [s for s in required_strategies if not is_strategy_available(s)]
if missing:
    logger.error(f"⚠️ Отсутствуют критические стратегии: {missing}")