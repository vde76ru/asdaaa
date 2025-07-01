"""
Безопасная версия мульти-индикаторной стратегии
Путь: src/strategies/safe_multi_indicator.py
"""
import pandas as pd
import numpy as np
import ta
from typing import Dict, Any
import logging
import warnings

from .base import BaseStrategy, TradingSignal

# Подавляем предупреждения NumPy
warnings.filterwarnings('ignore', category=RuntimeWarning)

logger = logging.getLogger(__name__)

class SafeMultiIndicatorStrategy(BaseStrategy):
    """
    Безопасная мульти-индикаторная стратегия с защитой от ошибок
    """
    
    def __init__(self):
        super().__init__("safe_multi_indicator")
        self.min_confidence = 0.65
        self.min_indicators_confirm = 3
    
    async def analyze(self, df: pd.DataFrame, symbol: str) -> TradingSignal:
        """Безопасный анализ с обработкой всех исключений"""
        
        if not self.validate_dataframe(df):
            return TradingSignal('WAIT', 0, 0, reason='Недостаточно данных')
        
        try:
            # Очищаем данные от NaN и inf
            df = self._clean_dataframe(df)
            
            # Рассчитываем индикаторы с защитой
            indicators = self._safe_calculate_indicators(df)
            
            if not indicators:
                return TradingSignal('WAIT', 0, 0, reason='Ошибка расчета индикаторов')
            
            # Анализируем сигналы
            signals = self._analyze_signals(indicators, df)
            
            # Принимаем решение
            return self._make_decision(signals, indicators, df)
            
        except Exception as e:
            logger.error(f"Ошибка анализа {symbol}: {e}")
            return TradingSignal('WAIT', 0, 0, reason='Ошибка анализа')
    
    def _clean_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Очистка данных от некорректных значений"""
        df = df.copy()
        
        # Заменяем inf на NaN
        df.replace([np.inf, -np.inf], np.nan, inplace=True)
        
        # Заполняем NaN методом forward fill
        df.fillna(method='ffill', inplace=True)
        
        # Если остались NaN, заполняем средними значениями
        df.fillna(df.mean(), inplace=True)
        
        return df
    
    def _safe_calculate_indicators(self, df: pd.DataFrame) -> Dict:
        """Безопасный расчет индикаторов"""
        indicators = {}
        
        try:
            # Подавляем предупреждения для этого блока
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                
                # RSI
                try:
                    indicators['rsi'] = ta.momentum.rsi(df['close'], window=14).iloc[-1]
                    if pd.isna(indicators['rsi']):
                        indicators['rsi'] = 50.0
                except:
                    indicators['rsi'] = 50.0
                
                # MACD
                try:
                    macd = ta.trend.MACD(df['close'])
                    indicators['macd'] = macd.macd().iloc[-1]
                    indicators['macd_signal'] = macd.macd_signal().iloc[-1]
                    indicators['macd_diff'] = macd.macd_diff().iloc[-1]
                    
                    # Проверка на NaN
                    for key in ['macd', 'macd_signal', 'macd_diff']:
                        if pd.isna(indicators[key]):
                            indicators[key] = 0.0
                except:
                    indicators['macd'] = 0.0
                    indicators['macd_signal'] = 0.0
                    indicators['macd_diff'] = 0.0
                
                # Bollinger Bands
                try:
                    bb = ta.volatility.BollingerBands(df['close'], window=20, window_dev=2)
                    indicators['bb_upper'] = bb.bollinger_hband().iloc[-1]
                    indicators['bb_lower'] = bb.bollinger_lband().iloc[-1]
                    indicators['bb_middle'] = bb.bollinger_mavg().iloc[-1]
                    indicators['bb_percent'] = bb.bollinger_pband().iloc[-1]
                    
                    # Проверка на NaN
                    current_price = df['close'].iloc[-1]
                    for key in ['bb_upper', 'bb_lower', 'bb_middle']:
                        if pd.isna(indicators[key]):
                            indicators[key] = current_price
                    if pd.isna(indicators['bb_percent']):
                        indicators['bb_percent'] = 0.5
                except:
                    current_price = df['close'].iloc[-1]
                    indicators['bb_upper'] = current_price * 1.02
                    indicators['bb_lower'] = current_price * 0.98
                    indicators['bb_middle'] = current_price
                    indicators['bb_percent'] = 0.5
                
                # EMA
                try:
                    indicators['ema_9'] = ta.trend.ema_indicator(df['close'], window=9).iloc[-1]
                    indicators['ema_21'] = ta.trend.ema_indicator(df['close'], window=21).iloc[-1]
                    indicators['ema_50'] = ta.trend.ema_indicator(df['close'], window=50).iloc[-1]
                except:
                    current_price = df['close'].iloc[-1]
                    indicators['ema_9'] = current_price
                    indicators['ema_21'] = current_price
                    indicators['ema_50'] = current_price
                
                # ADX (с защитой от деления на ноль)
                try:
                    adx = ta.trend.ADXIndicator(df['high'], df['low'], df['close'])
                    indicators['adx'] = adx.adx().iloc[-1]
                    indicators['adx_pos'] = adx.adx_pos().iloc[-1]
                    indicators['adx_neg'] = adx.adx_neg().iloc[-1]
                    
                    # Проверка на NaN
                    for key in ['adx', 'adx_pos', 'adx_neg']:
                        if pd.isna(indicators[key]):
                            indicators[key] = 0.0
                except:
                    indicators['adx'] = 0.0
                    indicators['adx_pos'] = 0.0
                    indicators['adx_neg'] = 0.0
                
                # ATR
                try:
                    atr = ta.volatility.AverageTrueRange(df['high'], df['low'], df['close'])
                    indicators['atr'] = atr.average_true_range().iloc[-1]
                    if pd.isna(indicators['atr']):
                        indicators['atr'] = df['close'].iloc[-1] * 0.02
                except:
                    indicators['atr'] = df['close'].iloc[-1] * 0.02
                
                # Volume
                try:
                    indicators['volume_sma'] = df['volume'].rolling(window=20).mean().iloc[-1]
                    indicators['volume_ratio'] = df['volume'].iloc[-1] / indicators['volume_sma']
                    if pd.isna(indicators['volume_ratio']):
                        indicators['volume_ratio'] = 1.0
                except:
                    indicators['volume_sma'] = df['volume'].mean()
                    indicators['volume_ratio'] = 1.0
                
                # Текущая цена
                indicators['current_price'] = df['close'].iloc[-1]
                
                return indicators
                
        except Exception as e:
            logger.error(f"Критическая ошибка расчета индикаторов: {e}")
            return {}
    
    def _analyze_signals(self, indicators: Dict, df: pd.DataFrame) -> Dict:
        """Анализ сигналов с защитой от ошибок"""
        signals = {
            'buy_signals': [],
            'sell_signals': [],
            'neutral_signals': []
        }
        
        try:
            # RSI сигналы
            if indicators['rsi'] < 30:
                signals['buy_signals'].append(('RSI', 'Перепроданность', 0.8))
            elif indicators['rsi'] > 70:
                signals['sell_signals'].append(('RSI', 'Перекупленность', 0.8))
            
            # MACD сигналы
            if indicators['macd'] > indicators['macd_signal'] and indicators['macd_diff'] > 0:
                signals['buy_signals'].append(('MACD', 'Бычье пересечение', 0.7))
            elif indicators['macd'] < indicators['macd_signal'] and indicators['macd_diff'] < 0:
                signals['sell_signals'].append(('MACD', 'Медвежье пересечение', 0.7))
            
            # Bollinger Bands сигналы
            if indicators['bb_percent'] < 0.2:
                signals['buy_signals'].append(('BB', 'Цена у нижней границы', 0.6))
            elif indicators['bb_percent'] > 0.8:
                signals['sell_signals'].append(('BB', 'Цена у верхней границы', 0.6))
            
            # EMA тренд
            if (indicators['ema_9'] > indicators['ema_21'] > indicators['ema_50'] and 
                indicators['current_price'] > indicators['ema_9']):
                signals['buy_signals'].append(('EMA', 'Восходящий тренд', 0.7))
            elif (indicators['ema_9'] < indicators['ema_21'] < indicators['ema_50'] and 
                  indicators['current_price'] < indicators['ema_9']):
                signals['sell_signals'].append(('EMA', 'Нисходящий тренд', 0.7))
            
            # ADX сила тренда
            if indicators['adx'] > 25:
                if indicators['adx_pos'] > indicators['adx_neg']:
                    signals['buy_signals'].append(('ADX', 'Сильный восходящий тренд', 0.6))
                else:
                    signals['sell_signals'].append(('ADX', 'Сильный нисходящий тренд', 0.6))
            
            # Volume подтверждение
            if indicators['volume_ratio'] > 1.5:
                signals['neutral_signals'].append(('Volume', 'Высокий объем', 0.5))
            
            return signals
            
        except Exception as e:
            logger.error(f"Ошибка анализа сигналов: {e}")
            return signals
    
    def _make_decision(self, signals: Dict, indicators: Dict, df: pd.DataFrame) -> TradingSignal:
        """Принятие решения с защитой от ошибок"""
        try:
            buy_score = sum(signal[2] for signal in signals['buy_signals'])
            sell_score = sum(signal[2] for signal in signals['sell_signals'])
            
            buy_count = len(signals['buy_signals'])
            sell_count = len(signals['sell_signals'])
            
            current_price = indicators['current_price']
            atr = indicators['atr']
            
            # Проверяем минимальное количество подтверждений
            if buy_count >= self.min_indicators_confirm and buy_score > sell_score:
                # Безопасный расчет уровней
                stop_loss = max(current_price * 0.95, current_price - 2 * atr)
                take_profit = min(current_price * 1.1, current_price + 3 * atr)
                
                # Проверка risk/reward
                risk_reward = self.calculate_risk_reward(current_price, stop_loss, take_profit)
                if risk_reward < 1.5:
                    take_profit = current_price + (current_price - stop_loss) * 2
                
                confidence = min(0.95, buy_score / (buy_count * 0.8))
                
                reasons = [f"{sig[0]}: {sig[1]}" for sig in signals['buy_signals']]
                reason = "; ".join(reasons[:3])
                
                return TradingSignal(
                    action='BUY',
                    confidence=confidence,
                    price=current_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    reason=reason,
                    risk_reward_ratio=risk_reward,
                    indicators=indicators
                )
                
            elif sell_count >= self.min_indicators_confirm and sell_score > buy_score:
                # Безопасный расчет уровней
                stop_loss = min(current_price * 1.05, current_price + 2 * atr)
                take_profit = max(current_price * 0.9, current_price - 3 * atr)
                
                # Проверка risk/reward
                risk_reward = self.calculate_risk_reward(current_price, stop_loss, take_profit)
                if risk_reward < 1.5:
                    take_profit = current_price - (stop_loss - current_price) * 2
                
                confidence = min(0.95, sell_score / (sell_count * 0.8))
                
                reasons = [f"{sig[0]}: {sig[1]}" for sig in signals['sell_signals']]
                reason = "; ".join(reasons[:3])
                
                return TradingSignal(
                    action='SELL',
                    confidence=confidence,
                    price=current_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    reason=reason,
                    risk_reward_ratio=risk_reward,
                    indicators=indicators
                )
            
            else:
                reason = f"Недостаточно подтверждений (BUY: {buy_count}, SELL: {sell_count})"
                return TradingSignal(
                    action='WAIT',
                    confidence=0,
                    price=current_price,
                    reason=reason,
                    indicators=indicators
                )
                
        except Exception as e:
            logger.error(f"Ошибка принятия решения: {e}")
            return TradingSignal(
                action='WAIT',
                confidence=0,
                price=df['close'].iloc[-1],
                reason='Ошибка принятия решения'
            )
