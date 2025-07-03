"""
Momentum стратегия - ИСПРАВЛЕННАЯ ВЕРСИЯ
Файл: src/strategies/momentum.py
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional
import logging

try:
    from ta.momentum import RSIIndicator, ROCIndicator
    from ta.trend import EMAIndicator
    from ta.volatility import AverageTrueRange
    TA_AVAILABLE = True
except ImportError:
    TA_AVAILABLE = False
    logging.warning("⚠️ TA-Lib не установлен, используем ручные реализации")

from .base import BaseStrategy
from ..common.types import UnifiedTradingSignal as TradingSignal

logger = logging.getLogger(__name__)

class MomentumStrategy(BaseStrategy):
    """
    Улучшенная momentum стратегия - ИСПРАВЛЕННАЯ ВЕРСИЯ
    Торгует по направлению сильного движения с защитой от ошибок
    
    ИСПРАВЛЕНИЯ:
    - Правильная инициализация с новым BaseStrategy
    - Обработка отсутствия TA-Lib
    - Улучшенная обработка ошибок
    """
    
    # Константы стратегии
    PRICE_CHANGE_THRESHOLD_5D = 1.0
    PRICE_CHANGE_THRESHOLD_10D = 2.0
    ROC_BULLISH_THRESHOLD = 2.0
    ROC_BEARISH_THRESHOLD = -2.0
    VOLUME_RATIO_THRESHOLD = 1.5
    RSI_NEUTRAL = 50
    
    # Метаинформация для фабрики
    STRATEGY_TYPE = 'momentum'
    RISK_LEVEL = 'medium'
    TIMEFRAMES = ['1h', '4h', '1d']
    
    def __init__(self, strategy_name: str = "momentum", config: Optional[Dict] = None):
        """
        Инициализация momentum стратегии
        
        Args:
            strategy_name: Название стратегии
            config: Конфигурация стратегии
        """
        # ✅ ИСПРАВЛЕНИЕ: Правильный вызов родительского конструктора
        super().__init__(strategy_name, config)
        
        # Специфичные для momentum настройки
        self.rsi_period = self.config.get('rsi_period', 14)
        self.ema_fast = self.config.get('ema_fast', 9)
        self.ema_slow = self.config.get('ema_slow', 21)
        self.roc_period = self.config.get('roc_period', 10)
        self.min_momentum_score = self.config.get('min_momentum_score', 0.6)
        
        logger.debug(f"✅ MomentumStrategy инициализирована: {self.name}")
        
    async def analyze(self, df: pd.DataFrame, symbol: str) -> TradingSignal:
        """Анализ momentum с улучшенной обработкой ошибок"""
        
        if not self.validate_dataframe(df):
            return TradingSignal('WAIT', 0, 0, reason='Недостаточно данных')
        
        try:
            # Рассчитываем индикаторы
            indicators = self._calculate_indicators(df)
            
            # Проверяем корректность данных
            if not indicators:
                return TradingSignal('WAIT', 0, 0, reason='Ошибка расчета индикаторов')
            
            # Анализируем momentum
            momentum_score = self._analyze_momentum(indicators)
            
            # Принимаем решение
            return self._make_decision(momentum_score, indicators, df)
            
        except Exception as e:
            logger.error(f"❌ Ошибка анализа momentum для {symbol}: {e}")
            return TradingSignal('WAIT', 0, 0, reason=f'Ошибка анализа: {e}')
    
    async def _calculate_indicators(self, df: pd.DataFrame) -> Dict:
        """Улучшенный расчет индикаторов с защитой от ошибок"""
        
        try:
            current_price = df['close'].iloc[-1]
            indicators = {
                'current_price': current_price,
                'timestamp': datetime.utcnow()
            }
            
            # === PRICE MOMENTUM ===
            # Краткосрочный momentum (5 периодов)
            if len(df) >= 5:
                price_5d_ago = df['close'].iloc[-5]
                indicators['price_change_5d'] = ((current_price - price_5d_ago) / price_5d_ago) * 100
            else:
                indicators['price_change_5d'] = 0
            
            # Среднесрочный momentum (10 периодов)  
            if len(df) >= 10:
                price_10d_ago = df['close'].iloc[-10]
                indicators['price_change_10d'] = ((current_price - price_10d_ago) / price_10d_ago) * 100
            else:
                indicators['price_change_10d'] = 0
                
            # === MOVING AVERAGES ===
            # Быстрая EMA
            if TA_AVAILABLE:
                ema_fast = EMAIndicator(close=df['close'], window=self.ema_fast)
                indicators['ema_fast'] = ema_fast.ema_indicator().iloc[-1]
            else:
                # Ручная реализация EMA
                indicators['ema_fast'] = df['close'].ewm(span=self.ema_fast).mean().iloc[-1]
                
            # Медленная EMA
            if TA_AVAILABLE:
                ema_slow = EMAIndicator(close=df['close'], window=self.ema_slow)
                indicators['ema_slow'] = ema_slow.ema_indicator().iloc[-1]
            else:
                indicators['ema_slow'] = df['close'].ewm(span=self.ema_slow).mean().iloc[-1]
                
            # EMA Cross Signal
            indicators['ema_cross'] = 'bullish' if indicators['ema_fast'] > indicators['ema_slow'] else 'bearish'
            
            # === RSI ===
            if TA_AVAILABLE:
                rsi = RSIIndicator(close=df['close'], window=self.rsi_period)
                indicators['rsi'] = rsi.rsi().iloc[-1]
            else:
                # Упрощенная ручная RSI
                delta = df['close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
                rs = gain / loss.replace(0, np.inf)
                indicators['rsi'] = 100 - (100 / (1 + rs)).iloc[-1]
                
            # === ROC (Rate of Change) ===
            if TA_AVAILABLE:
                roc = ROCIndicator(close=df['close'], window=self.roc_period)
                indicators['roc'] = roc.roc().iloc[-1]
            else:
                # Ручная ROC
                if len(df) >= self.roc_period:
                    roc_value = ((current_price - df['close'].iloc[-self.roc_period]) / 
                               df['close'].iloc[-self.roc_period]) * 100
                    indicators['roc'] = roc_value
                else:
                    indicators['roc'] = 0
                    
            # === ATR для расчета уровней ===
            if TA_AVAILABLE:
                atr = AverageTrueRange(high=df['high'], low=df['low'], close=df['close'], window=14)
                indicators['atr'] = atr.average_true_range().iloc[-1]
            else:
                # Упрощенный ATR
                high_low = df['high'] - df['low']
                high_close = abs(df['high'] - df['close'].shift())
                low_close = abs(df['low'] - df['close'].shift())
                true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
                indicators['atr'] = true_range.rolling(window=14).mean().iloc[-1]
                
            # === VOLUME ANALYSIS ===
            if 'volume' in df.columns:
                # Средний объем за последние 20 периодов
                avg_volume = df['volume'].rolling(window=20).mean().iloc[-1]
                current_volume = df['volume'].iloc[-1]
                indicators['volume_ratio'] = current_volume / avg_volume if avg_volume > 0 else 1
                
                # Объемно-взвешенная цена
                vwap = (df['close'] * df['volume']).rolling(window=20).sum() / df['volume'].rolling(window=20).sum()
                indicators['vwap'] = vwap.iloc[-1]
                indicators['price_vs_vwap'] = ((current_price - indicators['vwap']) / indicators['vwap']) * 100
            else:
                indicators['volume_ratio'] = 1.0
                indicators['vwap'] = current_price
                indicators['price_vs_vwap'] = 0
                
            return indicators
            
        except Exception as e:
            logger.error(f"❌ Ошибка расчета индикаторов: {e}")
            # Возвращаем безопасные дефолтные значения
            return {
                'current_price': df['close'].iloc[-1] if len(df) > 0 else 0,
                'price_change_5d': 0,
                'price_change_10d': 0,
                'ema_fast': df['close'].iloc[-1] if len(df) > 0 else 0,
                'ema_slow': df['close'].iloc[-1] if len(df) > 0 else 0,
                'ema_cross': 'neutral',
                'rsi': 50,
                'roc': 0,
                'atr': df['close'].iloc[-1] * 0.02 if len(df) > 0 else 1,  # 2% от цены как дефолт
                'volume_ratio': 1.0,
                'vwap': df['close'].iloc[-1] if len(df) > 0 else 0,
                'price_vs_vwap': 0,
                'timestamp': datetime.utcnow()
            }
            
    # =================================================================
    # 2. УЛУЧШЕНИЕ АНАЛИЗА MOMENTUM SCORE
    # =================================================================
    
    def _analyze_momentum_score(self, indicators: Dict) -> Dict:
        """Улучшенный анализ momentum с весовыми коэффициентами"""
        
        momentum_score = {
            'direction': 'NEUTRAL',
            'strength': 0.0,
            'components': [],
            'detailed_scores': {}
        }
        
        try:
            bullish_score = 0.0
            bearish_score = 0.0
            
            # === 1. PRICE MOMENTUM ANALYSIS (40% веса) ===
            # Краткосрочный price momentum (20%)
            price_5d = indicators['price_change_5d']
            if price_5d > self.PRICE_CHANGE_THRESHOLD_5D:
                bullish_score += 0.20
                momentum_score['components'].append(f'Цена +{price_5d:.1f}% за 5 период')
            elif price_5d < -self.PRICE_CHANGE_THRESHOLD_5D:
                bearish_score += 0.20
                momentum_score['components'].append(f'Цена {price_5d:.1f}% за 5 период')
                
            momentum_score['detailed_scores']['price_5d'] = price_5d
            
            # Среднесрочный price momentum (20%)
            price_10d = indicators['price_change_10d']
            if price_10d > self.PRICE_CHANGE_THRESHOLD_10D:
                bullish_score += 0.20
                momentum_score['components'].append(f'Цена +{price_10d:.1f}% за 10 периодов')
            elif price_10d < -self.PRICE_CHANGE_THRESHOLD_10D:
                bearish_score += 0.20
                momentum_score['components'].append(f'Цена {price_10d:.1f}% за 10 периодов')
                
            momentum_score['detailed_scores']['price_10d'] = price_10d
            
            # === 2. EMA CROSS ANALYSIS (20% веса) ===
            if indicators['ema_cross'] == 'bullish':
                bullish_score += 0.20
                momentum_score['components'].append('EMA пересечение вверх')
            elif indicators['ema_cross'] == 'bearish':
                bearish_score += 0.20
                momentum_score['components'].append('EMA пересечение вниз')
                
            # === 3. RSI MOMENTUM (15% веса) ===
            rsi = indicators['rsi']
            if rsi > 60:
                bullish_score += 0.15
                momentum_score['components'].append(f'RSI бычий: {rsi:.1f}')
            elif rsi < 40:
                bearish_score += 0.15
                momentum_score['components'].append(f'RSI медвежий: {rsi:.1f}')
                
            momentum_score['detailed_scores']['rsi'] = rsi
            
            # === 4. ROC MOMENTUM (15% веса) ===
            roc = indicators['roc']
            if roc > self.ROC_BULLISH_THRESHOLD:
                bullish_score += 0.15
                momentum_score['components'].append(f'ROC растет: {roc:.1f}%')
            elif roc < self.ROC_BEARISH_THRESHOLD:
                bearish_score += 0.15
                momentum_score['components'].append(f'ROC падает: {roc:.1f}%')
                
            momentum_score['detailed_scores']['roc'] = roc
            
            # === 5. VOLUME CONFIRMATION (10% веса) ===
            volume_ratio = indicators['volume_ratio']
            if volume_ratio > self.VOLUME_RATIO_THRESHOLD:
                # Объем подтверждает доминирующее направление
                if bullish_score > bearish_score:
                    bullish_score += 0.10
                    momentum_score['components'].append(f'Объем подтверждает: {volume_ratio:.1f}x')
                elif bearish_score > bullish_score:
                    bearish_score += 0.10
                    momentum_score['components'].append(f'Объем подтверждает: {volume_ratio:.1f}x')
                    
            momentum_score['detailed_scores']['volume_ratio'] = volume_ratio
            
            # === 6. ОПРЕДЕЛЕНИЕ ФИНАЛЬНОГО НАПРАВЛЕНИЯ ===
            momentum_score['detailed_scores']['bullish_score'] = bullish_score
            momentum_score['detailed_scores']['bearish_score'] = bearish_score
            
            if bullish_score > bearish_score and bullish_score > 0.4:  # Минимальный порог
                momentum_score['direction'] = 'BULLISH'
                momentum_score['strength'] = bullish_score
            elif bearish_score > bullish_score and bearish_score > 0.4:
                momentum_score['direction'] = 'BEARISH'  
                momentum_score['strength'] = bearish_score
            else:
                momentum_score['direction'] = 'NEUTRAL'
                momentum_score['strength'] = max(bullish_score, bearish_score)
                
            # Добавляем качественную оценку силы
            if momentum_score['strength'] >= 0.8:
                momentum_score['strength_label'] = 'ОЧЕНЬ_СИЛЬНЫЙ'
            elif momentum_score['strength'] >= 0.6:
                momentum_score['strength_label'] = 'СИЛЬНЫЙ'
            elif momentum_score['strength'] >= 0.4:
                momentum_score['strength_label'] = 'УМЕРЕННЫЙ'
            else:
                momentum_score['strength_label'] = 'СЛАБЫЙ'
                
        except Exception as e:
            logger.error(f"❌ Ошибка анализа momentum: {e}")
            momentum_score['components'].append(f'Ошибка анализа: {str(e)}')
            
        return momentum_score
        
    

    
    def _calculate_with_talib(self, df: pd.DataFrame) -> Dict:
        """Расчет индикаторов с помощью TA-Lib"""
        indicators = {}
        
        try:
            # RSI
            rsi_indicator = RSIIndicator(df['close'], window=self.rsi_period)
            indicators['rsi'] = float(rsi_indicator.rsi().iloc[-1])
            
            # EMA
            ema_fast = EMAIndicator(df['close'], window=self.ema_fast)
            ema_slow = EMAIndicator(df['close'], window=self.ema_slow)
            indicators['ema_fast'] = float(ema_fast.ema_indicator().iloc[-1])
            indicators['ema_slow'] = float(ema_slow.ema_indicator().iloc[-1])
            
            # Rate of Change
            roc_indicator = ROCIndicator(df['close'], window=self.roc_period)
            indicators['roc'] = float(roc_indicator.roc().iloc[-1])
            
            # ATR
            atr_indicator = AverageTrueRange(df['high'], df['low'], df['close'], window=14)
            indicators['atr'] = float(atr_indicator.average_true_range().iloc[-1])
            
        except Exception as e:
            logger.warning(f"⚠️ Ошибка расчета с TA-Lib: {e}, переключаемся на ручной расчет")
            return self._calculate_manual(df)
            
        return indicators
    
    def _calculate_manual(self, df: pd.DataFrame) -> Dict:
        """Ручной расчет индикаторов"""
        indicators = {}
        
        try:
            # RSI (упрощенная версия)
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            indicators['rsi'] = float(rsi.iloc[-1]) if not rsi.iloc[-1] is pd.isna(rsi.iloc[-1]) else 50.0
            
            # EMA
            ema_fast = df['close'].ewm(span=self.ema_fast).mean()
            ema_slow = df['close'].ewm(span=self.ema_slow).mean()
            indicators['ema_fast'] = float(ema_fast.iloc[-1])
            indicators['ema_slow'] = float(ema_slow.iloc[-1])
            
            # Rate of Change
            roc = ((df['close'] - df['close'].shift(self.roc_period)) / df['close'].shift(self.roc_period)) * 100
            indicators['roc'] = float(roc.iloc[-1]) if not pd.isna(roc.iloc[-1]) else 0.0
            
            # ATR (упрощенная версия)
            high_low = df['high'] - df['low']
            high_close = abs(df['high'] - df['close'].shift())
            low_close = abs(df['low'] - df['close'].shift())
            true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            atr = true_range.rolling(window=14).mean()
            indicators['atr'] = float(atr.iloc[-1]) if not pd.isna(atr.iloc[-1]) else 1.0
            
        except Exception as e:
            logger.error(f"❌ Ошибка ручного расчета индикаторов: {e}")
            # Возвращаем дефолтные значения
            indicators = {
                'rsi': 50.0,
                'ema_fast': float(df['close'].iloc[-1]),
                'ema_slow': float(df['close'].iloc[-1]),
                'roc': 0.0,
                'atr': float(df['close'].iloc[-1]) * 0.02  # 2% от цены
            }
            
        return indicators
    
    def _analyze_momentum(self, indicators: Dict) -> Dict:
        """Анализ momentum на основе индикаторов"""
        momentum_score = {
            'direction': 'NEUTRAL',
            'strength': 0.0,
            'components': []
        }
        
        bullish_score = 0.0
        bearish_score = 0.0
        
        try:
            # EMA тренд
            if indicators['ema_fast'] > indicators['ema_slow']:
                bullish_score += 0.3
                momentum_score['components'].append('EMA бычий')
            else:
                bearish_score += 0.3
                momentum_score['components'].append('EMA медвежий')
            
            # RSI momentum
            rsi = indicators['rsi']
            if rsi > 60:
                bullish_score += 0.2
                momentum_score['components'].append('RSI сильный')
            elif rsi < 40:
                bearish_score += 0.2
                momentum_score['components'].append('RSI слабый')
            
            # ROC momentum
            roc = indicators['roc']
            if roc > self.ROC_BULLISH_THRESHOLD:
                bullish_score += 0.25
                momentum_score['components'].append('ROC растет')
            elif roc < self.ROC_BEARISH_THRESHOLD:
                bearish_score += 0.25
                momentum_score['components'].append('ROC падает')
            
            # Volume confirmation
            if indicators['volume_ratio'] > self.VOLUME_RATIO_THRESHOLD:
                if bullish_score > bearish_score:
                    bullish_score += 0.15
                    momentum_score['components'].append('Объем подтверждает')
                else:
                    bearish_score += 0.15
                    momentum_score['components'].append('Объем подтверждает')
            
            # Определяем направление и силу
            if bullish_score > bearish_score and bullish_score > 0.5:
                momentum_score['direction'] = 'BULLISH'
                momentum_score['strength'] = bullish_score
            elif bearish_score > bullish_score and bearish_score > 0.5:
                momentum_score['direction'] = 'BEARISH'
                momentum_score['strength'] = bearish_score
            else:
                momentum_score['direction'] = 'NEUTRAL'
                momentum_score['strength'] = max(bullish_score, bearish_score)
                
        except Exception as e:
            logger.error(f"❌ Ошибка анализа momentum: {e}")
            
        return momentum_score
    
    def _make_decision(self, momentum_score: Dict, indicators: Dict, df: pd.DataFrame) -> TradingSignal:
        """Улучшенное принятие решения с дополнительными фильтрами"""
        
        try:
            # === ОСНОВНАЯ ПРОВЕРКА СИЛЫ MOMENTUM ===
            if momentum_score['strength'] < self.min_momentum_score:
                return TradingSignal(
                    action='WAIT',
                    confidence=0,
                    price=indicators['current_price'],
                    reason=f"Слабый momentum: {momentum_score['strength']:.2f} < {self.min_momentum_score}",
                    metadata={'momentum_score': momentum_score, 'indicators': indicators}
                )
            
            # === ОПРЕДЕЛЕНИЕ ДЕЙСТВИЯ ===
            if momentum_score['direction'] == 'BULLISH':
                action = 'BUY'
            elif momentum_score['direction'] == 'BEARISH':
                action = 'SELL'
            else:
                return TradingSignal(
                    action='WAIT',
                    confidence=0,
                    price=indicators['current_price'],
                    reason="Нейтральный momentum",
                    metadata={'momentum_score': momentum_score}
                )
            
            # === ДОПОЛНИТЕЛЬНЫЕ ФИЛЬТРЫ ===
            current_price = indicators['current_price']
            atr = indicators['atr']
            
            # Фильтр RSI - избегаем экстремальных зон
            rsi = indicators['rsi']
            if action == 'BUY' and rsi > 80:
                return TradingSignal(
                    action='WAIT',
                    confidence=0,
                    price=current_price,
                    reason=f"RSI перекуплен: {rsi:.1f}",
                    metadata={'rsi': rsi}
                )
            elif action == 'SELL' and rsi < 20:
                return TradingSignal(
                    action='WAIT',
                    confidence=0,
                    price=current_price,
                    reason=f"RSI перепродан: {rsi:.1f}",
                    metadata={'rsi': rsi}
                )
            
            # === РАСЧЕТ УРОВНЕЙ ===
            # Динамический расчет стоп-лосса на основе ATR и силы momentum
            atr_multiplier = 2.5 if momentum_score['strength'] > 0.7 else 2.0
            stop_loss = self.calculate_stop_loss(current_price, action, atr, atr_multiplier)
            
            # Динамический расчет тейк-профита
            tp_multiplier = 4.0 if momentum_score['strength'] > 0.8 else 3.0  
            take_profit = self.calculate_take_profit(current_price, action, atr, tp_multiplier)
            
            risk_reward = self.calculate_risk_reward(current_price, stop_loss, take_profit)
            
            # === ПРОВЕРКА RISK/REWARD ===
            min_rr = 1.5 if momentum_score['strength'] > 0.7 else 2.0
            if risk_reward < min_rr:
                return TradingSignal(
                    action='WAIT',
                    confidence=0,
                    price=current_price,
                    reason=f"Плохой R/R: {risk_reward:.2f} < {min_rr}",
                    metadata={'risk_reward': risk_reward, 'required': min_rr}
                )
            
            # === РАСЧЕТ CONFIDENCE ===
            # Confidence зависит от силы momentum и качества сигнала
            base_confidence = momentum_score['strength']
            
            # Бонусы за качество сигнала
            if volume_ratio := indicators.get('volume_ratio', 1.0) > 1.5:
                base_confidence += 0.05  # Объем подтверждает
                
            if risk_reward > 3.0:
                base_confidence += 0.05  # Отличный R/R
                
            # Штрафы
            if rsi > 75 or rsi < 25:
                base_confidence -= 0.1  # RSI в экстремальной зоне
                
            confidence = min(0.95, max(0.1, base_confidence))  # Ограничиваем
            
            # === ФОРМИРОВАНИЕ ПРИЧИНЫ ===
            components_str = ', '.join(momentum_score['components'][:3])  # Топ-3 компонента
            reason = (f"Momentum {momentum_score['direction']} ({momentum_score['strength_label']}): "
                     f"{components_str}")
            
            # === СОЗДАНИЕ ИТОГОВОГО СИГНАЛА ===
            return TradingSignal(
                action=action,
                confidence=confidence,
                price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                reason=reason,
                risk_reward_ratio=risk_reward,
                indicators=indicators,
                metadata={
                    'momentum_score': momentum_score,
                    'atr_multiplier': atr_multiplier,
                    'tp_multiplier': tp_multiplier,
                    'strength_label': momentum_score['strength_label'],
                    'detailed_scores': momentum_score.get('detailed_scores', {})
                }
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка принятия решения: {e}")
            return TradingSignal(
                action='WAIT',
                confidence=0,
                price=indicators.get('current_price', 0),
                reason=f'Ошибка решения: {e}',
                metadata={'error': str(e)}
            )