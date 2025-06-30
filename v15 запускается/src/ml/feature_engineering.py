"""
Алиас для обратной совместимости
Файл: src/ml/feature_engineering.py

Этот файл перенаправляет импорты в правильное место
"""

# ✅ Перенаправляем все импорты в правильный модуль
from .features.feature_engineering import *

# Для явного указания что экспортируется
from .features.feature_engineering import (
    FeatureEngineer,
    FeatureConfig,
    calculate_rsi,
    calculate_macd,
    calculate_bollinger_bands,
    calculate_atr,
    calculate_obv,
    calculate_stochastic
)

# Алиас для обратной совместимости
FeatureEngineering = FeatureEngineer

__all__ = [
    'FeatureEngineer',
    'FeatureEngineering',  # Алиас
    'FeatureConfig',
    'calculate_rsi',
    'calculate_macd', 
    'calculate_bollinger_bands',
    'calculate_atr',
    'calculate_obv',
    'calculate_stochastic'
]