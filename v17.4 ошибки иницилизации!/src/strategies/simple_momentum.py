import pandas as pd
import numpy as np
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

from ..common.types import UnifiedTradingSignal as TradingSignal

class SimpleMomentumStrategy:
    """Простая momentum стратегия с защитой от шума"""
    
    def __init__(self):
        self.rsi_period = 14
        self.ema_fast = 9
        self.ema_slow = 21
        self.rsi_oversold = 30
        self.rsi_overbought = 70
        
    def analyze(self, df: pd.DataFrame) -> TradingSignal:
        """Анализ данных и генерация сигнала"""
        if len(df) < 50:
            return TradingSignal('WAIT', 0, 0, 0, 'Недостаточно данных', 0)
        
        try:
            # Расчет индикаторов
            df['rsi'] = RSIIndicator(df['close'], window=self.rsi_period).rsi()
            df['ema_fast'] = EMAIndicator(df['close'], window=self.ema_fast).ema_indicator()
            df['ema_slow'] = EMAIndicator(df['close'], window=self.ema_slow).ema_indicator()
            
            # ATR для stop loss
            df['high_low'] = df['high'] - df['low']
            df['high_close'] = abs(df['high'] - df['close'].shift())
            df['low_close'] = abs(df['low'] - df['close'].shift())
            df['true_range'] = df[['high_low', 'high_close', 'low_close']].max(axis=1)
            df['atr'] = df['true_range'].rolling(window=14).mean()
            
            # Последние значения
            current_rsi = df['rsi'].iloc[-1]
            current_ema_fast = df['ema_fast'].iloc[-1]
            current_ema_slow = df['ema_slow'].iloc[-1]
            current_volume = df['volume'].iloc[-1]
            avg_volume = df['volume'].rolling(20).mean().iloc[-1]
            current_price = df['close'].iloc[-1]
            current_atr = df['atr'].iloc[-1]
            
            signal = 'WAIT'
            confidence = 0.0
            stop_loss = 0
            take_profit = 0
            reason = 'Нет условий для входа'
            
            # Условия для покупки
            if (current_ema_fast > current_ema_slow and
                self.rsi_oversold < current_rsi < 50 and
                current_volume > avg_volume * 1.2):
                
                signal = 'BUY'
                confidence = min(0.8, (current_volume / avg_volume) * 0.4 + 0.4)
                stop_loss = current_price - (2 * current_atr)
                take_profit = current_price + (3 * current_atr)
                reason = f'EMA пересечение вверх, RSI={current_rsi:.1f}, объем выше среднего'
                
            # Условия для продажи
            elif (current_ema_fast < current_ema_slow and
                  50 < current_rsi < self.rsi_overbought and
                  current_volume > avg_volume):
                
                signal = 'SELL'
                confidence = min(0.8, (current_volume / avg_volume) * 0.4 + 0.4)
                stop_loss = current_price + (2 * current_atr)
                take_profit = current_price - (3 * current_atr)
                reason = f'EMA пересечение вниз, RSI={current_rsi:.1f}, объем подтверждает'
            
            # Расчет risk/reward
            risk_reward_ratio = 0
            if signal != 'WAIT' and stop_loss != 0:
                risk = abs(current_price - stop_loss)
                reward = abs(take_profit - current_price)
                if risk > 0:
                    risk_reward_ratio = reward / risk
            
            return TradingSignal(
                action=signal,
                confidence=confidence,
                stop_loss=stop_loss,
                take_profit=take_profit,
                reason=reason,
                risk_reward_ratio=risk_reward_ratio
            )
            
        except Exception as e:
            logger.error(f"Ошибка в стратегии: {e}")
            return TradingSignal('WAIT', 0, 0, 0, f'Ошибка анализа: {e}', 0)