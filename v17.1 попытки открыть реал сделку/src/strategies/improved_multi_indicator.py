"""
✅ УЛУЧШЕННАЯ стратегия с обработкой математических ошибок
"""
import pandas as pd
import numpy as np
import ta
import logging
from typing import Optional, NamedTuple

logger = logging.getLogger(__name__)

class AnalysisResult(NamedTuple):
    """📊 Результат анализа торговой стратегии"""
    action: str  # 'BUY', 'SELL', 'WAIT'
    confidence: float  # Уверенность в сигнале (0.0 - 1.0)
    reason: str  # Объяснение почему принято решение
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

class ImprovedMultiIndicatorStrategy:
    """
    🚀 Улучшенная мультииндикаторная стратегия
    
    Особенности:
    - ✅ Обработка математических ошибок
    - ✅ Фильтрация некорректных данных
    - ✅ Детальное логирование
    - ✅ Защита от деления на ноль
    """
    
    def __init__(self):
        self.name = "improved_multi_indicator"
        
        # Параметры стратегии
        self.rsi_period = 14
        self.rsi_oversold = 30
        self.rsi_overbought = 70
        
        self.ma_short_period = 10
        self.ma_long_period = 50
        
        self.bb_period = 20
        self.bb_std = 2
        
        # Минимальная уверенность для сигнала
        self.min_confidence = 0.6
    
    def analyze(self, df: pd.DataFrame) -> AnalysisResult:
        """
        📈 Основная функция анализа
        
        Параметры:
        - df: DataFrame с колонками [timestamp, open, high, low, close, volume]
        
        Возвращает:
        - AnalysisResult с рекомендацией и уверенностью
        """
        try:
            # 1. Проверяем корректность данных
            if not self._validate_data(df):
                return AnalysisResult('WAIT', 0.0, 'Некорректные исходные данные')
            
            # 2. Вычисляем технические индикаторы
            indicators = self._calculate_indicators(df)
            
            if not indicators:
                return AnalysisResult('WAIT', 0.0, 'Ошибка вычисления индикаторов')
            
            # 3. Анализируем сигналы
            signals = self._analyze_signals(indicators, df)
            
            # 4. Принимаем решение
            decision = self._make_decision(signals)
            
            return decision
            
        except Exception as e:
            logger.error(f"❌ Ошибка анализа стратегии: {e}")
            return AnalysisResult('WAIT', 0.0, f'Ошибка анализа: {str(e)}')
    
    def _validate_data(self, df: pd.DataFrame) -> bool:
        """
        ✅ Проверка корректности входных данных
        """
        try:
            # Проверяем наличие необходимых колонок
            required_columns = ['open', 'high', 'low', 'close', 'volume']
            if not all(col in df.columns for col in required_columns):
                logger.error(f"❌ Отсутствуют необходимые колонки: {required_columns}")
                return False
            
            # Проверяем количество данных
            if len(df) < self.ma_long_period + 10:
                logger.warning(f"⚠️ Недостаточно данных: {len(df)}, нужно минимум {self.ma_long_period + 10}")
                return False
            
            # Проверяем на NaN и некорректные значения
            if df[required_columns].isnull().any().any():
                logger.warning("⚠️ Обнаружены пустые значения в данных")
                return False
            
            # Проверяем что цены положительные
            if (df[['open', 'high', 'low', 'close']] <= 0).any().any():
                logger.error("❌ Обнаружены отрицательные или нулевые цены")
                return False
            
            # Проверяем логику цен (high >= low, etc.)
            if not ((df['high'] >= df['low']) & 
                   (df['high'] >= df['open']) & 
                   (df['high'] >= df['close']) &
                   (df['low'] <= df['open']) & 
                   (df['low'] <= df['close'])).all():
                logger.error("❌ Нарушена логика OHLC данных")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка валидации данных: {e}")
            return False
    
    def _calculate_indicators(self, df: pd.DataFrame) -> Optional[dict]:
        """
        🧮 Вычисление технических индикаторов с защитой от ошибок
        """
        try:
            indicators = {}
            
            # Подавляем предупреждения numpy на время вычислений
            with np.errstate(divide='ignore', invalid='ignore'):
                
                # 1. RSI (Индекс относительной силы)
                try:
                    rsi_values = ta.momentum.rsi(df['close'], window=self.rsi_period)
                    indicators['rsi'] = self._clean_series(rsi_values)
                    indicators['rsi_current'] = indicators['rsi'].iloc[-1] if not indicators['rsi'].empty else np.nan
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка вычисления RSI: {e}")
                    indicators['rsi'] = pd.Series([np.nan] * len(df))
                    indicators['rsi_current'] = np.nan
                
                # 2. Скользящие средние
                try:
                    indicators['ma_short'] = self._clean_series(df['close'].rolling(window=self.ma_short_period).mean())
                    indicators['ma_long'] = self._clean_series(df['close'].rolling(window=self.ma_long_period).mean())
                    indicators['ma_short_current'] = indicators['ma_short'].iloc[-1] if not indicators['ma_short'].empty else np.nan
                    indicators['ma_long_current'] = indicators['ma_long'].iloc[-1] if not indicators['ma_long'].empty else np.nan
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка вычисления MA: {e}")
                    indicators.update({
                        'ma_short': pd.Series([np.nan] * len(df)),
                        'ma_long': pd.Series([np.nan] * len(df)),
                        'ma_short_current': np.nan,
                        'ma_long_current': np.nan
                    })
                
                # 3. Полосы Боллинджера
                try:
                    bb = ta.volatility.BollingerBands(df['close'], window=self.bb_period, window_dev=self.bb_std)
                    indicators['bb_upper'] = self._clean_series(bb.bollinger_hband())
                    indicators['bb_lower'] = self._clean_series(bb.bollinger_lband())
                    indicators['bb_middle'] = self._clean_series(bb.bollinger_mavg())
                    
                    indicators['bb_upper_current'] = indicators['bb_upper'].iloc[-1] if not indicators['bb_upper'].empty else np.nan
                    indicators['bb_lower_current'] = indicators['bb_lower'].iloc[-1] if not indicators['bb_lower'].empty else np.nan
                    indicators['bb_middle_current'] = indicators['bb_middle'].iloc[-1] if not indicators['bb_middle'].empty else np.nan
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка вычисления Bollinger Bands: {e}")
                    indicators.update({
                        'bb_upper': pd.Series([np.nan] * len(df)),
                        'bb_lower': pd.Series([np.nan] * len(df)),
                        'bb_middle': pd.Series([np.nan] * len(df)),
                        'bb_upper_current': np.nan,
                        'bb_lower_current': np.nan,
                        'bb_middle_current': np.nan
                    })
                
                # 4. MACD
                try:
                    macd = ta.trend.MACD(df['close'])
                    indicators['macd'] = self._clean_series(macd.macd())
                    indicators['macd_signal'] = self._clean_series(macd.macd_signal())
                    indicators['macd_histogram'] = self._clean_series(macd.macd_diff())
                    
                    indicators['macd_current'] = indicators['macd'].iloc[-1] if not indicators['macd'].empty else np.nan
                    indicators['macd_signal_current'] = indicators['macd_signal'].iloc[-1] if not indicators['macd_signal'].empty else np.nan
                    indicators['macd_histogram_current'] = indicators['macd_histogram'].iloc[-1] if not indicators['macd_histogram'].empty else np.nan
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка вычисления MACD: {e}")
                    indicators.update({
                        'macd': pd.Series([np.nan] * len(df)),
                        'macd_signal': pd.Series([np.nan] * len(df)),
                        'macd_histogram': pd.Series([np.nan] * len(df)),
                        'macd_current': np.nan,
                        'macd_signal_current': np.nan,
                        'macd_histogram_current': np.nan
                    })
            
            # Добавляем текущую цену
            indicators['current_price'] = df['close'].iloc[-1]
            
            # Проверяем что получили хотя бы какие-то данные
            valid_indicators = sum(1 for key, value in indicators.items() 
                                 if 'current' in key and not pd.isna(value))
            
            if valid_indicators < 2:
                logger.warning(f"⚠️ Слишком мало корректных индикаторов: {valid_indicators}")
                return None
            
            return indicators
            
        except Exception as e:
            logger.error(f"❌ Критическая ошибка вычисления индикаторов: {e}")
            return None
    
    def _clean_series(self, series: pd.Series) -> pd.Series:
        """
        🧹 Очистка временного ряда от некорректных значений
        """
        try:
            # Заменяем inf на NaN
            series = series.replace([np.inf, -np.inf], np.nan)
            
            # Удаляем выбросы (значения более чем в 1000 раз больше медианы)
            if not series.dropna().empty:
                median_val = series.median()
                if not pd.isna(median_val) and median_val > 0:
                    outlier_threshold = median_val * 1000
                    series = series.where(series < outlier_threshold, np.nan)
            
            return series
            
        except Exception as e:
            logger.warning(f"⚠️ Ошибка очистки данных: {e}")
            return series
    
    def _analyze_signals(self, indicators: dict, df: pd.DataFrame) -> dict:
        """
        🔍 Анализ торговых сигналов
        """
        signals = {
            'rsi_signal': 0,      # -1: продажа, 0: нейтрально, 1: покупка
            'ma_signal': 0,
            'bb_signal': 0,
            'macd_signal': 0,
            'reasons': []
        }
        
        try:
            current_price = indicators['current_price']
            
            # 1. Анализ RSI
            rsi_current = indicators.get('rsi_current', np.nan)
            if not pd.isna(rsi_current):
                if rsi_current <= self.rsi_oversold:
                    signals['rsi_signal'] = 1
                    signals['reasons'].append(f'RSI в зоне перепроданности ({rsi_current:.1f})')
                elif rsi_current >= self.rsi_overbought:
                    signals['rsi_signal'] = -1
                    signals['reasons'].append(f'RSI в зоне перекупленности ({rsi_current:.1f})')
            
            # 2. Анализ скользящих средних
            ma_short = indicators.get('ma_short_current', np.nan)
            ma_long = indicators.get('ma_long_current', np.nan)
            if not pd.isna(ma_short) and not pd.isna(ma_long):
                if ma_short > ma_long and current_price > ma_short:
                    signals['ma_signal'] = 1
                    signals['reasons'].append('Цена выше восходящих MA')
                elif ma_short < ma_long and current_price < ma_short:
                    signals['ma_signal'] = -1
                    signals['reasons'].append('Цена ниже нисходящих MA')
            
            # 3. Анализ полос Боллинджера
            bb_upper = indicators.get('bb_upper_current', np.nan)
            bb_lower = indicators.get('bb_lower_current', np.nan)
            if not pd.isna(bb_upper) and not pd.isna(bb_lower):
                if current_price <= bb_lower:
                    signals['bb_signal'] = 1
                    signals['reasons'].append('Цена у нижней полосы Боллинджера')
                elif current_price >= bb_upper:
                    signals['bb_signal'] = -1
                    signals['reasons'].append('Цена у верхней полосы Боллинджера')
            
            # 4. Анализ MACD
            macd_current = indicators.get('macd_current', np.nan)
            macd_signal_current = indicators.get('macd_signal_current', np.nan)
            if not pd.isna(macd_current) and not pd.isna(macd_signal_current):
                if macd_current > macd_signal_current:
                    signals['macd_signal'] = 1
                    signals['reasons'].append('MACD выше сигнальной линии')
                elif macd_current < macd_signal_current:
                    signals['macd_signal'] = -1
                    signals['reasons'].append('MACD ниже сигнальной линии')
            
            return signals
            
        except Exception as e:
            logger.error(f"❌ Ошибка анализа сигналов: {e}")
            return signals
    
    def _make_decision(self, signals: dict) -> AnalysisResult:
        """
        🎯 Принятие финального решения на основе всех сигналов
        """
        try:
            # Подсчитываем общий сигнал
            total_signal = (signals['rsi_signal'] + 
                          signals['ma_signal'] + 
                          signals['bb_signal'] + 
                          signals['macd_signal'])
            
            # Подсчитываем количество активных индикаторов
            active_indicators = sum(1 for signal in [signals['rsi_signal'], 
                                                   signals['ma_signal'], 
                                                   signals['bb_signal'], 
                                                   signals['macd_signal']] 
                                  if signal != 0)
            
            if active_indicators == 0:
                return AnalysisResult('WAIT', 0.0, 'Нет активных сигналов')
            
            # Рассчитываем уверенность (0.0 - 1.0)
            max_possible_signal = active_indicators
            confidence = abs(total_signal) / max_possible_signal if max_possible_signal > 0 else 0.0
            
            # Определяем действие
            if total_signal >= 2 and confidence >= self.min_confidence:
                action = 'BUY'
            elif total_signal <= -2 and confidence >= self.min_confidence:
                action = 'SELL'
            else:
                action = 'WAIT'
            
            # Формируем причину
            reason = '; '.join(signals['reasons']) if signals['reasons'] else 'Нет конкретных причин'
            if action == 'WAIT':
                reason = f'Недостаточно сигналов (сила: {total_signal}, уверенность: {confidence:.2f})'
            
            return AnalysisResult(
                action=action,
                confidence=confidence,
                reason=reason
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка принятия решения: {e}")
            return AnalysisResult('WAIT', 0.0, f'Ошибка принятия решения: {str(e)}')