"""
Основные компоненты анализа
Файл: src/analysis/core/__init__.py
"""

# Импорт из unified_config корректным способом
try:
    from ...core.unified_config import unified_config
except ImportError:
    try:
        from ...core import unified_config
    except ImportError:
        # Если не получается импортировать - создаем заглушку
        class MockConfig:
            def __getattr__(self, name):
                return None
        unified_config = MockConfig()

from .news_impact_scorer import NewsImpactScorer
from .market_data_aggregator import MarketDataAggregator

__all__ = ['NewsImpactScorer', 'MarketDataAggregator', 'unified_config']