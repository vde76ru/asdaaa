import pandas as pd
import numpy as np
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import EMAIndicator, MACD, ADXIndicator
from ta.volatility import BollingerBands, AverageTrueRange
from ta.volume import OnBalanceVolumeIndicator, VolumeWeightedAveragePrice
import logging
from typing import Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class TradingSignal:
    action: str  # BUY, SELL, WAIT
    confidence: float
    stop_loss: float
    take_profit: float
    reason: str
    risk_reward_ratio: float
    
class MultiIndicatorStrategy:
    """Продвинутая стратегия с множественными индикаторами"""
    
    def __init__(self):
        self.min_confidence = 0.65
        self.risk_reward_min = 2.0  # Минимум 1:2
        
    def analyze(self, df: pd.DataFrame) -> TradingSignal:
        """Комплексный анализ с множественными подтверждениями"""
        if len(df) < 200:  # Нужно больше данных для надежности
            return TradingSignal('WAIT', 0, 0, 0, 'Недостаточно данных', 0)
        
        # Рассчитываем все индикаторы
        indicators = self._calculate_indicators(df)
        
        # Определяем тренд
        trend = self._identify_trend(indicators)
        
        # Проверяем условия входа
        signal = self._check_entry_conditions(indicators, trend, df)
        
        return signal
    
    def _calculate_indicators(self, df: pd.DataFrame) -> Dict:
        """Расчет всех индикаторов"""
        # RSI
        rsi = RSIIndicator(df['close'], window=14)
        df['rsi'] = rsi.rsi()
        
        # MACD
        macd = MACD(df['close'])
        df['macd'] = macd.macd()
        df['macd_signal'] = macd.macd_signal()
        df['macd_diff'] = macd.macd_diff()
        
        # Bollinger Bands
        bb = BollingerBands(df['close'], window=20, window_dev=2)
        df['bb_upper'] = bb.bollinger_hband()
        df['bb_middle'] = bb.bollinger_mavg()
        df['bb_lower'] = bb.bollinger_lband()
        df['bb_width'] = bb.bollinger_wband()
        df['bb_percent'] = bb.bollinger_pband()
        
        # EMA
        df['ema_9'] = EMAIndicator(df['close'], window=9).ema_indicator()
        df['ema_21'] = EMAIndicator(df['close'], window=21).ema_indicator()
        df['ema_50'] = EMAIndicator(df['close'], window=50).ema_indicator()
        df['ema_200'] = EMAIndicator(df['close'], window=200).ema_indicator()
        
        # ADX
        adx = ADXIndicator(df['high'], df['low'], df['close'])
        df['adx'] = adx.adx()
        df['adx_pos'] = adx.adx_pos()
        df['adx_neg'] = adx.adx_neg()
        
        # ATR для stop loss
        atr = AverageTrueRange(df['high'], df['low'], df['close'])
        df['atr'] = atr.average_true_range()
        
        # Volume indicators
        df['obv'] = OnBalanceVolumeIndicator(df['close'], df['volume']).on_balance_volume()
        vwap = VolumeWeightedAveragePrice(df['high'], df['low'], df['close'], df['volume'])
        df['vwap'] = vwap.volume_weighted_average_price()
        
        # Stochastic
        stoch = StochasticOscillator(df['high'], df['low'], df['close'])
        df['stoch_k'] = stoch.stoch()
        df['stoch_d'] = stoch.stoch_signal()
        
        return df
    
    def _identify_trend(self, df: pd.DataFrame) -> str:
        """Определение текущего тренда"""
        last_row = df.iloc[-1]
        
        # EMA alignment
        ema_bullish = (last_row['ema_9'] > last_row['ema_21'] > 
                       last_row['ema_50'] > last_row['ema_200'])
        ema_bearish = (last_row['ema_9'] < last_row['ema_21'] < 
                       last_row['ema_50'] < last_row['ema_200'])
        
        # ADX trend strength
        strong_trend = last_row['adx'] > 25
        
        if ema_bullish and strong_trend:
            return 'BULLISH'
        elif ema_bearish and strong_trend:
            return 'BEARISH'
        else:
            return 'SIDEWAYS'
    
    def _check_entry_conditions(self, df: pd.DataFrame, trend: str, 
                               original_df: pd.DataFrame) -> TradingSignal:
        """Проверка условий для входа в позицию"""
        last_row = df.iloc[-1]
        prev_row = df.iloc[-2]
        
        confidence_scores = []
        reasons = []
        
        # === УСЛОВИЯ ДЛЯ ПОКУПКИ ===
        if trend in ['BULLISH', 'SIDEWAYS']:
            # 1. RSI oversold bounce
            if 30 < last_row['rsi'] < 40 and prev_row['rsi'] < 30:
                confidence_scores.append(0.2)
                reasons.append('RSI отскок от перепроданности')
            
            # 2. MACD bullish crossover
            if (last_row['macd'] > last_row['macd_signal'] and 
                prev_row['macd'] <= prev_row['macd_signal']):
                confidence_scores.append(0.25)
                reasons.append('MACD бычье пересечение')
            
            # 3. Bollinger Bands squeeze and breakout
            if (last_row['bb_width'] < df['bb_width'].rolling(20).mean().iloc[-1] * 0.8 and
                last_row['close'] > last_row['bb_middle']):
                confidence_scores.append(0.15)
                reasons.append('BB сжатие и прорыв')
            
            # 4. Volume confirmation
            avg_volume = df['volume'].rolling(20).mean().iloc[-1]
            if last_row['volume'] > avg_volume * 1.5:
                confidence_scores.append(0.2)
                reasons.append('Объем подтверждает')
            
            # 5. Price above VWAP
            if last_row['close'] > last_row['vwap']:
                confidence_scores.append(0.1)
                reasons.append('Цена выше VWAP')
            
            # 6. Stochastic oversold
            if last_row['stoch_k'] < 20 and last_row['stoch_k'] > last_row['stoch_d']:
                confidence_scores.append(0.1)
                reasons.append('Stochastic oversold crossover')
            
            total_confidence = sum(confidence_scores)
            
            if total_confidence >= self.min_confidence:
                # Расчет Stop Loss и Take Profit
                atr = last_row['atr']
                current_price = last_row['close']
                
                stop_loss = current_price - (2 * atr)  # 2 ATR stop
                take_profit = current_price + (4 * atr)  # 4 ATR target
                
                risk_reward = (take_profit - current_price) / (current_price - stop_loss)
                
                if risk_reward >= self.risk_reward_min:
                    return TradingSignal(
                        action='BUY',
                        confidence=min(total_confidence, 0.95),
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        reason='; '.join(reasons),
                        risk_reward_ratio=risk_reward
                    )
        
        # === УСЛОВИЯ ДЛЯ ПРОДАЖИ ===
        elif trend in ['BEARISH', 'SIDEWAYS']:
            # Аналогичные условия но в обратную сторону
            # (код опущен для краткости, но логика та же)
            pass
        
        return TradingSignal('WAIT', 0, 0, 0, 'Нет сигнала', 0)

class SafeScalpingStrategy:
    """Безопасная скальпинговая стратегия для боковых рынков"""
    
    def __init__(self):
        self.bb_period = 20
        self.bb_std = 2
        self.rsi_period = 7  # Быстрый RSI для скальпинга
        self.min_profit_percent = 0.3  # Минимум 0.3% профита
        
    def analyze(self, df: pd.DataFrame) -> TradingSignal:
        """Анализ для скальпинга в канале"""
        if len(df) < 50:
            return TradingSignal('WAIT', 0, 0, 0, 'Недостаточно данных', 0)
        
        # Bollinger Bands
        bb = BollingerBands(df['close'], window=self.bb_period, window_dev=self.bb_std)
        df['bb_upper'] = bb.bollinger_hband()
        df['bb_lower'] = bb.bollinger_lband()
        df['bb_middle'] = bb.bollinger_mavg()
        df['bb_percent'] = bb.bollinger_pband()
        
        # RSI
        df['rsi'] = RSIIndicator(df['close'], window=self.rsi_period).rsi()
        
        # ATR для волатильности
        atr = AverageTrueRange(df['high'], df['low'], df['close'], window=14)
        df['atr'] = atr.average_true_range()
        
        last_row = df.iloc[-1]
        current_price = last_row['close']
        
        # Проверяем что рынок в канале (низкая волатильность)
        atr_percent = (last_row['atr'] / current_price) * 100
        if atr_percent > 2:  # Слишком волатильно для скальпинга
            return TradingSignal('WAIT', 0, 0, 0, 'Высокая волатильность', 0)
        
        # BUY сигнал - отскок от нижней BB
        if (last_row['bb_percent'] < 0.1 and  # Близко к нижней границе
            last_row['rsi'] < 30 and  # Перепроданность
            df['close'].iloc[-3:].min() > last_row['bb_lower']):  # Не пробили границу
            
            stop_loss = last_row['bb_lower'] * 0.998  # Чуть ниже BB
            take_profit = last_row['bb_middle']  # Цель - средняя линия
            
            potential_profit = ((take_profit - current_price) / current_price) * 100
            
            if potential_profit >= self.min_profit_percent:
                risk_reward = (take_profit - current_price) / (current_price - stop_loss)
                
                return TradingSignal(
                    action='BUY',
                    confidence=0.75,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    reason='Отскок от нижней BB в канале',
                    risk_reward_ratio=risk_reward
                )
        
        return TradingSignal('WAIT', 0, 0, 0, 'Ждем отскока', 0)