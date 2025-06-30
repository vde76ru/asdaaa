"""
Новый файл: src/strategies/breakout.py
========================================
Стратегия пробоя уровней (Breakout Strategy)
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, List, Tuple
import logging

try:
    from ta.momentum import RSIIndicator
    from ta.trend import EMAIndicator, ADXIndicator
    from ta.volatility import AverageTrueRange
    from ta.volume import OnBalanceVolumeIndicator
    TA_AVAILABLE = True
except ImportError:
    TA_AVAILABLE = False
    logging.warning("⚠️ TA-Lib не установлен, используем базовые вычисления")

from .base import BaseStrategy, TradingSignal

logger = logging.getLogger(__name__)

class BreakoutStrategy(BaseStrategy):
    """
    Стратегия пробоя уровней
    
    Логика:
    - Определяет ключевые уровни поддержки и сопротивления
    - Ищет пробои этих уровней с подтверждением объемом
    - Входит по направлению пробоя
    - Лучше работает в трендовых рынках
    """
    
    # Константы стратегии
    VOLUME_MULTIPLIER_THRESHOLD = 1.5  # Объем должен быть в 1.5 раза выше среднего
    PRICE_BREAKOUT_THRESHOLD = 0.02    # 2% пробой от уровня
    MIN_CONSOLIDATION_PERIODS = 10     # Минимум периодов консолидации
    ADX_TREND_THRESHOLD = 25           # Минимальная сила тренда
    RSI_MOMENTUM_MIN = 45              # Минимальный RSI для восходящего пробоя
    RSI_MOMENTUM_MAX = 55              # Максимальный RSI для нисходящего пробоя
    
    # Метаинформация
    STRATEGY_TYPE = 'breakout'
    RISK_LEVEL = 'medium_high'
    TIMEFRAMES = ['1h', '4h', '1d']
    
    def __init__(self, strategy_name: str = "breakout", config: Optional[Dict] = None):
        """Инициализация стратегии пробоя"""
        super().__init__(strategy_name, config)
        
        # Параметры из конфигурации
        self.lookback_period = self.config.get('lookback_period', 20)
        self.volume_threshold = self.config.get('volume_threshold', 1.5)
        self.price_threshold = self.config.get('price_threshold', 0.02)
        self.min_confidence = self.config.get('min_confidence', 0.7)
        self.consolidation_periods = self.config.get('consolidation_periods', 10)
        
        logger.info(f"✅ BreakoutStrategy инициализирована: {self.name}")
        
    async def analyze(self, df: pd.DataFrame, symbol: str) -> TradingSignal:
        """Анализ для стратегии пробоя"""
        if not self.validate_dataframe(df):
            return TradingSignal('WAIT', 0, 0, reason='Недостаточно данных')
            
        try:
            # Находим ключевые уровни
            support_resistance = self._find_support_resistance_levels(df)
            if not support_resistance:
                return TradingSignal('WAIT', 0, 0, reason='Не найдены уровни поддержки/сопротивления')
            
            # Рассчитываем индикаторы
            indicators = self._calculate_indicators(df)
            if not indicators:
                return TradingSignal('WAIT', 0, 0, reason='Ошибка расчета индикаторов')
            
            # Проверяем пробои
            breakout_signals = self._analyze_breakouts(df, support_resistance, indicators)
            
            # Принимаем решение
            return self._make_decision(breakout_signals, indicators, support_resistance, df)
            
        except Exception as e:
            logger.error(f"Ошибка анализа breakout для {symbol}: {e}")
            return TradingSignal('WAIT', 0, 0, reason=f'Ошибка анализа: {e}')
    
    def _find_support_resistance_levels(self, df: pd.DataFrame) -> Dict:
        """Поиск уровней поддержки и сопротивления"""
        try:
            # Используем последние N периодов для анализа
            recent_df = df.tail(self.lookback_period * 2)
            
            # Находим локальные максимумы и минимумы
            highs = recent_df['high'].rolling(window=5, center=True).max()
            lows = recent_df['low'].rolling(window=5, center=True).min()
            
            # Локальные максимумы (потенциальные уровни сопротивления)
            resistance_levels = []
            for i in range(2, len(recent_df) - 2):
                if (recent_df['high'].iloc[i] == highs.iloc[i] and 
                    recent_df['high'].iloc[i] > recent_df['high'].iloc[i-1] and
                    recent_df['high'].iloc[i] > recent_df['high'].iloc[i+1]):
                    resistance_levels.append(recent_df['high'].iloc[i])
            
            # Локальные минимумы (потенциальные уровни поддержки)
            support_levels = []
            for i in range(2, len(recent_df) - 2):
                if (recent_df['low'].iloc[i] == lows.iloc[i] and 
                    recent_df['low'].iloc[i] < recent_df['low'].iloc[i-1] and
                    recent_df['low'].iloc[i] < recent_df['low'].iloc[i+1]):
                    support_levels.append(recent_df['low'].iloc[i])
            
            # Убираем дубликаты и сортируем
            resistance_levels = sorted(list(set(resistance_levels)), reverse=True)
            support_levels = sorted(list(set(support_levels)))
            
            # Берем самые сильные уровни
            current_price = df['close'].iloc[-1]
            
            # Ближайшие уровни сопротивления (выше текущей цены)
            resistance_above = [r for r in resistance_levels if r > current_price][:3]
            
            # Ближайшие уровни поддержки (ниже текущей цены)
            support_below = [s for s in support_levels if s < current_price][-3:]
            
            # Дополнительно: простые уровни на основе max/min
            period_high = recent_df['high'].max()
            period_low = recent_df['low'].min()
            
            return {
                'resistance_levels': resistance_above,
                'support_levels': support_below,
                'period_high': period_high,
                'period_low': period_low,
                'current_price': current_price
            }
            
        except Exception as e:
            logger.error(f"Ошибка поиска уровней: {e}")
            return {}
    
    def _calculate_indicators(self, df: pd.DataFrame) -> Dict:
        """Расчет индикаторов для breakout стратегии"""
        try:
            indicators = {}
            current_price = float(df['close'].iloc[-1])
            indicators['current_price'] = current_price
            
            if TA_AVAILABLE:
                # RSI для определения моментума
                rsi = RSIIndicator(df['close'], window=14)
                indicators['rsi'] = float(rsi.rsi().iloc[-1])
                
                # ADX для силы тренда
                adx = ADXIndicator(df['high'], df['low'], df['close'])
                indicators['adx'] = float(adx.adx().iloc[-1])
                indicators['adx_pos'] = float(adx.adx_pos().iloc[-1])
                indicators['adx_neg'] = float(adx.adx_neg().iloc[-1])
                
                # EMA для определения общего тренда
                ema_20 = EMAIndicator(df['close'], window=20)
                ema_50 = EMAIndicator(df['close'], window=50)
                indicators['ema_20'] = float(ema_20.ema_indicator().iloc[-1])
                indicators['ema_50'] = float(ema_50.ema_indicator().iloc[-1])
                
                # ATR для волатильности
                atr = AverageTrueRange(df['high'], df['low'], df['close'])
                indicators['atr'] = float(atr.average_true_range().iloc[-1])
                
                # OBV для объемного анализа (если есть объем)
                if 'volume' in df.columns:
                    obv = OnBalanceVolumeIndicator(df['close'], df['volume'])
                    indicators['obv'] = float(obv.on_balance_volume().iloc[-1])
                    indicators['obv_trend'] = self._calculate_obv_trend(obv.on_balance_volume())
                
            else:
                # Базовые вычисления без TA-Lib
                indicators['rsi'] = self._calculate_rsi(df['close'])
                indicators['ema_20'] = df['close'].ewm(span=20).mean().iloc[-1]
                indicators['ema_50'] = df['close'].ewm(span=50).mean().iloc[-1]
                indicators['atr'] = self._calculate_atr(df)
                indicators['adx'] = 30.0  # Предполагаем средний ADX
                indicators['adx_pos'] = 25.0
                indicators['adx_neg'] = 25.0
            
            # Анализ объема
            if 'volume' in df.columns:
                volume_ma = df['volume'].rolling(20).mean()
                current_volume = df['volume'].iloc[-1]
                indicators['volume_ratio'] = current_volume / volume_ma.iloc[-1]
                indicators['average_volume'] = float(volume_ma.iloc[-1])
            else:
                indicators['volume_ratio'] = 1.0
                indicators['average_volume'] = 0
            
            # Недавняя волатильность
            indicators['price_volatility'] = df['close'].pct_change().rolling(20).std().iloc[-1]
            
            # Определение тренда
            if indicators['ema_20'] > indicators['ema_50']:
                indicators['trend'] = 'UPTREND'
            elif indicators['ema_20'] < indicators['ema_50']:
                indicators['trend'] = 'DOWNTREND'
            else:
                indicators['trend'] = 'SIDEWAYS'
            
            return indicators
            
        except Exception as e:
            logger.error(f"Ошибка расчета индикаторов breakout: {e}")
            return {}
    
    def _analyze_breakouts(self, df: pd.DataFrame, levels: Dict, indicators: Dict) -> Dict:
        """Анализ потенциальных пробоев"""
        signals = {'breakout_up': [], 'breakout_down': []}
        
        try:
            current_price = indicators['current_price']
            previous_price = df['close'].iloc[-2]
            volume_ratio = indicators.get('volume_ratio', 1.0)
            
            # Проверяем пробой уровней сопротивления (восходящий пробой)
            for resistance in levels.get('resistance_levels', []):
                price_move = (current_price - resistance) / resistance
                
                if (previous_price <= resistance and current_price > resistance and 
                    price_move >= self.price_threshold):
                    
                    # Проверяем подтверждение объемом
                    volume_confirmation = volume_ratio >= self.volume_threshold
                    
                    # Проверяем моментум
                    rsi = indicators.get('rsi', 50)
                    momentum_confirmation = rsi >= self.RSI_MOMENTUM_MIN
                    
                    # Проверяем силу тренда
                    adx = indicators.get('adx', 20)
                    trend_strength = adx >= self.ADX_TREND_THRESHOLD
                    
                    confidence = 0.7
                    if volume_confirmation:
                        confidence += 0.2
                    if momentum_confirmation:
                        confidence += 0.1
                    if trend_strength:
                        confidence += 0.1
                    
                    confidence = min(confidence, 1.0)
                    
                    signals['breakout_up'].append({
                        'level': resistance,
                        'breakout_strength': price_move,
                        'volume_confirmation': volume_confirmation,
                        'confidence': confidence,
                        'reason': f'Пробой сопротивления {resistance:.4f}, движение {price_move:.2%}'
                    })
            
            # Проверяем пробой уровней поддержки (нисходящий пробой)
            for support in levels.get('support_levels', []):
                price_move = (support - current_price) / support
                
                if (previous_price >= support and current_price < support and 
                    price_move >= self.price_threshold):
                    
                    volume_confirmation = volume_ratio >= self.volume_threshold
                    
                    rsi = indicators.get('rsi', 50)
                    momentum_confirmation = rsi <= self.RSI_MOMENTUM_MAX
                    
                    adx = indicators.get('adx', 20)
                    trend_strength = adx >= self.ADX_TREND_THRESHOLD
                    
                    confidence = 0.7
                    if volume_confirmation:
                        confidence += 0.2
                    if momentum_confirmation:
                        confidence += 0.1
                    if trend_strength:
                        confidence += 0.1
                    
                    confidence = min(confidence, 1.0)
                    
                    signals['breakout_down'].append({
                        'level': support,
                        'breakout_strength': price_move,
                        'volume_confirmation': volume_confirmation,
                        'confidence': confidence,
                        'reason': f'Пробой поддержки {support:.4f}, движение {price_move:.2%}'
                    })
            
            # Также проверяем пробой периодических максимумов/минимумов
            period_high = levels.get('period_high', 0)
            period_low = levels.get('period_low', float('inf'))
            
            # Пробой периодического максимума
            if current_price > period_high and volume_ratio >= self.volume_threshold:
                confidence = 0.8 if volume_ratio >= 2.0 else 0.6
                signals['breakout_up'].append({
                    'level': period_high,
                    'breakout_strength': (current_price - period_high) / period_high,
                    'volume_confirmation': True,
                    'confidence': confidence,
                    'reason': f'Пробой периодического максимума {period_high:.4f}'
                })
            
            # Пробой периодического минимума
            if current_price < period_low and volume_ratio >= self.volume_threshold:
                confidence = 0.8 if volume_ratio >= 2.0 else 0.6
                signals['breakout_down'].append({
                    'level': period_low,
                    'breakout_strength': (period_low - current_price) / period_low,
                    'volume_confirmation': True,
                    'confidence': confidence,
                    'reason': f'Пробой периодического минимума {period_low:.4f}'
                })
            
            return signals
            
        except Exception as e:
            logger.error(f"Ошибка анализа пробоев: {e}")
            return signals
    
    def _make_decision(self, breakout_signals: Dict, indicators: Dict, 
                      levels: Dict, df: pd.DataFrame) -> TradingSignal:
        """Принятие решения для breakout стратегии"""
        try:
            current_price = indicators['current_price']
            atr = indicators['atr']
            trend = indicators.get('trend', 'SIDEWAYS')
            
            # Анализируем восходящие пробои
            breakout_up = breakout_signals.get('breakout_up', [])
            breakout_down = breakout_signals.get('breakout_down', [])
            
            # BUY сигнал (восходящий пробой)
            if breakout_up:
                # Берем самый сильный сигнал
                best_signal = max(breakout_up, key=lambda x: x['confidence'])
                
                # Дополнительная проверка: пробой должен соответствовать тренду
                trend_alignment = trend in ['UPTREND', 'SIDEWAYS']
                
                final_confidence = best_signal['confidence']
                if trend_alignment:
                    final_confidence *= 1.1
                else:
                    final_confidence *= 0.8
                
                final_confidence = min(final_confidence, 1.0)
                
                if final_confidence >= self.min_confidence:
                    # Расчет уровней
                    stop_loss = self.calculate_stop_loss(current_price, 'BUY', atr)
                    # Для breakout используем более консервативный stop loss
                    stop_loss = max(stop_loss, best_signal['level'] * 0.98)
                    
                    take_profit = self.calculate_take_profit(current_price, 'BUY', atr)
                    
                    reason = f"BREAKOUT_BUY: {best_signal['reason']}, тренд={trend}"
                    
                    return TradingSignal(
                        action='BUY',
                        confidence=final_confidence,
                        price=current_price,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        reason=reason,
                        risk_reward_ratio=(take_profit - current_price) / (current_price - stop_loss),
                        indicators=indicators
                    )
            
            # SELL сигнал (нисходящий пробой)
            if breakout_down:
                best_signal = max(breakout_down, key=lambda x: x['confidence'])
                
                trend_alignment = trend in ['DOWNTREND', 'SIDEWAYS']
                
                final_confidence = best_signal['confidence']
                if trend_alignment:
                    final_confidence *= 1.1
                else:
                    final_confidence *= 0.8
                
                final_confidence = min(final_confidence, 1.0)
                
                if final_confidence >= self.min_confidence:
                    stop_loss = self.calculate_stop_loss(current_price, 'SELL', atr)
                    stop_loss = min(stop_loss, best_signal['level'] * 1.02)
                    
                    take_profit = self.calculate_take_profit(current_price, 'SELL', atr)
                    
                    reason = f"BREAKOUT_SELL: {best_signal['reason']}, тренд={trend}"
                    
                    return TradingSignal(
                        action='SELL',
                        confidence=final_confidence,
                        price=current_price,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        reason=reason,
                        risk_reward_ratio=(current_price - take_profit) / (stop_loss - current_price),
                        indicators=indicators
                    )
            
            # WAIT
            breakout_count = len(breakout_up) + len(breakout_down)
            reason = f"WAIT: пробоев={breakout_count}, тренд={trend}, недостаточная уверенность"
            
            return TradingSignal(
                action='WAIT',
                confidence=0.0,
                price=current_price,
                reason=reason,
                indicators=indicators
            )
            
        except Exception as e:
            logger.error(f"Ошибка принятия решения breakout: {e}")
            return TradingSignal('WAIT', 0, 0, reason=f'Ошибка решения: {e}')
    
    # Вспомогательные методы
    def _calculate_obv_trend(self, obv_series):
        """Определение тренда OBV"""
        if len(obv_series) < 10:
            return 'NEUTRAL'
        
        recent_obv = obv_series.tail(10)
        if recent_obv.iloc[-1] > recent_obv.iloc[0]:
            return 'RISING'
        elif recent_obv.iloc[-1] < recent_obv.iloc[0]:
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
    
    def _calculate_atr(self, df, period=14):
        """ATR без TA-Lib"""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        return float(atr.iloc[-1]) if not atr.empty else 0.01