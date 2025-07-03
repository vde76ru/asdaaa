"""
Новый файл: src/strategies/scalping.py
========================================
Стратегия скальпинга (Scalping Strategy)
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
import logging

try:
    from ta.momentum import RSIIndicator, StochasticOscillator
    from ta.trend import EMAIndicator
    from ta.volatility import AverageTrueRange
    TA_AVAILABLE = True
except ImportError:
    TA_AVAILABLE = False
    logging.warning("⚠️ TA-Lib не установлен, используем базовые вычисления")

from .base import BaseStrategy
from ..common.types import UnifiedTradingSignal as TradingSignal

logger = logging.getLogger(__name__)

class ScalpingStrategy(BaseStrategy):
    """
    Стратегия скальпинга
    
    Логика:
    - Быстрые входы и выходы на малых таймфреймах
    - Маленькие цели по прибыли (0.5-1%)
    - Жесткие стоп-лоссы (0.3-0.5%)
    - Высокая частота сделок
    - Работает в боковых рынках с низкой волатильностью
    """
    
    # Константы стратегии
    PROFIT_TARGET_PERCENT = 0.005   # 0.5% цель прибыли
    STOP_LOSS_PERCENT = 0.003       # 0.3% стоп-лосс
    RSI_OVERSOLD = 35              # Менее экстремальные уровни для скальпинга
    RSI_OVERBOUGHT = 65
    STOCH_OVERSOLD = 25
    STOCH_OVERBOUGHT = 75
    EMA_PERIOD_FAST = 5            # Быстрые периоды для скальпинга
    EMA_PERIOD_SLOW = 13
    MAX_SPREAD_PERCENT = 0.001     # Максимальный спред (0.1%)
    MIN_VOLUME_RATIO = 0.8         # Минимальный объем (80% от среднего)
    
    # Метаинформация
    STRATEGY_TYPE = 'scalping'
    RISK_LEVEL = 'low'
    TIMEFRAMES = ['1m', '5m', '15m']
    
    def __init__(self, strategy_name: str = "scalping", config: Optional[Dict] = None):
        """Инициализация стратегии скальпинга"""
        super().__init__(strategy_name, config)
        
        # Параметры из конфигурации
        self.profit_target = self.config.get('profit_target', 0.005)
        self.stop_loss = self.config.get('stop_loss', 0.003)
        self.ema_fast = self.config.get('ema_fast', 5)
        self.ema_slow = self.config.get('ema_slow', 13)
        self.min_confidence = self.config.get('min_confidence', 0.8)  # Высокая уверенность для скальпинга
        
        logger.info(f"✅ ScalpingStrategy инициализирована: {self.name}")
        
    async def analyze(self, df: pd.DataFrame, symbol: str) -> TradingSignal:
        """Анализ для стратегии скальпинга"""
        if not self.validate_dataframe(df):
            return TradingSignal('WAIT', 0, 0, reason='Недостаточно данных')
            
        try:
            # Проверяем условия для скальпинга
            market_conditions = self._check_scalping_conditions(df)
            if not market_conditions['suitable']:
                return TradingSignal('WAIT', 0, 0, reason=market_conditions['reason'])
            
            # Рассчитываем быстрые индикаторы
            indicators = self._calculate_scalping_indicators(df)
            if not indicators:
                return TradingSignal('WAIT', 0, 0, reason='Ошибка расчета индикаторов')
                
            # Ищем быстрые торговые возможности
            scalping_signals = self._analyze_scalping_signals(indicators, df)
            
            # Принимаем решение
            return self._make_scalping_decision(scalping_signals, indicators, df)
            
        except Exception as e:
            logger.error(f"Ошибка анализа scalping для {symbol}: {e}")
            return TradingSignal('WAIT', 0, 0, reason=f'Ошибка анализа: {e}')
    
    def _check_scalping_conditions(self, df: pd.DataFrame) -> Dict:
        """Проверка подходящих условий для скальпинга"""
        try:
            # Проверяем волатильность (должна быть низкой-средней)
            recent_returns = df['close'].pct_change().tail(20)
            volatility = recent_returns.std() * np.sqrt(1440)  # Дневная волатильность
            
            if volatility > 0.05:  # Более 5% дневной волатильности
                return {'suitable': False, 'reason': f'Высокая волатильность: {volatility:.2%}'}
            
            # Проверяем спред (разница между high и low)
            recent_spreads = ((df['high'] - df['low']) / df['close']).tail(20)
            avg_spread = recent_spreads.mean()
            
            if avg_spread > self.MAX_SPREAD_PERCENT:
                return {'suitable': False, 'reason': f'Высокий спред: {avg_spread:.3%}'}
            
            # Проверяем объем
            if 'volume' in df.columns:
                recent_volume = df['volume'].tail(20)
                avg_volume = recent_volume.mean()
                current_volume = df['volume'].iloc[-1]
                volume_ratio = current_volume / avg_volume
                
                if volume_ratio < self.MIN_VOLUME_RATIO:
                    return {'suitable': False, 'reason': f'Низкий объем: {volume_ratio:.1f}x'}
            
            # Проверяем тренд (скальпинг лучше в боковых рынках)
            ema_20 = df['close'].ewm(span=20).mean()
            price_above_ema = df['close'].iloc[-1] > ema_20.iloc[-1]
            ema_slope = (ema_20.iloc[-1] - ema_20.iloc[-5]) / ema_20.iloc[-5]
            
            if abs(ema_slope) > 0.02:  # Сильный тренд
                return {'suitable': False, 'reason': f'Сильный тренд: {ema_slope:.2%}'}
            
            return {
                'suitable': True, 
                'reason': f'Подходящие условия: волатильность={volatility:.2%}, спред={avg_spread:.3%}'
            }
            
        except Exception as e:
            logger.error(f"Ошибка проверки условий скальпинга: {e}")
            return {'suitable': False, 'reason': f'Ошибка проверки: {e}'}
    
    def _calculate_scalping_indicators(self, df: pd.DataFrame) -> Dict:
        """Расчет быстрых индикаторов для скальпинга"""
        try:
            indicators = {}
            current_price = float(df['close'].iloc[-1])
            indicators['current_price'] = current_price
            
            if TA_AVAILABLE:
                # Быстрые EMA
                ema_fast = EMAIndicator(df['close'], window=self.ema_fast)
                ema_slow = EMAIndicator(df['close'], window=self.ema_slow)
                indicators['ema_fast'] = float(ema_fast.ema_indicator().iloc[-1])
                indicators['ema_slow'] = float(ema_slow.ema_indicator().iloc[-1])
                
                # Предыдущие значения для определения пересечений
                indicators['ema_fast_prev'] = float(ema_fast.ema_indicator().iloc[-2])
                indicators['ema_slow_prev'] = float(ema_slow.ema_indicator().iloc[-2])
                
                # RSI с коротким периодом
                rsi = RSIIndicator(df['close'], window=7)  # Короткий RSI для скальпинга
                indicators['rsi'] = float(rsi.rsi().iloc[-1])
                
                # Stochastic для точного тайминга
                stoch = StochasticOscillator(df['high'], df['low'], df['close'], window=5, smooth_window=3)
                indicators['stoch_k'] = float(stoch.stoch().iloc[-1])
                indicators['stoch_d'] = float(stoch.stoch_signal().iloc[-1])
                
                # ATR для стоп-лоссов
                atr = AverageTrueRange(df['high'], df['low'], df['close'], window=7)
                indicators['atr'] = float(atr.average_true_range().iloc[-1])
                
            else:
                # Базовые вычисления без TA-Lib
                indicators['ema_fast'] = df['close'].ewm(span=self.ema_fast).mean().iloc[-1]
                indicators['ema_slow'] = df['close'].ewm(span=self.ema_slow).mean().iloc[-1]
                indicators['ema_fast_prev'] = df['close'].ewm(span=self.ema_fast).mean().iloc[-2]
                indicators['ema_slow_prev'] = df['close'].ewm(span=self.ema_slow).mean().iloc[-2]
                indicators['rsi'] = self._calculate_rsi(df['close'], 7)
                indicators['stoch_k'], indicators['stoch_d'] = self._calculate_stochastic(df)
                indicators['atr'] = self._calculate_atr(df, 7)
            
            # Микротренд (очень короткий период)
            micro_trend = df['close'].tail(3)
            if len(micro_trend) >= 3:
                if micro_trend.iloc[-1] > micro_trend.iloc[-2] > micro_trend.iloc[-3]:
                    indicators['micro_trend'] = 'UP'
                elif micro_trend.iloc[-1] < micro_trend.iloc[-2] < micro_trend.iloc[-3]:
                    indicators['micro_trend'] = 'DOWN'
                else:
                    indicators['micro_trend'] = 'SIDEWAYS'
            else:
                indicators['micro_trend'] = 'SIDEWAYS'
            
            # Momentum (изменение за последние несколько периодов)
            indicators['momentum_3'] = (current_price - df['close'].iloc[-4]) / df['close'].iloc[-4]
            indicators['momentum_5'] = (current_price - df['close'].iloc[-6]) / df['close'].iloc[-6]
            
            # Ценовая позиция в недавнем диапазоне
            recent_high = df['high'].tail(10).max()
            recent_low = df['low'].tail(10).min()
            if recent_high > recent_low:
                indicators['price_position'] = (current_price - recent_low) / (recent_high - recent_low)
            else:
                indicators['price_position'] = 0.5
            
            return indicators
            
        except Exception as e:
            logger.error(f"Ошибка расчета индикаторов scalping: {e}")
            return {}
    
    def _analyze_scalping_signals(self, indicators: Dict, df: pd.DataFrame) -> Dict:
        """Анализ быстрых скальпинговых сигналов"""
        signals = {'buy_signals': [], 'sell_signals': []}
        
        try:
            # EMA пересечения (основной сигнал для скальпинга)
            ema_fast = indicators['ema_fast']
            ema_slow = indicators['ema_slow']
            ema_fast_prev = indicators['ema_fast_prev']
            ema_slow_prev = indicators['ema_slow_prev']
            
            # Бычье пересечение EMA
            if ema_fast > ema_slow and ema_fast_prev <= ema_slow_prev:
                signals['buy_signals'].append({
                    'type': 'EMA_CROSS_UP',
                    'confidence': 0.8,
                    'reason': f'Бычье пересечение EMA {self.ema_fast}/{self.ema_slow}'
                })
            
            # Медвежье пересечение EMA
            if ema_fast < ema_slow and ema_fast_prev >= ema_slow_prev:
                signals['sell_signals'].append({
                    'type': 'EMA_CROSS_DOWN',
                    'confidence': 0.8,
                    'reason': f'Медвежье пересечение EMA {self.ema_fast}/{self.ema_slow}'
                })
            
            # RSI сигналы (менее экстремальные уровни)
            rsi = indicators['rsi']
            if rsi < self.RSI_OVERSOLD:
                signals['buy_signals'].append({
                    'type': 'RSI_OVERSOLD',
                    'confidence': 0.6,
                    'reason': f'RSI перепродан: {rsi:.1f}'
                })
            elif rsi > self.RSI_OVERBOUGHT:
                signals['sell_signals'].append({
                    'type': 'RSI_OVERBOUGHT',
                    'confidence': 0.6,
                    'reason': f'RSI перекуплен: {rsi:.1f}'
                })
            
            # Stochastic сигналы
            stoch_k = indicators['stoch_k']
            stoch_d = indicators['stoch_d']
            
            if stoch_k < self.STOCH_OVERSOLD and stoch_k > stoch_d:
                signals['buy_signals'].append({
                    'type': 'STOCH_BUY',
                    'confidence': 0.7,
                    'reason': f'Stochastic сигнал покупки: K={stoch_k:.1f}, D={stoch_d:.1f}'
                })
            elif stoch_k > self.STOCH_OVERBOUGHT and stoch_k < stoch_d:
                signals['sell_signals'].append({
                    'type': 'STOCH_SELL',
                    'confidence': 0.7,
                    'reason': f'Stochastic сигнал продажи: K={stoch_k:.1f}, D={stoch_d:.1f}'
                })
            
            # Микротренд подтверждение
            micro_trend = indicators['micro_trend']
            if micro_trend == 'UP':
                for signal in signals['buy_signals']:
                    signal['confidence'] *= 1.1
            elif micro_trend == 'DOWN':
                for signal in signals['sell_signals']:
                    signal['confidence'] *= 1.1
            
            # Momentum подтверждение
            momentum_3 = indicators['momentum_3']
            momentum_5 = indicators['momentum_5']
            
            if momentum_3 > 0.001 and momentum_5 > 0.001:  # Положительный momentum
                for signal in signals['buy_signals']:
                    signal['confidence'] *= 1.1
            elif momentum_3 < -0.001 and momentum_5 < -0.001:  # Отрицательный momentum
                for signal in signals['sell_signals']:
                    signal['confidence'] *= 1.1
            
            # Ограничиваем уверенность
            for signal_list in [signals['buy_signals'], signals['sell_signals']]:
                for signal in signal_list:
                    signal['confidence'] = min(signal['confidence'], 1.0)
            
            return signals
            
        except Exception as e:
            logger.error(f"Ошибка анализа сигналов scalping: {e}")
            return signals
    
    def _make_scalping_decision(self, signals: Dict, indicators: Dict, df: pd.DataFrame) -> TradingSignal:
        """Принятие решения для скальпинга"""
        try:
            buy_signals = signals.get('buy_signals', [])
            sell_signals = signals.get('sell_signals', [])
            
            current_price = indicators['current_price']
            atr = indicators['atr']
            
            # BUY сигнал
            if buy_signals:
                # Берем сигнал с максимальной уверенностью
                best_signal = max(buy_signals, key=lambda x: x['confidence'])
                
                if best_signal['confidence'] >= self.min_confidence:
                    # Рассчитываем точные уровни для скальпинга
                    stop_loss = current_price * (1 - self.stop_loss)
                    take_profit = current_price * (1 + self.profit_target)
                    
                    # Альтернативно: используем ATR для более динамичных уровней
                    atr_stop = current_price - (atr * 1.5)
                    atr_target = current_price + (atr * 2.0)
                    
                    # Выбираем более консервативные уровни
                    final_stop = max(stop_loss, atr_stop)
                    final_target = min(take_profit, atr_target)
                    
                    # Проверяем risk/reward ratio
                    risk = current_price - final_stop
                    reward = final_target - current_price
                    
                    if risk > 0 and reward / risk >= 1.5:  # Минимум 1:1.5 для скальпинга
                        reasons = [signal['reason'] for signal in buy_signals]
                        reason = f"SCALPING_BUY: " + "; ".join(reasons)
                        
                        return TradingSignal(
                            action='BUY',
                            confidence=best_signal['confidence'],
                            price=current_price,
                            stop_loss=final_stop,
                            take_profit=final_target,
                            reason=reason,
                            risk_reward_ratio=reward / risk,
                            indicators=indicators
                        )
            
            # SELL сигнал
            if sell_signals:
                best_signal = max(sell_signals, key=lambda x: x['confidence'])
                
                if best_signal['confidence'] >= self.min_confidence:
                    stop_loss = current_price * (1 + self.stop_loss)
                    take_profit = current_price * (1 - self.profit_target)
                    
                    atr_stop = current_price + (atr * 1.5)
                    atr_target = current_price - (atr * 2.0)
                    
                    final_stop = min(stop_loss, atr_stop)
                    final_target = max(take_profit, atr_target)
                    
                    risk = final_stop - current_price
                    reward = current_price - final_target
                    
                    if risk > 0 and reward / risk >= 1.5:
                        reasons = [signal['reason'] for signal in sell_signals]
                        reason = f"SCALPING_SELL: " + "; ".join(reasons)
                        
                        return TradingSignal(
                            action='SELL',
                            confidence=best_signal['confidence'],
                            price=current_price,
                            stop_loss=final_stop,
                            take_profit=final_target,
                            reason=reason,
                            risk_reward_ratio=reward / risk,
                            indicators=indicators
                        )
            
            # WAIT
            signal_count = len(buy_signals) + len(sell_signals)
            max_confidence = max([s['confidence'] for s in buy_signals + sell_signals]) if signal_count > 0 else 0
            
            reason = f"SCALPING_WAIT: сигналов={signal_count}, макс_уверенность={max_confidence:.2f}"
            
            return TradingSignal(
                action='WAIT',
                confidence=0.0,
                price=current_price,
                reason=reason,
                indicators=indicators
            )
            
        except Exception as e:
            logger.error(f"Ошибка принятия решения scalping: {e}")
            return TradingSignal('WAIT', 0, 0, reason=f'Ошибка решения: {e}')
    
    # Вспомогательные методы
    def _calculate_rsi(self, prices, period=7):
        """RSI без TA-Lib с коротким периодом"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return float(rsi.iloc[-1]) if not rsi.empty else 50.0
    
    def _calculate_stochastic(self, df, k_period=5, d_period=3):
        """Stochastic без TA-Lib"""
        low_min = df['low'].rolling(window=k_period).min()
        high_max = df['high'].rolling(window=k_period).max()
        
        k_percent = 100 * ((df['close'] - low_min) / (high_max - low_min))
        d_percent = k_percent.rolling(window=d_period).mean()
        
        return float(k_percent.iloc[-1]) if not k_percent.empty else 50.0, float(d_percent.iloc[-1]) if not d_percent.empty else 50.0
    
    def _calculate_atr(self, df, period=7):
        """ATR без TA-Lib с коротким периодом"""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        return float(atr.iloc[-1]) if not atr.empty else 0.001
    
    def validate_dataframe(self, df: pd.DataFrame) -> bool:
        """Специальная валидация для скальпинга"""
        if df is None or df.empty:
            return False
            
        required_columns = ['open', 'high', 'low', 'close']
        if not all(col in df.columns for col in required_columns):
            return False
            
        # Для скальпинга нужно меньше данных, но они должны быть свежими
        if len(df) < 50:
            return False
            
        # Проверяем на NaN
        if df[required_columns].isnull().any().any():
            return False
            
        return True