"""
Объединенный модуль технических индикаторов
Объединяет функциональность из:
- technical_indicators.py
- ta_wrapper.py

Файл: src/indicators/unified_indicators.py
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, Tuple, List, Union
import logging

# Проверяем наличие библиотек
try:
    import pandas_ta as ta
    HAS_PANDAS_TA = True
except ImportError:
    HAS_PANDAS_TA = False
    print("⚠️ pandas_ta не установлен, используем базовые индикаторы")

# Пытаемся импортировать TA-Lib
try:
    import talib
    USE_TALIB = True
except ImportError:
    USE_TALIB = False
    print("⚠️ TA-Lib не установлен, используем ручные реализации индикаторов")

logger = logging.getLogger(__name__)

# ===== TA-LIB WRAPPER ФУНКЦИИ =====

def SMA(series: Union[pd.Series, np.ndarray], timeperiod: int = 30) -> np.ndarray:
    """Simple Moving Average"""
    if USE_TALIB:
        return talib.SMA(series, timeperiod=timeperiod)
    else:
        return pd.Series(series).rolling(window=timeperiod).mean().values

def EMA(series: Union[pd.Series, np.ndarray], timeperiod: int = 30) -> np.ndarray:
    """Exponential Moving Average"""
    if USE_TALIB:
        return talib.EMA(series, timeperiod=timeperiod)
    else:
        return pd.Series(series).ewm(span=timeperiod, adjust=False).mean().values

def RSI(series: Union[pd.Series, np.ndarray], timeperiod: int = 14) -> np.ndarray:
    """Relative Strength Index"""
    if USE_TALIB:
        return talib.RSI(series, timeperiod=timeperiod)
    else:
        prices = pd.Series(series)
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=timeperiod).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=timeperiod).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.values

def BBANDS(series: Union[pd.Series, np.ndarray], 
           timeperiod: int = 20, 
           nbdevup: int = 2, 
           nbdevdn: int = 2, 
           matype: int = 0) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Bollinger Bands"""
    if USE_TALIB:
        return talib.BBANDS(series, timeperiod=timeperiod, nbdevup=nbdevup, nbdevdn=nbdevdn, matype=matype)
    else:
        prices = pd.Series(series)
        sma = prices.rolling(window=timeperiod).mean()
        std = prices.rolling(window=timeperiod).std()
        
        upper = sma + (std * nbdevup)
        lower = sma - (std * nbdevdn)
        
        return upper.values, sma.values, lower.values

def MACD(series: Union[pd.Series, np.ndarray], 
         fastperiod: int = 12, 
         slowperiod: int = 26, 
         signalperiod: int = 9) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Moving Average Convergence Divergence"""
    if USE_TALIB:
        return talib.MACD(series, fastperiod=fastperiod, slowperiod=slowperiod, signalperiod=signalperiod)
    else:
        prices = pd.Series(series)
        exp1 = prices.ewm(span=fastperiod).mean()
        exp2 = prices.ewm(span=slowperiod).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=signalperiod).mean()
        histogram = macd - signal
        
        return macd.values, signal.values, histogram.values

def ATR(high: Union[pd.Series, np.ndarray], 
        low: Union[pd.Series, np.ndarray], 
        close: Union[pd.Series, np.ndarray], 
        timeperiod: int = 14) -> np.ndarray:
    """Average True Range"""
    if USE_TALIB:
        return talib.ATR(high, low, close, timeperiod=timeperiod)
    else:
        df = pd.DataFrame({'high': high, 'low': low, 'close': close})
        
        # Расчет TR (True Range)
        hl = df['high'] - df['low']
        hc = abs(df['high'] - df['close'].shift())
        lc = abs(df['low'] - df['close'].shift())
        
        tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
        atr = tr.rolling(window=timeperiod).mean()
        
        return atr.values

def STOCH(high: Union[pd.Series, np.ndarray], 
          low: Union[pd.Series, np.ndarray], 
          close: Union[pd.Series, np.ndarray],
          fastk_period: int = 5, 
          slowk_period: int = 3, 
          slowd_period: int = 3) -> Tuple[np.ndarray, np.ndarray]:
    """Stochastic Oscillator"""
    if USE_TALIB:
        return talib.STOCH(high, low, close, fastk_period=fastk_period, slowk_period=slowk_period, slowd_period=slowd_period)
    else:
        df = pd.DataFrame({'high': high, 'low': low, 'close': close})
        
        lowest_low = df['low'].rolling(window=fastk_period).min()
        highest_high = df['high'].rolling(window=fastk_period).max()
        
        k_percent = 100 * ((df['close'] - lowest_low) / (highest_high - lowest_low))
        k_percent = k_percent.rolling(window=slowk_period).mean()
        d_percent = k_percent.rolling(window=slowd_period).mean()
        
        return k_percent.values, d_percent.values

def ADX(high: Union[pd.Series, np.ndarray], 
        low: Union[pd.Series, np.ndarray], 
        close: Union[pd.Series, np.ndarray], 
        timeperiod: int = 14) -> np.ndarray:
    """Average Directional Movement Index"""
    if USE_TALIB:
        return talib.ADX(high, low, close, timeperiod=timeperiod)
    else:
        df = pd.DataFrame({'high': high, 'low': low, 'close': close})
        
        # Простая реализация ADX
        tr = np.maximum(df['high'] - df['low'], 
                       np.maximum(abs(df['high'] - df['close'].shift()), 
                                abs(df['low'] - df['close'].shift())))
        
        dm_plus = np.where((df['high'] - df['high'].shift()) > (df['low'].shift() - df['low']),
                          np.maximum(df['high'] - df['high'].shift(), 0), 0)
        dm_minus = np.where((df['low'].shift() - df['low']) > (df['high'] - df['high'].shift()),
                           np.maximum(df['low'].shift() - df['low'], 0), 0)
        
        atr = pd.Series(tr).rolling(window=timeperiod).mean()
        di_plus = 100 * (pd.Series(dm_plus).rolling(window=timeperiod).mean() / atr)
        di_minus = 100 * (pd.Series(dm_minus).rolling(window=timeperiod).mean() / atr)
        
        dx = 100 * abs(di_plus - di_minus) / (di_plus + di_minus)
        adx = dx.rolling(window=timeperiod).mean()
        
        return adx.values

def PLUS_DI(high: Union[pd.Series, np.ndarray], 
           low: Union[pd.Series, np.ndarray], 
           close: Union[pd.Series, np.ndarray], 
           timeperiod: int = 14) -> np.ndarray:
    """Plus Directional Indicator"""
    if USE_TALIB:
        return talib.PLUS_DI(high, low, close, timeperiod=timeperiod)
    else:
        return np.full_like(close, 50.0)  # Fallback значение

def MINUS_DI(high: Union[pd.Series, np.ndarray], 
            low: Union[pd.Series, np.ndarray], 
            close: Union[pd.Series, np.ndarray], 
            timeperiod: int = 14) -> np.ndarray:
    """Minus Directional Indicator"""
    if USE_TALIB:
        return talib.MINUS_DI(high, low, close, timeperiod=timeperiod)
    else:
        return np.full_like(close, 50.0)  # Fallback значение

def ROC(series: Union[pd.Series, np.ndarray], timeperiod: int = 10) -> np.ndarray:
    """Rate of Change"""
    if USE_TALIB:
        return talib.ROC(series, timeperiod=timeperiod)
    else:
        prices = pd.Series(series)
        roc = prices.pct_change(periods=timeperiod) * 100
        return roc.values

def OBV(close: Union[pd.Series, np.ndarray], volume: Union[pd.Series, np.ndarray]) -> np.ndarray:
    """On Balance Volume"""
    if USE_TALIB:
        return talib.OBV(close, volume)
    else:
        df = pd.DataFrame({'close': close, 'volume': volume})
        obv = []
        obv_value = 0
        
        for i in range(len(df)):
            if i == 0:
                obv_value = df['volume'].iloc[i]
            else:
                if df['close'].iloc[i] > df['close'].iloc[i-1]:
                    obv_value += df['volume'].iloc[i]
                elif df['close'].iloc[i] < df['close'].iloc[i-1]:
                    obv_value -= df['volume'].iloc[i]
            obv.append(obv_value)
        
        return np.array(obv)

def CCI(high: Union[pd.Series, np.ndarray], 
        low: Union[pd.Series, np.ndarray], 
        close: Union[pd.Series, np.ndarray], 
        timeperiod: int = 14) -> np.ndarray:
    """Commodity Channel Index"""
    if USE_TALIB:
        return talib.CCI(high, low, close, timeperiod=timeperiod)
    else:
        typical_price = (high + low + close) / 3
        sma = pd.Series(typical_price).rolling(window=timeperiod).mean()
        mad = pd.Series(typical_price).rolling(window=timeperiod).apply(lambda x: np.mean(np.abs(x - x.mean())))
        cci = (typical_price - sma) / (0.015 * mad)
        return cci.values

def WILLR(high: Union[pd.Series, np.ndarray], 
          low: Union[pd.Series, np.ndarray], 
          close: Union[pd.Series, np.ndarray], 
          timeperiod: int = 14) -> np.ndarray:
    """Williams %R"""
    if USE_TALIB:
        return talib.WILLR(high, low, close, timeperiod=timeperiod)
    else:
        df = pd.DataFrame({'high': high, 'low': low, 'close': close})
        highest_high = df['high'].rolling(window=timeperiod).max()
        lowest_low = df['low'].rolling(window=timeperiod).min()
        
        willr = -100 * ((highest_high - df['close']) / (highest_high - lowest_low))
        return willr.values

def MFI(high: Union[pd.Series, np.ndarray], 
        low: Union[pd.Series, np.ndarray], 
        close: Union[pd.Series, np.ndarray], 
        volume: Union[pd.Series, np.ndarray], 
        timeperiod: int = 14) -> np.ndarray:
    """Money Flow Index"""
    if USE_TALIB:
        return talib.MFI(high, low, close, volume, timeperiod=timeperiod)
    else:
        df = pd.DataFrame({'high': high, 'low': low, 'close': close, 'volume': volume})
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        money_flow = typical_price * df['volume']
        
        positive_flow = money_flow.where(typical_price > typical_price.shift(), 0)
        negative_flow = money_flow.where(typical_price < typical_price.shift(), 0)
        
        positive_flow_sum = positive_flow.rolling(window=timeperiod).sum()
        negative_flow_sum = negative_flow.rolling(window=timeperiod).sum()
        
        money_ratio = positive_flow_sum / negative_flow_sum
        mfi = 100 - (100 / (1 + money_ratio))
        
        return mfi.values

def AROON(high: Union[pd.Series, np.ndarray], 
          low: Union[pd.Series, np.ndarray], 
          timeperiod: int = 14) -> Tuple[np.ndarray, np.ndarray]:
    """Aroon Oscillator"""
    if USE_TALIB:
        return talib.AROON(high, low, timeperiod=timeperiod)
    else:
        return (np.full_like(high, 50.0), np.full_like(high, 50.0))

# Дополнительные функции
def BOP(open: Union[pd.Series, np.ndarray], 
        high: Union[pd.Series, np.ndarray], 
        low: Union[pd.Series, np.ndarray], 
        close: Union[pd.Series, np.ndarray]) -> np.ndarray:
    """Balance Of Power"""
    if USE_TALIB:
        return talib.BOP(open, high, low, close)
    else:
        return np.zeros_like(close)

def CMO(series: Union[pd.Series, np.ndarray], timeperiod: int = 14) -> np.ndarray:
    """Chande Momentum Oscillator"""
    if USE_TALIB:
        return talib.CMO(series, timeperiod=timeperiod)
    else:
        return np.zeros_like(series)

def DX(high: Union[pd.Series, np.ndarray], 
       low: Union[pd.Series, np.ndarray], 
       close: Union[pd.Series, np.ndarray], 
       timeperiod: int = 14) -> np.ndarray:
    """Directional Movement Index"""
    if USE_TALIB:
        return talib.DX(high, low, close, timeperiod=timeperiod)
    else:
        return np.full_like(close, 25.0)

def PPO(series: Union[pd.Series, np.ndarray], 
        fastperiod: int = 12, 
        slowperiod: int = 26, 
        matype: int = 0) -> np.ndarray:
    """Percentage Price Oscillator"""
    if USE_TALIB:
        return talib.PPO(series, fastperiod=fastperiod, slowperiod=slowperiod, matype=matype)
    else:
        return np.zeros_like(series)

def TRIX(series: Union[pd.Series, np.ndarray], timeperiod: int = 30) -> np.ndarray:
    """1-day Rate-Of-Change (ROC) of a Triple Smooth EMA"""
    if USE_TALIB:
        return talib.TRIX(series, timeperiod=timeperiod)
    else:
        return np.zeros_like(series)

def ULTOSC(high: Union[pd.Series, np.ndarray], 
           low: Union[pd.Series, np.ndarray], 
           close: Union[pd.Series, np.ndarray], 
           timeperiod1: int = 7, 
           timeperiod2: int = 14, 
           timeperiod3: int = 28) -> np.ndarray:
    """Ultimate Oscillator"""
    if USE_TALIB:
        return talib.ULTOSC(high, low, close, timeperiod1=timeperiod1, timeperiod2=timeperiod2, timeperiod3=timeperiod3)
    else:
        return np.full_like(close, 50.0)

# Hilbert Transform функции
def HT_TRENDLINE(series: Union[pd.Series, np.ndarray]) -> np.ndarray:
    """Hilbert Transform - Instantaneous Trendline"""
    if USE_TALIB:
        return talib.HT_TRENDLINE(series)
    else:
        return pd.Series(series).rolling(window=20).mean().values

def HT_SINE(series: Union[pd.Series, np.ndarray]) -> Tuple[np.ndarray, np.ndarray]:
    """Hilbert Transform - SineWave"""
    if USE_TALIB:
        return talib.HT_SINE(series)
    else:
        return (np.zeros_like(series), np.zeros_like(series))

def HT_TRENDMODE(series: Union[pd.Series, np.ndarray]) -> np.ndarray:
    """Hilbert Transform - Trend vs Cycle Mode"""
    if USE_TALIB:
        return talib.HT_TRENDMODE(series)
    else:
        return np.zeros_like(series, dtype=int)

# Price Transform функции
def AVGPRICE(open: Union[pd.Series, np.ndarray], 
             high: Union[pd.Series, np.ndarray], 
             low: Union[pd.Series, np.ndarray], 
             close: Union[pd.Series, np.ndarray]) -> np.ndarray:
    """Average Price"""
    if USE_TALIB:
        return talib.AVGPRICE(open, high, low, close)
    else:
        return (open + high + low + close) / 4

def MEDPRICE(high: Union[pd.Series, np.ndarray], 
             low: Union[pd.Series, np.ndarray]) -> np.ndarray:
    """Median Price"""
    if USE_TALIB:
        return talib.MEDPRICE(high, low)
    else:
        return (high + low) / 2

def TYPPRICE(high: Union[pd.Series, np.ndarray], 
             low: Union[pd.Series, np.ndarray], 
             close: Union[pd.Series, np.ndarray]) -> np.ndarray:
    """Typical Price"""
    if USE_TALIB:
        return talib.TYPPRICE(high, low, close)
    else:
        return (high + low + close) / 3

def WCLPRICE(high: Union[pd.Series, np.ndarray], 
             low: Union[pd.Series, np.ndarray], 
             close: Union[pd.Series, np.ndarray]) -> np.ndarray:
    """Weighted Close Price"""
    if USE_TALIB:
        return talib.WCLPRICE(high, low, close)
    else:
        return (high + low + close * 2) / 4

# Статистические функции
def LINEARREG(series: Union[pd.Series, np.ndarray], timeperiod: int = 14) -> np.ndarray:
    """Linear Regression"""
    if USE_TALIB:
        return talib.LINEARREG(series, timeperiod=timeperiod)
    else:
        return pd.Series(series).rolling(window=timeperiod).mean().values

def LINEARREG_ANGLE(series: Union[pd.Series, np.ndarray], timeperiod: int = 14) -> np.ndarray:
    """Linear Regression Angle"""
    if USE_TALIB:
        return talib.LINEARREG_ANGLE(series, timeperiod=timeperiod)
    else:
        return np.zeros_like(series)

def LINEARREG_SLOPE(series: Union[pd.Series, np.ndarray], timeperiod: int = 14) -> np.ndarray:
    """Linear Regression Slope"""
    if USE_TALIB:
        return talib.LINEARREG_SLOPE(series, timeperiod=timeperiod)
    else:
        return np.zeros_like(series)

def STDDEV(series: Union[pd.Series, np.ndarray], timeperiod: int = 5, nbdev: int = 1) -> np.ndarray:
    """Standard Deviation"""
    if USE_TALIB:
        return talib.STDDEV(series, timeperiod=timeperiod, nbdev=nbdev)
    else:
        return pd.Series(series).rolling(window=timeperiod).std().values

def TSF(series: Union[pd.Series, np.ndarray], timeperiod: int = 14) -> np.ndarray:
    """Time Series Forecast"""
    if USE_TALIB:
        return talib.TSF(series, timeperiod=timeperiod)
    else:
        return pd.Series(series).rolling(window=timeperiod).mean().values

def VAR(series: Union[pd.Series, np.ndarray], timeperiod: int = 5, nbdev: int = 1) -> np.ndarray:
    """Variance"""
    if USE_TALIB:
        return talib.VAR(series, timeperiod=timeperiod, nbdev=nbdev)
    else:
        return pd.Series(series).rolling(window=timeperiod).var().values

# Candlestick Pattern Recognition функции (базовые)
def CDLDOJI(open: Union[pd.Series, np.ndarray], 
            high: Union[pd.Series, np.ndarray], 
            low: Union[pd.Series, np.ndarray], 
            close: Union[pd.Series, np.ndarray]) -> np.ndarray:
    """Doji"""
    if USE_TALIB:
        return talib.CDLDOJI(open, high, low, close)
    else:
        # Простая проверка на doji (open ≈ close)
        return np.where(abs(close - open) / ((high - low) + 1e-10) < 0.1, 100, 0)

def CDLHAMMER(open: Union[pd.Series, np.ndarray], 
              high: Union[pd.Series, np.ndarray], 
              low: Union[pd.Series, np.ndarray], 
              close: Union[pd.Series, np.ndarray]) -> np.ndarray:
    """Hammer"""
    if USE_TALIB:
        return talib.CDLHAMMER(open, high, low, close)
    else:
        return np.zeros_like(close, dtype=int)

def CDLINVERTEDHAMMER(open: Union[pd.Series, np.ndarray], 
                      high: Union[pd.Series, np.ndarray], 
                      low: Union[pd.Series, np.ndarray], 
                      close: Union[pd.Series, np.ndarray]) -> np.ndarray:
    """Inverted Hammer"""
    if USE_TALIB:
        return talib.CDLINVERTEDHAMMER(open, high, low, close)
    else:
        return np.zeros_like(close, dtype=int)

def CDLHANGINGMAN(open: Union[pd.Series, np.ndarray], 
                  high: Union[pd.Series, np.ndarray], 
                  low: Union[pd.Series, np.ndarray], 
                  close: Union[pd.Series, np.ndarray]) -> np.ndarray:
    """Hanging Man"""
    if USE_TALIB:
        return talib.CDLHANGINGMAN(open, high, low, close)
    else:
        return np.zeros_like(close, dtype=int)

def CDLENGULFING(open: Union[pd.Series, np.ndarray], 
                 high: Union[pd.Series, np.ndarray], 
                 low: Union[pd.Series, np.ndarray], 
                 close: Union[pd.Series, np.ndarray]) -> np.ndarray:
    """Engulfing Pattern"""
    if USE_TALIB:
        return talib.CDLENGULFING(open, high, low, close)
    else:
        return np.zeros_like(close, dtype=int)

def CDLMORNINGSTAR(open: Union[pd.Series, np.ndarray], 
                   high: Union[pd.Series, np.ndarray], 
                   low: Union[pd.Series, np.ndarray], 
                   close: Union[pd.Series, np.ndarray], 
                   penetration: float = 0.3) -> np.ndarray:
    """Morning Star"""
    if USE_TALIB:
        return talib.CDLMORNINGSTAR(open, high, low, close, penetration=penetration)
    else:
        return np.zeros_like(close, dtype=int)

def CDLEVENINGSTAR(open: Union[pd.Series, np.ndarray], 
                   high: Union[pd.Series, np.ndarray], 
                   low: Union[pd.Series, np.ndarray], 
                   close: Union[pd.Series, np.ndarray], 
                   penetration: float = 0.3) -> np.ndarray:
    """Evening Star"""
    if USE_TALIB:
        return talib.CDLEVENINGSTAR(open, high, low, close, penetration=penetration)
    else:
        return np.zeros_like(close, dtype=int)

def CDLSHOOTINGSTAR(open: Union[pd.Series, np.ndarray], 
                    high: Union[pd.Series, np.ndarray], 
                    low: Union[pd.Series, np.ndarray], 
                    close: Union[pd.Series, np.ndarray]) -> np.ndarray:
    """Shooting Star"""
    if USE_TALIB:
        return talib.CDLSHOOTINGSTAR(open, high, low, close)
    else:
        return np.zeros_like(close, dtype=int)

def CDL3WHITESOLDIERS(open: Union[pd.Series, np.ndarray], 
                      high: Union[pd.Series, np.ndarray], 
                      low: Union[pd.Series, np.ndarray], 
                      close: Union[pd.Series, np.ndarray]) -> np.ndarray:
    """Three Advancing White Soldiers"""
    if USE_TALIB:
        return talib.CDL3WHITESOLDIERS(open, high, low, close)
    else:
        return np.zeros_like(close, dtype=int)

def CDL3BLACKCROWS(open: Union[pd.Series, np.ndarray], 
                   high: Union[pd.Series, np.ndarray], 
                   low: Union[pd.Series, np.ndarray], 
                   close: Union[pd.Series, np.ndarray]) -> np.ndarray:
    """Three Black Crows"""
    if USE_TALIB:
        return talib.CDL3BLACKCROWS(open, high, low, close)
    else:
        return np.zeros_like(close, dtype=int)

def CDL3INSIDE(open: Union[pd.Series, np.ndarray], 
               high: Union[pd.Series, np.ndarray], 
               low: Union[pd.Series, np.ndarray], 
               close: Union[pd.Series, np.ndarray]) -> np.ndarray:
    """Three Inside Up/Down"""
    if USE_TALIB:
        return talib.CDL3INSIDE(open, high, low, close)
    else:
        return np.zeros_like(close, dtype=int)

# ===== ОСНОВНОЙ КЛАСС ТЕХНИЧЕСКИХ ИНДИКАТОРОВ =====

class UnifiedIndicators:
    """
    ✅ ИСПРАВЛЕНО: Singleton паттерн + все необходимые методы
    """
    _instance = None
    _initialized = False
    
    def __new__(cls):
        """Singleton паттерн"""
        if cls._instance is None:
            cls._instance = super(UnifiedIndicators, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Инициализация только один раз"""
        if UnifiedIndicators._initialized:
            return
        UnifiedIndicators._initialized = True
        
        # ✅ ДОБАВЛЕНЫ НЕДОСТАЮЩИЕ МЕТОДЫ ПРОВЕРКИ
        self.pandas_ta_available = self._check_pandas_ta()
        self.talib_available = self._check_talib()
        
        if not self.talib_available:
            print("⚠️ TA-Lib не установлен, используем ручные реализации индикаторов")
        
        from ..logging.smart_logger import SmartLogger
        self.logger = SmartLogger(__name__)
        self.logger.info(f"✅ UnifiedIndicators инициализирован (pandas_ta: {self.pandas_ta_available}, TA-Lib: {self.talib_available})")
    
    def _check_pandas_ta(self) -> bool:
        """Проверка доступности pandas_ta"""
        try:
            import pandas_ta as ta
            return True
        except ImportError:
            return False
    
    def _check_talib(self) -> bool:
        """Проверка доступности TA-Lib"""
        try:
            import talib
            return True
        except ImportError:
            return False
    
    # === RSI ===
    def rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Relative Strength Index"""
        if self.talib_available:
            import talib
            return pd.Series(talib.RSI(prices.values, timeperiod=period), index=prices.index)
        elif self.pandas_ta_available:
            import pandas_ta as ta
            return ta.rsi(prices, length=period)
        else:
            return self._manual_rsi(prices, period)
    
    def _manual_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Ручная реализация RSI"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    # === MACD ===
    def macd(self, prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, pd.Series]:
        """MACD indicator"""
        if self.talib_available:
            import talib
            macd_line, signal_line, histogram = talib.MACD(prices.values, fastperiod=fast, slowperiod=slow, signalperiod=signal)
            return {
                'macd': pd.Series(macd_line, index=prices.index),
                'signal': pd.Series(signal_line, index=prices.index),
                'histogram': pd.Series(histogram, index=prices.index)
            }
        elif self.pandas_ta_available:
            import pandas_ta as ta
            macd_df = ta.macd(prices, fast=fast, slow=slow, signal=signal)
            return {
                'macd': macd_df[f'MACD_{fast}_{slow}_{signal}'],
                'signal': macd_df[f'MACDs_{fast}_{slow}_{signal}'],
                'histogram': macd_df[f'MACDh_{fast}_{slow}_{signal}']
            }
        else:
            return self._manual_macd(prices, fast, slow, signal)
    
    def _manual_macd(self, prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, pd.Series]:
        """Ручная реализация MACD"""
        ema_fast = prices.ewm(span=fast).mean()
        ema_slow = prices.ewm(span=slow).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal).mean()
        histogram = macd_line - signal_line
        
        return {
            'macd': macd_line,
            'signal': signal_line,
            'histogram': histogram
        }
    
    # === Bollinger Bands ===
    def bollinger_bands(self, prices: pd.Series, period: int = 20, std_dev: float = 2) -> Dict[str, pd.Series]:
        """Bollinger Bands"""
        if self.talib_available:
            import talib
            upper, middle, lower = talib.BBANDS(prices.values, timeperiod=period, nbdevup=std_dev, nbdevdn=std_dev)
            return {
                'upper': pd.Series(upper, index=prices.index),
                'middle': pd.Series(middle, index=prices.index),
                'lower': pd.Series(lower, index=prices.index)
            }
        elif self.pandas_ta_available:
            import pandas_ta as ta
            bb = ta.bbands(prices, length=period, std=std_dev)
            return {
                'upper': bb[f'BBU_{period}_{std_dev}'],
                'middle': bb[f'BBM_{period}_{std_dev}'],
                'lower': bb[f'BBL_{period}_{std_dev}']
            }
        else:
            return self._manual_bollinger_bands(prices, period, std_dev)
    
    def _manual_bollinger_bands(self, prices: pd.Series, period: int = 20, std_dev: float = 2) -> Dict[str, pd.Series]:
        """Ручная реализация Bollinger Bands"""
        sma = prices.rolling(window=period).mean()
        std = prices.rolling(window=period).std()
        
        return {
            'upper': sma + (std * std_dev),
            'middle': sma,
            'lower': sma - (std * std_dev)
        }
    
    # === Stochastic ===
    def stochastic(self, high: pd.Series, low: pd.Series, close: pd.Series, k_period: int = 14, d_period: int = 3) -> Dict[str, pd.Series]:
        """Stochastic Oscillator"""
        if self.talib_available:
            import talib
            k, d = talib.STOCH(high.values, low.values, close.values, 
                              fastk_period=k_period, slowk_period=d_period, slowd_period=d_period)
            return {
                'k': pd.Series(k, index=close.index),
                'd': pd.Series(d, index=close.index)
            }
        elif self.pandas_ta_available:
            import pandas_ta as ta
            stoch = ta.stoch(high, low, close, k=k_period, d=d_period)
            return {
                'k': stoch[f'STOCHk_{k_period}_{d_period}_{d_period}'],
                'd': stoch[f'STOCHd_{k_period}_{d_period}_{d_period}']
            }
        else:
            return self._manual_stochastic(high, low, close, k_period, d_period)
    
    def _manual_stochastic(self, high: pd.Series, low: pd.Series, close: pd.Series, k_period: int = 14, d_period: int = 3) -> Dict[str, pd.Series]:
        """Ручная реализация Stochastic"""
        lowest_low = low.rolling(window=k_period).min()
        highest_high = high.rolling(window=k_period).max()
        
        k_percent = 100 * ((close - lowest_low) / (highest_high - lowest_low))
        d_percent = k_percent.rolling(window=d_period).mean()
        
        return {
            'k': k_percent,
            'd': d_percent
        }
    
    # === ATR ===
    def atr(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """Average True Range"""
        if self.talib_available:
            import talib
            return pd.Series(talib.ATR(high.values, low.values, close.values, timeperiod=period), index=close.index)
        elif self.pandas_ta_available:
            import pandas_ta as ta
            return ta.atr(high, low, close, length=period)
        else:
            return self._manual_atr(high, low, close, period)
    
    def _manual_atr(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """Ручная реализация ATR"""
        prev_close = close.shift(1)
        
        tr1 = high - low
        tr2 = abs(high - prev_close)
        tr3 = abs(low - prev_close)
        
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return true_range.rolling(window=period).mean()
    
    # === EMA ===
    def ema(self, prices: pd.Series, period: int = 20) -> pd.Series:
        """Exponential Moving Average"""
        if self.talib_available:
            import talib
            return pd.Series(talib.EMA(prices.values, timeperiod=period), index=prices.index)
        elif self.pandas_ta_available:
            import pandas_ta as ta
            return ta.ema(prices, length=period)
        else:
            return prices.ewm(span=period).mean()
    
    # === SMA ===
    def sma(self, prices: pd.Series, period: int = 20) -> pd.Series:
        """Simple Moving Average"""
        if self.talib_available:
            import talib
            return pd.Series(talib.SMA(prices.values, timeperiod=period), index=prices.index)
        elif self.pandas_ta_available:
            import pandas_ta as ta
            return ta.sma(prices, length=period)
        else:
            return prices.rolling(window=period).mean()
    
    # === Volume Profile ===
    def vwap(self, high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series) -> pd.Series:
        """Volume Weighted Average Price"""
        if self.pandas_ta_available:
            import pandas_ta as ta
            return ta.vwap(high, low, close, volume)
        else:
            return self._manual_vwap(high, low, close, volume)
    
    def _manual_vwap(self, high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series) -> pd.Series:
        """Ручная реализация VWAP"""
        typical_price = (high + low + close) / 3
        return (typical_price * volume).cumsum() / volume.cumsum()
    
    # === Utility Methods ===
    def get_available_indicators(self) -> List[str]:
        """Получить список доступных индикаторов"""
        return [
            'rsi', 'macd', 'bollinger_bands', 'stochastic', 
            'atr', 'ema', 'sma', 'vwap'
        ]
    
    def get_info(self) -> Dict[str, Any]:
        """Информация о системе индикаторов"""
        return {
            'pandas_ta_available': self.pandas_ta_available,
            'talib_available': self.talib_available,
            'available_indicators': self.get_available_indicators(),
            'instance_id': id(self),
            'initialized': UnifiedIndicators._initialized
        }



# Создаем глобальный экземпляр для удобства
unified_indicators = UnifiedIndicators()

# Экспорт всех функций
__all__ = [
    # Основной класс
    'UnifiedIndicators', 'unified_indicators',
    
    # TA-Lib wrapper функции
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

# Алиасы для обратной совместимости
TechnicalIndicators = UnifiedIndicators
indicators = unified_indicators