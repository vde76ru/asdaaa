"""
Market Analyzer - Анализатор рыночных условий
Файл: src/analysis/market_analyzer.py

🎯 ФУНКЦИИ:
✅ Анализ трендов и фаз рынка
✅ Определение волатильности и силы тренда
✅ Оценка рыночных условий для выбора стратегий
✅ Интеграция с множественными индикаторами
"""

import asyncio
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import logging

try:
    from ta.trend import EMAIndicator, ADXIndicator
    from ta.momentum import RSIIndicator
    from ta.volatility import AverageTrueRange, BollingerBands
    from ta.volume import OnBalanceVolumeIndicator
    TA_AVAILABLE = True
except ImportError:
    TA_AVAILABLE = False
    logging.warning("⚠️ TA-Lib не установлен, используем базовые вычисления")

from ..core.unified_config import unified_config as config
from ..core.database import SessionLocal
from ..core.models import Candle, MarketCondition

logger = logging.getLogger(__name__)

class TrendDirection(Enum):
    """Направления тренда"""
    STRONG_UPTREND = "strong_uptrend"
    UPTREND = "uptrend"
    SIDEWAYS = "sideways"
    DOWNTREND = "downtrend"
    STRONG_DOWNTREND = "strong_downtrend"

class MarketRegime(Enum):
    """Режимы рынка"""
    TRENDING = "trending"
    RANGING = "ranging"
    VOLATILE = "volatile"
    CONSOLIDATION = "consolidation"

class VolatilityLevel(Enum):
    """Уровни волатильности"""
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"

@dataclass
class MarketConditions:
    """Состояние рыночных условий"""
    symbol: str
    trend_direction: TrendDirection
    trend_strength: float          # 0-1
    market_regime: MarketRegime
    volatility_level: VolatilityLevel
    volatility_value: float
    volume_trend: str              # increasing/decreasing/stable
    support_level: Optional[float]
    resistance_level: Optional[float]
    confidence: float              # Уверенность в анализе 0-1
    timestamp: datetime
    
    # Дополнительные метрики
    rsi: Optional[float] = None
    adx: Optional[float] = None
    bb_position: Optional[float] = None  # Позиция в Bollinger Bands
    volume_score: Optional[float] = None

class MarketAnalyzer:
    """
    Анализатор рыночных условий
    
    🔥 ОПРЕДЕЛЯЕТ ОПТИМАЛЬНЫЕ УСЛОВИЯ ДЛЯ КАЖДОЙ СТРАТЕГИИ:
    - Momentum стратегии ← Трендовые рынки
    - Mean Reversion ← Боковые рынки  
    - Breakout ← Консолидация с низкой волатильностью
    - Scalping ← Высокая ликвидность, низкая волатильность
    """
    
    def __init__(self):
        """Инициализация анализатора"""
        self.trend_periods = {
            'short': 20,   # Краткосрочный тренд
            'medium': 50,  # Среднесрочный тренд
            'long': 200    # Долгосрочный тренд
        }
        
        self.volatility_window = 20
        self.volume_window = 20
        self.support_resistance_window = 50
        
        logger.info("✅ MarketAnalyzer инициализирован")
    
    async def analyze_market_conditions(self, symbol: str, timeframe: str = '1h') -> MarketConditions:
        """
        Основной метод анализа рыночных условий
        
        Args:
            symbol: Торговая пара
            timeframe: Таймфрейм анализа
            
        Returns:
            MarketConditions: Полный анализ рыночных условий
        """
        try:
            # Получаем исторические данные
            df = await self._get_market_data(symbol, timeframe)
            
            if df is None or len(df) < 50:
                return self._get_default_conditions(symbol)
            
            # Анализируем компоненты
            trend_analysis = self._analyze_trend(df)
            volatility_analysis = self._analyze_volatility(df)
            volume_analysis = self._analyze_volume(df)
            support_resistance = self._find_support_resistance(df)
            technical_indicators = self._calculate_technical_indicators(df)
            
            # Определяем режим рынка
            market_regime = self._determine_market_regime(
                trend_analysis, volatility_analysis, volume_analysis
            )
            
            # Рассчитываем уверенность
            confidence = self._calculate_confidence(
                trend_analysis, volatility_analysis, technical_indicators
            )
            
            # Создаем результат
            conditions = MarketConditions(
                symbol=symbol,
                trend_direction=trend_analysis['direction'],
                trend_strength=trend_analysis['strength'],
                market_regime=market_regime,
                volatility_level=volatility_analysis['level'],
                volatility_value=volatility_analysis['value'],
                volume_trend=volume_analysis['trend'],
                support_level=support_resistance.get('support'),
                resistance_level=support_resistance.get('resistance'),
                confidence=confidence,
                timestamp=datetime.utcnow(),
                rsi=technical_indicators.get('rsi'),
                adx=technical_indicators.get('adx'),
                bb_position=technical_indicators.get('bb_position'),
                volume_score=volume_analysis.get('score')
            )
            
            logger.info(
                f"📊 Анализ {symbol}: {trend_analysis['direction'].value}, "
                f"Волатильность: {volatility_analysis['level'].value}, "
                f"Режим: {market_regime.value}"
            )
            
            return conditions
            
        except Exception as e:
            logger.error(f"❌ Ошибка анализа рынка для {symbol}: {e}")
            return self._get_default_conditions(symbol)
    
    async def _get_market_data(self, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
        """Получение рыночных данных из БД или API"""
        try:
            # Пытаемся получить из базы данных
            db = SessionLocal()
            
            # Получаем данные за последние 200 периодов
            candles = db.query(Candle).filter(
                Candle.symbol == symbol,
                Candle.timeframe == timeframe
            ).order_by(Candle.timestamp.desc()).limit(200).all()
            
            if candles:
                # Конвертируем в DataFrame
                data = []
                for candle in reversed(candles):  # Сортируем по возрастанию времени
                    data.append({
                        'timestamp': candle.timestamp,
                        'open': float(candle.open),
                        'high': float(candle.high),
                        'low': float(candle.low),
                        'close': float(candle.close),
                        'volume': float(candle.volume)
                    })
                
                df = pd.DataFrame(data)
                df.set_index('timestamp', inplace=True)
                
                logger.debug(f"📈 Получено {len(df)} свечей для {symbol}")
                return df
            else:
                logger.warning(f"⚠️ Нет данных в БД для {symbol}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Ошибка получения данных для {symbol}: {e}")
            return None
        finally:
            try:
                db.close()
            except:
                pass
    
    def _analyze_trend(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Анализ трендов на разных таймфреймах"""
        try:
            current_price = df['close'].iloc[-1]
            
            # EMA анализ
            trends = {}
            for period_name, period in self.trend_periods.items():
                if len(df) >= period:
                    if TA_AVAILABLE:
                        ema = EMAIndicator(df['close'], window=period).ema_indicator()
                        trends[period_name] = current_price / ema.iloc[-1] - 1
                    else:
                        # Простая скользящая средняя как fallback
                        sma = df['close'].rolling(period).mean()
                        trends[period_name] = current_price / sma.iloc[-1] - 1
            
            # Определяем общее направление тренда
            if not trends:
                return {
                    'direction': TrendDirection.SIDEWAYS,
                    'strength': 0.5,
                    'short_trend': 0,
                    'medium_trend': 0,
                    'long_trend': 0
                }
            
            avg_trend = np.mean(list(trends.values()))
            strength = min(abs(avg_trend) * 10, 1.0)  # Нормализуем 0-1
            
            # Классификация направления
            if avg_trend > 0.05:
                direction = TrendDirection.STRONG_UPTREND
            elif avg_trend > 0.02:
                direction = TrendDirection.UPTREND
            elif avg_trend < -0.05:
                direction = TrendDirection.STRONG_DOWNTREND
            elif avg_trend < -0.02:
                direction = TrendDirection.DOWNTREND
            else:
                direction = TrendDirection.SIDEWAYS
            
            return {
                'direction': direction,
                'strength': strength,
                'short_trend': trends.get('short', 0),
                'medium_trend': trends.get('medium', 0),
                'long_trend': trends.get('long', 0),
                'avg_trend': avg_trend
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка анализа тренда: {e}")
            return {
                'direction': TrendDirection.SIDEWAYS,
                'strength': 0.5,
                'short_trend': 0,
                'medium_trend': 0,
                'long_trend': 0
            }
    
    def _analyze_volatility(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Анализ волатильности"""
        try:
            # Рассчитываем ATR или простую волатильность
            if TA_AVAILABLE and len(df) >= self.volatility_window:
                atr = AverageTrueRange(df['high'], df['low'], df['close'], 
                                     window=self.volatility_window).average_true_range()
                volatility = atr.iloc[-1] / df['close'].iloc[-1]
            else:
                # Простая волатильность через стандартное отклонение
                returns = df['close'].pct_change()
                volatility = returns.rolling(self.volatility_window).std().iloc[-1]
            
            # Классификация уровня волатильности
            if volatility < 0.01:
                level = VolatilityLevel.VERY_LOW
            elif volatility < 0.02:
                level = VolatilityLevel.LOW
            elif volatility < 0.04:
                level = VolatilityLevel.MEDIUM
            elif volatility < 0.08:
                level = VolatilityLevel.HIGH
            else:
                level = VolatilityLevel.EXTREME
            
            return {
                'level': level,
                'value': volatility,
                'normalized': min(volatility * 25, 1.0)  # Нормализуем 0-1
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка анализа волатильности: {e}")
            return {
                'level': VolatilityLevel.MEDIUM,
                'value': 0.02,
                'normalized': 0.5
            }
    
    def _analyze_volume(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Анализ объемов торговли"""
        try:
            if 'volume' not in df.columns:
                return {'trend': 'stable', 'score': 0.5}
            
            current_volume = df['volume'].iloc[-1]
            avg_volume = df['volume'].rolling(self.volume_window).mean().iloc[-1]
            
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
            
            # Тренд объема
            if volume_ratio > 1.5:
                trend = 'increasing'
                score = min(volume_ratio / 3, 1.0)
            elif volume_ratio < 0.7:
                trend = 'decreasing' 
                score = max(1 - volume_ratio, 0.2)
            else:
                trend = 'stable'
                score = 0.5
            
            return {
                'trend': trend,
                'ratio': volume_ratio,
                'score': score
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка анализа объема: {e}")
            return {'trend': 'stable', 'score': 0.5}
    
    def _find_support_resistance(self, df: pd.DataFrame) -> Dict[str, Optional[float]]:
        """Поиск уровней поддержки и сопротивления"""
        try:
            if len(df) < self.support_resistance_window:
                return {'support': None, 'resistance': None}
            
            # Простой алгоритм поиска локальных максимумов и минимумов
            recent_data = df.tail(self.support_resistance_window)
            
            # Сопротивление - максимум за период
            resistance = recent_data['high'].max()
            
            # Поддержка - минимум за период
            support = recent_data['low'].min()
            
            current_price = df['close'].iloc[-1]
            
            # Проверяем значимость уровней
            resistance_distance = (resistance - current_price) / current_price
            support_distance = (current_price - support) / current_price
            
            # Если уровни слишком далеко, игнорируем
            if resistance_distance > 0.1:  # Более 10%
                resistance = None
            if support_distance > 0.1:  # Более 10%
                support = None
            
            return {
                'support': support,
                'resistance': resistance
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка поиска уровней: {e}")
            return {'support': None, 'resistance': None}
    
    def _calculate_technical_indicators(self, df: pd.DataFrame) -> Dict[str, Optional[float]]:
        """Расчет технических индикаторов"""
        indicators = {}
        
        try:
            # RSI
            if TA_AVAILABLE:
                rsi = RSIIndicator(df['close'], window=14).rsi()
                indicators['rsi'] = rsi.iloc[-1] if not rsi.empty else None
                
                # ADX (сила тренда)
                if len(df) >= 14:
                    adx = ADXIndicator(df['high'], df['low'], df['close'], window=14).adx()
                    indicators['adx'] = adx.iloc[-1] if not adx.empty else None
                
                # Bollinger Bands позиция
                bb = BollingerBands(df['close'], window=20, window_dev=2)
                bb_upper = bb.bollinger_hband()
                bb_lower = bb.bollinger_lband()
                
                if not bb_upper.empty and not bb_lower.empty:
                    current_price = df['close'].iloc[-1]
                    upper = bb_upper.iloc[-1]
                    lower = bb_lower.iloc[-1]
                    
                    # Позиция в полосах Боллинджера (0-1)
                    indicators['bb_position'] = (current_price - lower) / (upper - lower)
            
        except Exception as e:
            logger.error(f"❌ Ошибка расчета индикаторов: {e}")
        
        return indicators
    
    def _determine_market_regime(self, trend_analysis: Dict, volatility_analysis: Dict, 
                                volume_analysis: Dict) -> MarketRegime:
        """Определение режима рынка"""
        try:
            trend_strength = trend_analysis['strength']
            volatility_level = volatility_analysis['level']
            
            # Логика определения режима
            if trend_strength > 0.7:
                return MarketRegime.TRENDING
            elif volatility_level in [VolatilityLevel.HIGH, VolatilityLevel.EXTREME]:
                return MarketRegime.VOLATILE
            elif trend_strength < 0.3 and volatility_level == VolatilityLevel.LOW:
                return MarketRegime.CONSOLIDATION
            else:
                return MarketRegime.RANGING
                
        except Exception as e:
            logger.error(f"❌ Ошибка определения режима рынка: {e}")
            return MarketRegime.RANGING
    
    def _calculate_confidence(self, trend_analysis: Dict, volatility_analysis: Dict,
                            technical_indicators: Dict) -> float:
        """Расчет уверенности в анализе"""
        try:
            confidence_factors = []
            
            # Фактор силы тренда
            trend_strength = trend_analysis.get('strength', 0.5)
            confidence_factors.append(trend_strength)
            
            # Фактор стабильности волатильности
            volatility_normalized = volatility_analysis.get('normalized', 0.5)
            volatility_confidence = 1 - abs(volatility_normalized - 0.5) * 2
            confidence_factors.append(volatility_confidence)
            
            # Фактор технических индикаторов
            rsi = technical_indicators.get('rsi')
            if rsi is not None:
                # Экстремальные значения RSI дают больше уверенности
                rsi_confidence = abs(rsi - 50) / 50
                confidence_factors.append(rsi_confidence)
            
            # Общая уверенность
            if confidence_factors:
                confidence = np.mean(confidence_factors)
                return max(0.3, min(confidence, 0.95))  # Ограничиваем 0.3-0.95
            else:
                return 0.5
                
        except Exception as e:
            logger.error(f"❌ Ошибка расчета уверенности: {e}")
            return 0.5
    
    def _get_default_conditions(self, symbol: str) -> MarketConditions:
        """Возвращает условия по умолчанию при ошибках"""
        return MarketConditions(
            symbol=symbol,
            trend_direction=TrendDirection.SIDEWAYS,
            trend_strength=0.5,
            market_regime=MarketRegime.RANGING,
            volatility_level=VolatilityLevel.MEDIUM,
            volatility_value=0.02,
            volume_trend='stable',
            support_level=None,
            resistance_level=None,
            confidence=0.3,
            timestamp=datetime.utcnow()
        )
    
    def get_strategy_recommendations(self, conditions: MarketConditions) -> Dict[str, float]:
        """
        Рекомендации стратегий на основе рыночных условий
        
        Returns:
            Dict[strategy_name, suitability_score]: Скоры пригодности 0-1
        """
        recommendations = {}
        
        # Momentum стратегии
        if conditions.trend_direction in [TrendDirection.UPTREND, TrendDirection.STRONG_UPTREND, 
                                        TrendDirection.DOWNTREND, TrendDirection.STRONG_DOWNTREND]:
            recommendations['momentum'] = 0.8 * conditions.trend_strength
        else:
            recommendations['momentum'] = 0.2
        
        # Mean Reversion стратегии
        if conditions.trend_direction == TrendDirection.SIDEWAYS:
            recommendations['mean_reversion'] = 0.8
        else:
            recommendations['mean_reversion'] = 0.3
        
        # Breakout стратегии
        if (conditions.market_regime == MarketRegime.CONSOLIDATION and 
            conditions.volatility_level == VolatilityLevel.LOW):
            recommendations['breakout'] = 0.9
        else:
            recommendations['breakout'] = 0.4
        
        # Scalping стратегии
        if (conditions.volatility_level in [VolatilityLevel.LOW, VolatilityLevel.MEDIUM] and
            conditions.volume_trend == 'increasing'):
            recommendations['scalping'] = 0.7
        else:
            recommendations['scalping'] = 0.3
        
        # Multi-indicator (универсальная)
        recommendations['multi_indicator'] = 0.6 + conditions.confidence * 0.3
        
        return recommendations

# Экспорт
__all__ = [
    'MarketAnalyzer',
    'MarketConditions',
    'TrendDirection',
    'MarketRegime',
    'VolatilityLevel'
]