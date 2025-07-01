"""
Новый файл: src/strategies/swing.py
===================================
Стратегия свинг-трейдинга (Swing Trading Strategy)
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, List
import logging

try:
    from ta.momentum import RSIIndicator
    from ta.trend import EMAIndicator, MACD, ADXIndicator
    from ta.volatility import BollingerBands, AverageTrueRange
    from ta.volume import OnBalanceVolumeIndicator
    TA_AVAILABLE = True
except ImportError:
    TA_AVAILABLE = False
    logging.warning("⚠️ TA-Lib не установлен, используем базовые вычисления")

from .base import BaseStrategy, TradingSignal

logger = logging.getLogger(__name__)

class SwingStrategy(BaseStrategy):
    """
    Стратегия свинг-трейдинга
    
    Логика:
    - Средне-срочные позиции (несколько дней до недель)
    - Торговля по направлению основного тренда
    - Вход на откатах против краткосрочного тренда
    - Широкие стоп-лоссы и цели прибыли
    - Лучше работает в трендовых рынках
    """
    
    # Константы стратегии
    PROFIT_TARGET_PERCENT = 0.03    # 3% цель прибыли
    STOP_LOSS_PERCENT = 0.015       # 1.5% стоп-лосс
    RSI_OVERSOLD = 40              # Умеренные уровни для свинг-трейдинга
    RSI_OVERBOUGHT = 60
    TREND_LOOKBACK = 50            # Период для определения тренда
    PULLBACK_DEPTH_MIN = 0.01      # Минимальная глубина отката (1%)
    PULLBACK_DEPTH_MAX = 0.05      # Максимальная глубина отката (5%)
    VOLUME_CONFIRMATION_THRESHOLD = 1.2  # Подтверждение объемом
    
    # Метаинформация
    STRATEGY_TYPE = 'swing'
    RISK_LEVEL = 'medium'
    TIMEFRAMES = ['1h', '4h', '1d']
    
    def __init__(self, strategy_name: str = "swing", config: Optional[Dict] = None):
        """Инициализация стратегии свинг-трейдинга"""
        super().__init__(strategy_name, config)
        
        # Параметры из конфигурации
        self.profit_target = self.config.get('profit_target', 0.03)
        self.stop_loss = self.config.get('stop_loss', 0.015)
        self.trend_lookback = self.config.get('trend_lookback', 50)
        self.min_confidence = self.config.get('min_confidence', 0.7)
        self.ema_short = self.config.get('ema_short', 20)
        self.ema_long = self.config.get('ema_long', 50)
        
        logger.info(f"✅ SwingStrategy инициализирована: {self.name}")
        
    async def analyze(self, df: pd.DataFrame, symbol: str) -> TradingSignal:
        """Анализ для стратегии свинг-трейдинга"""
        if not self.validate_dataframe(df):
            return TradingSignal('WAIT', 0, 0, reason='Недостаточно данных')
            
        try:
            # Определяем основной тренд
            trend_analysis = self._analyze_main_trend(df)
            if trend_analysis['trend'] == 'UNKNOWN':
                return TradingSignal('WAIT', 0, 0, reason='Неопределенный тренд')
            
            # Рассчитываем индикаторы
            indicators = self._calculate_swing_indicators(df)
            if not indicators:
                return TradingSignal('WAIT', 0, 0, reason='Ошибка расчета индикаторов')
                
            # Ищем точки входа (откаты против краткосрочного тренда)
            swing_signals = self._analyze_swing_entry_points(df, trend_analysis, indicators)
            
            # Принимаем решение
            return self._make_swing_decision(swing_signals, trend_analysis, indicators, df)
            
        except Exception as e:
            logger.error(f"Ошибка анализа swing для {symbol}: {e}")
            return TradingSignal('WAIT', 0, 0, reason=f'Ошибка анализа: {e}')
    
    def _analyze_main_trend(self, df: pd.DataFrame) -> Dict:
        """Анализ основного тренда"""
        try:
            # Используем EMA для определения тренда
            ema_short = df['close'].ewm(span=self.ema_short).mean()
            ema_long = df['close'].ewm(span=self.ema_long).mean()
            
            current_price = df['close'].iloc[-1]
            ema_short_current = ema_short.iloc[-1]
            ema_long_current = ema_long.iloc[-1]
            
            # Определяем направление тренда
            if ema_short_current > ema_long_current and current_price > ema_short_current:
                trend_direction = 'UPTREND'
            elif ema_short_current < ema_long_current and current_price < ema_short_current:
                trend_direction = 'DOWNTREND'
            else:
                trend_direction = 'SIDEWAYS'
            
            # Оцениваем силу тренда
            price_change = (current_price - df['close'].iloc[-self.trend_lookback]) / df['close'].iloc[-self.trend_lookback]
            trend_strength = abs(price_change)
            
            if trend_strength > 0.10:
                strength = 'STRONG'
            elif trend_strength > 0.05:
                strength = 'MODERATE'
            elif trend_strength > 0.02:
                strength = 'WEAK'
            else:
                strength = 'NONE'
                trend_direction = 'SIDEWAYS'
            
            # Проверяем консистентность тренда
            ema_slope_short = (ema_short.iloc[-1] - ema_short.iloc[-10]) / ema_short.iloc[-10]
            ema_slope_long = (ema_long.iloc[-1] - ema_long.iloc[-10]) / ema_long.iloc[-10]
            
            consistency = 0.0
            if trend_direction == 'UPTREND' and ema_slope_short > 0 and ema_slope_long > 0:
                consistency = min(ema_slope_short * 100, 1.0)
            elif trend_direction == 'DOWNTREND' and ema_slope_short < 0 and ema_slope_long < 0:
                consistency = min(abs(ema_slope_short) * 100, 1.0)
            
            return {
                'trend': trend_direction,
                'strength': strength,
                'consistency': consistency,
                'price_change': price_change,
                'ema_short': ema_short_current,
                'ema_long': ema_long_current
            }
            
        except Exception as e:
            logger.error(f"Ошибка анализа тренда: {e}")
            return {'trend': 'UNKNOWN'}
    
    def _calculate_swing_indicators(self, df: pd.DataFrame) -> Dict:
        """Расчет индикаторов для свинг-трейдинга"""
        try:
            indicators = {}
            current_price = float(df['close'].iloc[-1])
            indicators['current_price'] = current_price
            
            if TA_AVAILABLE:
                # RSI
                rsi = RSIIndicator(df['close'], window=14)
                indicators['rsi'] = float(rsi.rsi().iloc[-1])
                
                # MACD для подтверждения тренда
                macd = MACD(df['close'])
                indicators['macd'] = float(macd.macd().iloc[-1])
                indicators['macd_signal'] = float(macd.macd_signal().iloc[-1])
                indicators['macd_diff'] = float(macd.macd_diff().iloc[-1])
                
                # ADX для силы тренда
                adx = ADXIndicator(df['high'], df['low'], df['close'])
                indicators['adx'] = float(adx.adx().iloc[-1])
                indicators['adx_pos'] = float(adx.adx_pos().iloc[-1])
                indicators['adx_neg'] = float(adx.adx_neg().iloc[-1])
                
                # Bollinger Bands для определения перерастяжения
                bb = BollingerBands(df['close'], window=20, window_dev=2)
                indicators['bb_upper'] = float(bb.bollinger_hband().iloc[-1])
                indicators['bb_lower'] = float(bb.bollinger_lband().iloc[-1])
                indicators['bb_middle'] = float(bb.bollinger_mavg().iloc[-1])
                indicators['bb_percent'] = float(bb.bollinger_pband().iloc[-1])
                
                # ATR для волатильности
                atr = AverageTrueRange(df['high'], df['low'], df['close'])
                indicators['atr'] = float(atr.average_true_range().iloc[-1])
                
                # OBV для объемного анализа
                if 'volume' in df.columns:
                    obv = OnBalanceVolumeIndicator(df['close'], df['volume'])
                    indicators['obv'] = float(obv.on_balance_volume().iloc[-1])
                    indicators['obv_trend'] = self._calculate_obv_trend(obv.on_balance_volume())
                
            else:
                # Базовые вычисления без TA-Lib
                indicators['rsi'] = self._calculate_rsi(df['close'])
                macd, signal, hist = self._calculate_macd(df['close'])
                indicators['macd'] = macd
                indicators['macd_signal'] = signal
                indicators['macd_diff'] = hist
                indicators['adx'] = 30.0  # Предполагаем средний ADX
                
                bb_upper, bb_middle, bb_lower = self._calculate_bollinger_bands(df['close'])
                indicators['bb_upper'] = bb_upper
                indicators['bb_middle'] = bb_middle
                indicators['bb_lower'] = bb_lower
                indicators['bb_percent'] = (current_price - bb_lower) / (bb_upper - bb_lower) if bb_upper > bb_lower else 0.5
                
                indicators['atr'] = self._calculate_atr(df)
            
            # Дополнительные расчеты
            # Позиция цены относительно недавнего диапазона
            recent_high = df['high'].tail(20).max()
            recent_low = df['low'].tail(20).min()
            if recent_high > recent_low:
                indicators['price_position'] = (current_price - recent_low) / (recent_high - recent_low)
            else:
                indicators['price_position'] = 0.5
            
            # Анализ объема
            if 'volume' in df.columns:
                volume_ma = df['volume'].rolling(20).mean()
                current_volume = df['volume'].iloc[-1]
                indicators['volume_ratio'] = current_volume / volume_ma.iloc[-1] if volume_ma.iloc[-1] > 0 else 1.0
            else:
                indicators['volume_ratio'] = 1.0
            
            # Недавняя волатильность
            indicators['volatility'] = df['close'].pct_change().rolling(20).std().iloc[-1]
            
            return indicators
            
        except Exception as e:
            logger.error(f"Ошибка расчета индикаторов swing: {e}")
            return {}
    
    def _analyze_swing_entry_points(self, df: pd.DataFrame, trend_analysis: Dict, indicators: Dict) -> Dict:
        """Анализ точек входа для свинг-трейдинга"""
        signals = {'buy_signals': [], 'sell_signals': []}
        
        try:
            trend = trend_analysis['trend']
            current_price = indicators['current_price']
            
            # Для восходящего тренда ищем откаты вниз для покупки
            if trend == 'UPTREND':
                signals['buy_signals'] = self._find_bullish_pullback_entries(df, trend_analysis, indicators)
            
            # Для нисходящего тренда ищем откаты вверх для продажи
            elif trend == 'DOWNTREND':
                signals['sell_signals'] = self._find_bearish_pullback_entries(df, trend_analysis, indicators)
            
            return signals
            
        except Exception as e:
            logger.error(f"Ошибка анализа точек входа swing: {e}")
            return signals
    
    def _find_bullish_pullback_entries(self, df: pd.DataFrame, trend_analysis: Dict, indicators: Dict) -> List[Dict]:
        """Поиск точек входа на откатах в восходящем тренде"""
        buy_signals = []
        
        try:
            current_price = indicators['current_price']
            rsi = indicators['rsi']
            bb_percent = indicators['bb_percent']
            macd_diff = indicators['macd_diff']
            ema_short = trend_analysis['ema_short']
            
            # 1. RSI откат (не перепроданность, а просто снижение)
            if self.RSI_OVERSOLD <= rsi <= 50:
                confidence = 0.6 + (50 - rsi) / 100  # Чем ниже RSI, тем выше уверенность
                buy_signals.append({
                    'type': 'RSI_PULLBACK',
                    'confidence': confidence,
                    'reason': f'RSI откат в восходящем тренде: {rsi:.1f}'
                })
            
            # 2. Цена отошла от EMA, но тренд сохраняется
            price_distance_from_ema = (current_price - ema_short) / ema_short
            if -0.05 <= price_distance_from_ema <= -0.01:  # Откат на 1-5%
                confidence = 0.7
                buy_signals.append({
                    'type': 'EMA_PULLBACK',
                    'confidence': confidence,
                    'reason': f'Откат к EMA в восходящем тренде: {price_distance_from_ema:.2%}'
                })
            
            # 3. Bollinger Bands - цена в нижней части полосы
            if bb_percent < 0.3:
                confidence = 0.6 + (0.3 - bb_percent)
                buy_signals.append({
                    'type': 'BB_LOWER',
                    'confidence': confidence,
                    'reason': f'Цена в нижней части Bollinger Bands: {bb_percent:.2f}'
                })
            
            # 4. MACD подтверждение (начинает расти после снижения)
            if macd_diff > 0 and macd_diff > indicators.get('macd_diff_prev', 0):
                confidence = 0.5
                buy_signals.append({
                    'type': 'MACD_RECOVERY',
                    'confidence': confidence,
                    'reason': 'MACD начинает восстанавливаться'
                })
            
            # 5. Объемное подтверждение
            volume_ratio = indicators.get('volume_ratio', 1.0)
            if volume_ratio >= self.VOLUME_CONFIRMATION_THRESHOLD:
                # Увеличиваем уверенность всех сигналов
                for signal in buy_signals:
                    signal['confidence'] *= 1.1
                    signal['reason'] += f' + объем x{volume_ratio:.1f}'
            
            return buy_signals
            
        except Exception as e:
            logger.error(f"Ошибка поиска бычьих сигналов: {e}")
            return []
    
    def _find_bearish_pullback_entries(self, df: pd.DataFrame, trend_analysis: Dict, indicators: Dict) -> List[Dict]:
        """Поиск точек входа на откатах в нисходящем тренде"""
        sell_signals = []
        
        try:
            current_price = indicators['current_price']
            rsi = indicators['rsi']
            bb_percent = indicators['bb_percent']
            macd_diff = indicators['macd_diff']
            ema_short = trend_analysis['ema_short']
            
            # 1. RSI откат вверх
            if 50 <= rsi <= self.RSI_OVERBOUGHT:
                confidence = 0.6 + (rsi - 50) / 100
                sell_signals.append({
                    'type': 'RSI_PULLBACK',
                    'confidence': confidence,
                    'reason': f'RSI откат в нисходящем тренде: {rsi:.1f}'
                })
            
            # 2. Цена поднялась к EMA
            price_distance_from_ema = (current_price - ema_short) / ema_short
            if 0.01 <= price_distance_from_ema <= 0.05:
                confidence = 0.7
                sell_signals.append({
                    'type': 'EMA_PULLBACK',
                    'confidence': confidence,
                    'reason': f'Откат к EMA в нисходящем тренде: {price_distance_from_ema:.2%}'
                })
            
            # 3. Bollinger Bands - цена в верхней части полосы
            if bb_percent > 0.7:
                confidence = 0.6 + (bb_percent - 0.7)
                sell_signals.append({
                    'type': 'BB_UPPER',
                    'confidence': confidence,
                    'reason': f'Цена в верхней части Bollinger Bands: {bb_percent:.2f}'
                })
            
            # 4. MACD подтверждение
            if macd_diff < 0 and macd_diff < indicators.get('macd_diff_prev', 0):
                confidence = 0.5
                sell_signals.append({
                    'type': 'MACD_DECLINE',
                    'confidence': confidence,
                    'reason': 'MACD продолжает снижаться'
                })
            
            # 5. Объемное подтверждение
            volume_ratio = indicators.get('volume_ratio', 1.0)
            if volume_ratio >= self.VOLUME_CONFIRMATION_THRESHOLD:
                for signal in sell_signals:
                    signal['confidence'] *= 1.1
                    signal['reason'] += f' + объем x{volume_ratio:.1f}'
            
            return sell_signals
            
        except Exception as e:
            logger.error(f"Ошибка поиска медвежьих сигналов: {e}")
            return []
    
    def _make_swing_decision(self, signals: Dict, trend_analysis: Dict, indicators: Dict, df: pd.DataFrame) -> TradingSignal:
        """Принятие решения для свинг-трейдинга"""
        try:
            buy_signals = signals.get('buy_signals', [])
            sell_signals = signals.get('sell_signals', [])
            
            current_price = indicators['current_price']
            atr = indicators['atr']
            trend_strength = trend_analysis.get('strength', 'WEAK')
            
            # Корректировка уверенности в зависимости от силы тренда
            strength_multiplier = {
                'STRONG': 1.2,
                'MODERATE': 1.0,
                'WEAK': 0.8,
                'NONE': 0.5
            }.get(trend_strength, 1.0)
            
            # BUY сигнал
            if buy_signals:
                total_confidence = sum(signal['confidence'] for signal in buy_signals)
                total_confidence *= strength_multiplier
                total_confidence = min(total_confidence, 1.0)
                
                if total_confidence >= self.min_confidence:
                    # Расчет уровней для свинг-трейдинга (более широкие)
                    stop_loss = current_price * (1 - self.stop_loss)
                    take_profit = current_price * (1 + self.profit_target)
                    
                    # Альтернативно: используем ATR для динамичных уровней
                    atr_stop = current_price - (atr * 3.0)  # Широкий стоп для свинга
                    atr_target = current_price + (atr * 6.0)
                    
                    # Выбираем более подходящие уровни
                    final_stop = max(stop_loss, atr_stop)
                    final_target = max(take_profit, atr_target)
                    
                    risk = current_price - final_stop
                    reward = final_target - current_price
                    
                    if risk > 0 and reward / risk >= 2.0:  # Минимум 1:2 для свинга
                        reasons = [signal['reason'] for signal in buy_signals]
                        reason = f"SWING_BUY ({trend_strength}): " + "; ".join(reasons)
                        
                        return TradingSignal(
                            action='BUY',
                            confidence=total_confidence,
                            price=current_price,
                            stop_loss=final_stop,
                            take_profit=final_target,
                            reason=reason,
                            risk_reward_ratio=reward / risk,
                            indicators=indicators
                        )
            
            # SELL сигнал
            if sell_signals:
                total_confidence = sum(signal['confidence'] for signal in sell_signals)
                total_confidence *= strength_multiplier
                total_confidence = min(total_confidence, 1.0)
                
                if total_confidence >= self.min_confidence:
                    stop_loss = current_price * (1 + self.stop_loss)
                    take_profit = current_price * (1 - self.profit_target)
                    
                    atr_stop = current_price + (atr * 3.0)
                    atr_target = current_price - (atr * 6.0)
                    
                    final_stop = min(stop_loss, atr_stop)
                    final_target = min(take_profit, atr_target)
                    
                    risk = final_stop - current_price
                    reward = current_price - final_target
                    
                    if risk > 0 and reward / risk >= 2.0:
                        reasons = [signal['reason'] for signal in sell_signals]
                        reason = f"SWING_SELL ({trend_strength}): " + "; ".join(reasons)
                        
                        return TradingSignal(
                            action='SELL',
                            confidence=total_confidence,
                            price=current_price,
                            stop_loss=final_stop,
                            take_profit=final_target,
                            reason=reason,
                            risk_reward_ratio=reward / risk,
                            indicators=indicators
                        )
            
            # WAIT
            signal_count = len(buy_signals) + len(sell_signals)
            trend = trend_analysis.get('trend', 'UNKNOWN')
            
            reason = f"SWING_WAIT: тренд={trend}, сила={trend_strength}, сигналов={signal_count}"
            
            return TradingSignal(
                action='WAIT',
                confidence=0.0,
                price=current_price,
                reason=reason,
                indicators=indicators
            )
            
        except Exception as e:
            logger.error(f"Ошибка принятия решения swing: {e}")
            return TradingSignal('WAIT', 0, 0, reason=f'Ошибка решения: {e}')
    
    # Вспомогательные методы
    def _calculate_obv_trend(self, obv_series):
        """Определение тренда OBV"""
        if len(obv_series) < 20:
            return 'NEUTRAL'
        
        recent_obv = obv_series.tail(20)
        slope = (recent_obv.iloc[-1] - recent_obv.iloc[0]) / len(recent_obv)
        
        if slope > recent_obv.std() * 0.1:
            return 'RISING'
        elif slope < -recent_obv.std() * 0.1:
            return 'FALLING'
        else:
            return 'NEUTRAL'
    
    def _calculate_rsi(self, prices, period=14):
        """RSI без TA-Lib"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return float(rsi.iloc[-1]) if not rsi.empty else 50.0
    
    def _calculate_macd(self, prices, fast=12, slow=26, signal=9):
        """MACD без TA-Lib"""
        ema_fast = prices.ewm(span=fast).mean()
        ema_slow = prices.ewm(span=slow).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal).mean()
        histogram = macd_line - signal_line
        
        return float(macd_line.iloc[-1]), float(signal_line.iloc[-1]), float(histogram.iloc[-1])
    
    def _calculate_bollinger_bands(self, prices, period=20, std_dev=2):
        """Bollinger Bands без TA-Lib"""
        sma = prices.rolling(window=period).mean()
        std = prices.rolling(window=period).std()
        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)
        return float(upper.iloc[-1]), float(sma.iloc[-1]), float(lower.iloc[-1])
    
    def _calculate_atr(self, df, period=14):
        """ATR без TA-Lib"""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        return float(atr.iloc[-1]) if not atr.empty else 0.02
    
    def validate_dataframe(self, df: pd.DataFrame) -> bool:
        """Валидация для свинг-трейдинга"""
        if df is None or df.empty:
            return False
            
        required_columns = ['open', 'high', 'low', 'close']
        if not all(col in df.columns for col in required_columns):
            return False
            
        # Для свинг-трейдинга нужно больше данных для анализа тренда
        if len(df) < 100:
            return False
            
        if df[required_columns].isnull().any().any():
            return False
            
        return True