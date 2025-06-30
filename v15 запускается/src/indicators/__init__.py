"""
Модуль технических индикаторов - УПРОЩЕННАЯ ВЕРСИЯ
"""

from .unified_indicators import (
    UnifiedIndicators, 
    unified_indicators,
    SMA, EMA, RSI, BBANDS, MACD, ATR, STOCH, ADX,
    PLUS_DI, MINUS_DI, ROC, OBV, CCI, WILLR, MFI,
    AROON, BOP, CMO, DX, PPO, TRIX, ULTOSC,
    HT_TRENDLINE, HT_SINE, HT_TRENDMODE,
    CDLDOJI, CDLHAMMER, CDLINVERTEDHAMMER, CDLHANGINGMAN,
    CDLENGULFING, CDLMORNINGSTAR, CDLEVENINGSTAR, CDLSHOOTINGSTAR,
    CDL3WHITESOLDIERS, CDL3BLACKCROWS, CDL3INSIDE,
    AVGPRICE, MEDPRICE, TYPPRICE, WCLPRICE,
    LINEARREG, LINEARREG_ANGLE, LINEARREG_SLOPE,
    STDDEV, TSF, VAR, USE_TALIB, HAS_PANDAS_TA
)

# Алиасы для совместимости
TechnicalIndicators = UnifiedIndicators
indicators = unified_indicators

__all__ = [
    'UnifiedIndicators', 'unified_indicators',
    'TechnicalIndicators', 'indicators',
    'SMA', 'EMA', 'RSI', 'BBANDS', 'MACD', 'ATR', 'STOCH', 'ADX',
    'PLUS_DI', 'MINUS_DI', 'ROC', 'OBV', 'CCI', 'WILLR', 'MFI',
    'AROON', 'BOP', 'CMO', 'DX', 'PPO', 'TRIX', 'ULTOSC',
    'HT_TRENDLINE', 'HT_SINE', 'HT_TRENDMODE',
    'CDLDOJI', 'CDLHAMMER', 'CDLINVERTEDHAMMER', 'CDLHANGINGMAN',
    'CDLENGULFING', 'CDLMORNINGSTAR', 'CDLEVENINGSTAR', 'CDLSHOOTINGSTAR',
    'CDL3WHITESOLDIERS', 'CDL3BLACKCROWS', 'CDL3INSIDE',
    'AVGPRICE', 'MEDPRICE', 'TYPPRICE', 'WCLPRICE',
    'LINEARREG', 'LINEARREG_ANGLE', 'LINEARREG_SLOPE',
    'STDDEV', 'TSF', 'VAR', 'USE_TALIB', 'HAS_PANDAS_TA'
]