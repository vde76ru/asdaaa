"""
Мульти-индикаторная стратегия
Путь: /var/www/www-root/data/www/systemetech.ru/src/strategies/multi_indicator.py
"""
import pandas as pd
import numpy as np
from typing import Dict  # ✅ ИСПРАВЛЕНО: добавлен импорт Dict
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import EMAIndicator, MACD, ADXIndicator
from ta.volatility import BollingerBands, AverageTrueRange
from ta.volume import OnBalanceVolumeIndicator
import logging
from typing import Dict

from .base import BaseStrategy
from ..common.types import UnifiedTradingSignal as TradingSignal

logger = logging.getLogger(__name__)

class MultiIndicatorStrategy(BaseStrategy):
    """
    Продвинутая стратегия с множественными индикаторами
    Использует подтверждение от нескольких индикаторов
    """
    
    # ✅ УЛУЧШЕНИЕ: Константы для лучшей читаемости
    RSI_OVERSOLD = 30
    RSI_OVERBOUGHT = 70
    STOCH_OVERSOLD = 20
    STOCH_OVERBOUGHT = 80
    ADX_TREND_THRESHOLD = 25
    VOLUME_RATIO_THRESHOLD = 1.5
    BB_LOWER_THRESHOLD = 0.2
    BB_UPPER_THRESHOLD = 0.8
    
    def __init__(self):
        super().__init__("multi_indicator")
        self.min_confidence = 0.65
        self.min_indicators_confirm = 3  # Минимум 3 индикатора должны подтвердить
    
    async def analyze(self, df: pd.DataFrame, symbol: str) -> TradingSignal:
        """Комплексный анализ с множественными подтверждениями"""
        
        if not self.validate_dataframe(df):
            return TradingSignal('WAIT', 0, 0, reason='Недостаточно данных')
        
        try:
            # Рассчитываем все индикаторы
            indicators = self._calculate_indicators(df)
            
            # ✅ УЛУЧШЕНИЕ: Проверяем корректность индикаторов
            if not indicators:
                return TradingSignal('WAIT', 0, 0, reason='Ошибка расчета индикаторов')
            
            # Анализируем сигналы от каждого индикатора
            signals = self._analyze_signals(indicators, df)
            
            # Принимаем решение на основе всех сигналов
            return self._make_decision(signals, indicators, df)
            
        except Exception as e:
            logger.error(f"Ошибка анализа {symbol}: {e}")
            return TradingSignal('WAIT', 0, 0, reason=f'Ошибка анализа: {e}')
    
    def _calculate_indicators(self, df: pd.DataFrame) -> Dict:
        """Расчет всех индикаторов"""
        try:
            indicators = {}
            
            # Последние значения
            current_price = float(df['close'].iloc[-1])
            indicators['current_price'] = current_price
            
            # RSI
            rsi = RSIIndicator(df['close'], window=self.rsi_period)
            indicators['rsi'] = float(rsi.rsi().iloc[-1])
            
            # MACD
            macd = MACD(df['close'])
            indicators['macd'] = float(macd.macd().iloc[-1])
            indicators['macd_signal'] = float(macd.macd_signal().iloc[-1])
            indicators['macd_diff'] = float(macd.macd_diff().iloc[-1])
            
            # Bollinger Bands
            bb = BollingerBands(df['close'], window=20, window_dev=2)
            indicators['bb_upper'] = float(bb.bollinger_hband().iloc[-1])
            indicators['bb_lower'] = float(bb.bollinger_lband().iloc[-1])
            indicators['bb_middle'] = float(bb.bollinger_mavg().iloc[-1])
            indicators['bb_percent'] = float(bb.bollinger_pband().iloc[-1])
            
            # EMA
            ema_9 = EMAIndicator(df['close'], window=9)
            ema_21 = EMAIndicator(df['close'], window=21)
            ema_50 = EMAIndicator(df['close'], window=50)
            indicators['ema_9'] = float(ema_9.ema_indicator().iloc[-1])
            indicators['ema_21'] = float(ema_21.ema_indicator().iloc[-1])
            indicators['ema_50'] = float(ema_50.ema_indicator().iloc[-1])
            
            # ADX
            adx = ADXIndicator(df['high'], df['low'], df['close'])
            indicators['adx'] = float(adx.adx().iloc[-1])
            indicators['adx_pos'] = float(adx.adx_pos().iloc[-1])
            indicators['adx_neg'] = float(adx.adx_neg().iloc[-1])
            
            # ATR для stop loss
            atr = AverageTrueRange(df['high'], df['low'], df['close'])
            indicators['atr'] = float(atr.average_true_range().iloc[-1])
            
            # Stochastic
            stoch = StochasticOscillator(df['high'], df['low'], df['close'])
            indicators['stoch_k'] = float(stoch.stoch().iloc[-1])
            indicators['stoch_d'] = float(stoch.stoch_signal().iloc[-1])
            
            # Volume analysis
            if 'volume' in df.columns:
                volume_ratio = df['volume'].iloc[-1] / df['volume'].rolling(20).mean().iloc[-1]
                indicators['volume_ratio'] = float(volume_ratio)
            else:
                indicators['volume_ratio'] = 1.0
                
            return indicators
            
        except Exception as e:
            logger.error(f"Ошибка расчета индикаторов: {e}")
            return {}

    
    def _calculate_ema_safely(self, df: pd.DataFrame, indicators: Dict):
        """✅ НОВОЕ: Безопасный расчет EMA"""
        try:
            periods = [9, 21, 50, 200]
            for period in periods:
                if len(df) >= period:
                    ema_indicator = EMAIndicator(df['close'], window=period)
                    ema_values = ema_indicator.ema_indicator()
                    indicators[f'ema_{period}'] = ema_values.iloc[-1] if not ema_values.empty else df['close'].iloc[-1]
                else:
                    indicators[f'ema_{period}'] = df['close'].iloc[-1]
        except Exception as e:
            logger.error(f"Ошибка расчета EMA: {e}")
            # Используем текущую цену как fallback
            for period in [9, 21, 50, 200]:
                indicators[f'ema_{period}'] = df['close'].iloc[-1]
    
    def _calculate_adx_safely(self, df: pd.DataFrame, indicators: Dict):
        """✅ НОВОЕ: Безопасный расчет ADX"""
        try:
            if len(df) >= 14:  # ADX требует минимум 14 периодов
                adx = ADXIndicator(df['high'], df['low'], df['close'])
                adx_values = adx.adx()
                adx_pos_values = adx.adx_pos()
                adx_neg_values = adx.adx_neg()
                
                indicators['adx'] = adx_values.iloc[-1] if not adx_values.empty else 0.0
                indicators['adx_pos'] = adx_pos_values.iloc[-1] if not adx_pos_values.empty else 0.0
                indicators['adx_neg'] = adx_neg_values.iloc[-1] if not adx_neg_values.empty else 0.0
            else:
                indicators['adx'] = 0.0
                indicators['adx_pos'] = 0.0
                indicators['adx_neg'] = 0.0
        except Exception as e:
            logger.error(f"Ошибка расчета ADX: {e}")
            indicators['adx'] = 0.0
            indicators['adx_pos'] = 0.0
            indicators['adx_neg'] = 0.0
    
    def _calculate_volume_safely(self, df: pd.DataFrame, indicators: Dict):
        """✅ НОВОЕ: Безопасный расчет объемных индикаторов"""
        try:
            if len(df) >= 20:
                volume_sma = df['volume'].rolling(window=20).mean()
                indicators['volume_sma'] = volume_sma.iloc[-1] if not volume_sma.empty else df['volume'].iloc[-1]
                
                if indicators['volume_sma'] > 0:
                    indicators['volume_ratio'] = df['volume'].iloc[-1] / indicators['volume_sma']
                else:
                    indicators['volume_ratio'] = 1.0
            else:
                indicators['volume_sma'] = df['volume'].mean()
                indicators['volume_ratio'] = 1.0
        except Exception as e:
            logger.error(f"Ошибка расчета объемных индикаторов: {e}")
            indicators['volume_sma'] = df['volume'].iloc[-1] if len(df) > 0 else 1.0
            indicators['volume_ratio'] = 1.0
    
    def _calculate_stochastic_safely(self, df: pd.DataFrame, indicators: Dict):
        """✅ НОВОЕ: Безопасный расчет Stochastic"""
        try:
            if len(df) >= 14:  # Stochastic требует минимум 14 периодов
                stoch = StochasticOscillator(df['high'], df['low'], df['close'])
                stoch_k_values = stoch.stoch()
                stoch_d_values = stoch.stoch_signal()
                
                indicators['stoch_k'] = stoch_k_values.iloc[-1] if not stoch_k_values.empty else 50.0
                indicators['stoch_d'] = stoch_d_values.iloc[-1] if not stoch_d_values.empty else 50.0
            else:
                indicators['stoch_k'] = 50.0
                indicators['stoch_d'] = 50.0
        except Exception as e:
            logger.error(f"Ошибка расчета Stochastic: {e}")
            indicators['stoch_k'] = 50.0
            indicators['stoch_d'] = 50.0
    
    def _analyze_signals(self, indicators: Dict, df: pd.DataFrame) -> Dict:
        """Анализ сигналов от каждого индикатора"""
        signals = {
            'buy_signals': [],
            'sell_signals': [],
            'neutral_signals': []
        }
        
        try:
            # RSI сигналы
            if indicators['rsi'] < self.RSI_OVERSOLD:
                signals['buy_signals'].append(('RSI', 'Перепроданность', 0.8))
            elif indicators['rsi'] > self.RSI_OVERBOUGHT:
                signals['sell_signals'].append(('RSI', 'Перекупленность', 0.8))
                
            # MACD сигналы
            if indicators['macd'] > indicators['macd_signal'] and indicators['macd_diff'] > 0:
                signals['buy_signals'].append(('MACD', 'Бычий пересечение + растущий гистограмма', 0.7))
            elif indicators['macd'] < indicators['macd_signal'] and indicators['macd_diff'] < 0:
                signals['sell_signals'].append(('MACD', 'Медвежий пересечение + падающий гистограмма', 0.7))
                
            # Bollinger Bands сигналы
            if indicators['bb_percent'] < self.BB_LOWER_THRESHOLD:  # Касание нижней полосы
                signals['buy_signals'].append(('BB', 'Касание нижней полосы', 0.6))
            elif indicators['bb_percent'] > self.BB_UPPER_THRESHOLD:  # Касание верхней полосы  
                signals['sell_signals'].append(('BB', 'Касание верхней полосы', 0.6))
                
            # EMA тренд
            if (indicators['ema_9'] > indicators['ema_21'] > indicators['ema_50'] and 
                indicators['current_price'] > indicators['ema_9']):
                signals['buy_signals'].append(('EMA', 'Восходящий тренд', 0.7))
            elif (indicators['ema_9'] < indicators['ema_21'] < indicators['ema_50'] and 
                  indicators['current_price'] < indicators['ema_9']):
                signals['sell_signals'].append(('EMA', 'Нисходящий тренд', 0.7))
                
            # ADX сила тренда
            if indicators['adx'] > self.ADX_TREND_THRESHOLD:
                if indicators['adx_pos'] > indicators['adx_neg']:
                    signals['buy_signals'].append(('ADX', 'Сильный восходящий тренд', 0.6))
                else:
                    signals['sell_signals'].append(('ADX', 'Сильный нисходящий тренд', 0.6))
                    
            # Volume подтверждение
            if indicators['volume_ratio'] > self.VOLUME_RATIO_THRESHOLD:
                signals['neutral_signals'].append(('Volume', 'Высокий объем', 0.5))
                
            # Stochastic сигналы
            if indicators['stoch_k'] < self.STOCH_OVERSOLD and indicators['stoch_k'] > indicators['stoch_d']:
                signals['buy_signals'].append(('Stochastic', 'Перепроданность + пересечение', 0.6))
            elif indicators['stoch_k'] > self.STOCH_OVERBOUGHT and indicators['stoch_k'] < indicators['stoch_d']:
                signals['sell_signals'].append(('Stochastic', 'Перекупленность + пересечение', 0.6))
                
            return signals
            
        except Exception as e:
            logger.error(f"Ошибка анализа сигналов: {e}")
            return signals
    
    def _make_decision(self, signals: Dict, indicators: Dict, df: pd.DataFrame) -> TradingSignal:
        """Принятие решения на основе всех сигналов"""
        try:
            buy_score = sum(signal[2] for signal in signals['buy_signals'])
            sell_score = sum(signal[2] for signal in signals['sell_signals'])
            
            buy_count = len(signals['buy_signals'])
            sell_count = len(signals['sell_signals'])
            
            current_price = indicators['current_price']
            atr = indicators['atr']
            
            # Проверяем минимальное количество подтверждений
            if buy_count >= self.min_indicators_confirm and buy_score > sell_score:
                # Расчет уровней
                stop_loss = self.calculate_stop_loss(current_price, 'BUY', atr)
                take_profit = self.calculate_take_profit(current_price, 'BUY', atr)
                
                confidence = min(buy_score / 5.0, 1.0)  # Нормализуем уверенность
                
                # Проверяем минимальную уверенность
                if confidence >= self.min_confidence:
                    reasons = [f"{signal[0]}: {signal[1]}" for signal in signals['buy_signals']]
                    reason = "BUY: " + "; ".join(reasons)
                    
                    return TradingSignal(
                        action='BUY',
                        confidence=confidence,
                        price=current_price,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        reason=reason,
                        risk_reward_ratio=(take_profit - current_price) / (current_price - stop_loss),
                        indicators=indicators
                    )
                    
            elif sell_count >= self.min_indicators_confirm and sell_score > buy_score:
                # Расчет уровней для SELL
                stop_loss = self.calculate_stop_loss(current_price, 'SELL', atr)
                take_profit = self.calculate_take_profit(current_price, 'SELL', atr)
                
                confidence = min(sell_score / 5.0, 1.0)
                
                if confidence >= self.min_confidence:
                    reasons = [f"{signal[0]}: {signal[1]}" for signal in signals['sell_signals']]
                    reason = "SELL: " + "; ".join(reasons)
                    
                    return TradingSignal(
                        action='SELL',
                        confidence=confidence,
                        price=current_price,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        reason=reason,
                        risk_reward_ratio=(current_price - take_profit) / (stop_loss - current_price),
                        indicators=indicators
                    )
            
            # Если нет четкого сигнала
            reason = f"WAIT: buy_signals={buy_count}, sell_signals={sell_count}, confidence={max(buy_score, sell_score):.2f}"
            return TradingSignal(
                action='WAIT',
                confidence=0.0,
                price=current_price,
                reason=reason,
                indicators=indicators
            )
            
        except Exception as e:
            logger.error(f"Ошибка принятия решения: {e}")
            return TradingSignal(
                action='WAIT',
                confidence=0.0,
                price=current_price if 'current_price' in indicators else 0,
                reason=f"Ошибка анализа: {e}"
            )
            
            
    def validate_dataframe(self, df: pd.DataFrame) -> bool:
        """Расширенная валидация данных"""
        if df is None or df.empty:
            logger.warning("DataFrame пустой")
            return False
            
        required_columns = ['open', 'high', 'low', 'close']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            logger.warning(f"Отсутствуют колонки: {missing_columns}")
            return False
            
        if len(df) < 200:  # Нужно больше данных для надежности индикаторов
            logger.warning(f"Недостаточно данных: {len(df)} < 200")
            return False
            
        # Проверяем на NaN
        if df[required_columns].isnull().any().any():
            logger.warning("Обнаружены NaN значения в данных")
            return False
            
        # Проверяем логику цен
        if not (df['low'] <= df['close']).all() or not (df['close'] <= df['high']).all():
            logger.warning("Нарушена логика цен: low <= close <= high")
            return False
            
        return True