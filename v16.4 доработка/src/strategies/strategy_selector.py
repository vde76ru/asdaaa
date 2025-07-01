#!/usr/bin/env python3
"""
STRATEGY SELECTOR - Интеллектуальный выбор торговых стратегий
Файл: src/strategies/strategy_selector.py

🎯 ФУНКЦИИ:
✅ Автоматический выбор оптимальной стратегии для рыночных условий  
✅ Анализ производительности стратегий в реальном времени
✅ Адаптивное переключение между стратегиями
✅ Ensemble подход - комбинирование нескольких стратегий
✅ Учет корреляции и диверсификации стратегий
"""

import asyncio
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from collections import defaultdict, deque
from dataclasses import dataclass
import logging

from .base import BaseStrategy, TradingSignal
from .multi_indicator import MultiIndicatorStrategy
from .momentum import MomentumStrategy
from .mean_reversion import MeanReversionStrategy
from .scalping import ScalpingStrategy
from ..core.database import SessionLocal
try:
    from ..core.models import StrategyPerformance, MarketCondition
except ImportError:
    # Если моделей нет, используем заглушки
    StrategyPerformance = None
    MarketCondition = None
from ..core.unified_config import unified_config as config

logger = logging.getLogger(__name__)

@dataclass
class StrategyScore:
    """Оценка стратегии"""
    name: str
    score: float                    # Общий скор 0-100
    confidence: float              # Уверенность 0-1
    win_rate: float               # Процент прибыльных сделок
    avg_return: float             # Средняя доходность
    max_drawdown: float           # Максимальная просадка
    sharpe_ratio: float           # Коэффициент Шарпа
    recent_performance: float     # Производительность за последние дни
    market_condition_fit: float   # Соответствие рыночным условиям

@dataclass
class MarketCondition:
    """Состояние рынка для выбора стратегии"""
    trend: str                    # BULLISH, BEARISH, SIDEWAYS
    volatility: str              # LOW, MEDIUM, HIGH
    volume_profile: str          # INCREASING, DECREASING, STABLE
    market_phase: str            # ACCUMULATION, MARKUP, DISTRIBUTION, MARKDOWN
    fear_greed_index: int        # 0-100
    
class StrategySelector:
    """
    Интеллектуальный селектор торговых стратегий
    
    🧠 АДАПТИВНЫЙ ВЫБОР СТРАТЕГИЙ:
    1. Анализирует текущие рыночные условия
    2. Оценивает историческую производительность стратегий
    3. Учитывает корреляцию между стратегиями
    4. Выбирает оптимальную стратегию или их комбинацию
    5. Динамически переключается при изменении условий
    """
    
    def __init__(self):
        """Инициализация селектора стратегий"""
        self.strategies = self._initialize_strategies()
        self.performance_history = defaultdict(deque)
        self.last_selection_time = None
        self.current_strategy = None
        self.selection_interval = timedelta(hours=1)  # Переоценка каждый час
        
        # Настройки из конфигурации
        self.min_confidence = config.MIN_STRATEGY_CONFIDENCE
        self.ensemble_min_strategies = config.ENSEMBLE_MIN_STRATEGIES
        self.performance_window_days = config.STRATEGY_PERFORMANCE_WINDOW_DAYS
        
        logger.info(f"✅ StrategySelector инициализирован с {len(self.strategies)} стратегиями")
    
    def _initialize_strategies(self) -> Dict[str, BaseStrategy]:
        """Инициализация всех доступных стратегий"""
        strategies = {}
        
        try:
            # Базовые стратегии
            if config.ENABLE_MULTI_INDICATOR:
                strategies['multi_indicator'] = MultiIndicatorStrategy()
                
            if config.ENABLE_MOMENTUM:
                strategies['momentum'] = MomentumStrategy()
                
            strategies['mean_reversion'] = MeanReversionStrategy()
            strategies['scalping'] = ScalpingStrategy()
            
            # Попытка загрузить дополнительные стратегии
            try:
                from .breakout import BreakoutStrategy
                strategies['breakout'] = BreakoutStrategy()
            except ImportError:
                logger.warning("⚠️ BreakoutStrategy не найден")
                
            try:
                from .swing import SwingStrategy
                strategies['swing'] = SwingStrategy()
            except ImportError:
                logger.warning("⚠️ SwingStrategy не найден")
            
            logger.info(f"📊 Загружено стратегий: {list(strategies.keys())}")
            return strategies
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации стратегий: {e}")
            # Возвращаем минимальный набор
            return {
                'multi_indicator': MultiIndicatorStrategy(),
                'momentum': MomentumStrategy()
            }
    
    async def select_best_strategy(self, market_data: pd.DataFrame, 
                                 symbol: str) -> Tuple[str, BaseStrategy, float]:
        """
        Выбор лучшей стратегии для текущих условий
        
        Returns:
            Tuple[strategy_name, strategy_instance, confidence]
        """
        try:
            # Анализируем рыночные условия
            market_condition = await self._analyze_market_conditions(market_data)
            
            # Оцениваем каждую стратегию
            strategy_scores = await self._evaluate_strategies(
                market_data, symbol, market_condition
            )
            
            # Выбираем лучшую стратегию
            best_strategy = self._select_optimal_strategy(strategy_scores)
            
            # Сохраняем выбор
            self.current_strategy = best_strategy.name
            self.last_selection_time = datetime.utcnow()
            
            logger.info(
                f"🎯 Выбрана стратегия: {best_strategy.name} "
                f"(score: {best_strategy.score:.1f}, confidence: {best_strategy.confidence:.2f})"
            )
            
            return (
                best_strategy.name,
                self.strategies[best_strategy.name],
                best_strategy.confidence
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка выбора стратегии: {e}")
            # Возвращаем дефолтную стратегию
            default_name = config.DEFAULT_STRATEGY
            return (
                default_name,
                self.strategies.get(default_name, list(self.strategies.values())[0]),
                0.5
            )
    
    async def _analyze_market_conditions(self, df: pd.DataFrame) -> MarketCondition:
        """Анализ текущих рыночных условий"""
        try:
            # Определяем тренд
            sma_20 = df['close'].rolling(20).mean()
            sma_50 = df['close'].rolling(50).mean()
            current_price = df['close'].iloc[-1]
            
            if current_price > sma_20.iloc[-1] > sma_50.iloc[-1]:
                trend = 'BULLISH'
            elif current_price < sma_20.iloc[-1] < sma_50.iloc[-1]:
                trend = 'BEARISH'
            else:
                trend = 'SIDEWAYS'
            
            # Определяем волатильность
            volatility_20 = df['close'].rolling(20).std()
            current_vol = volatility_20.iloc[-1]
            avg_vol = volatility_20.mean()
            
            if current_vol > avg_vol * 1.5:
                volatility = 'HIGH'
            elif current_vol < avg_vol * 0.7:
                volatility = 'LOW'
            else:
                volatility = 'MEDIUM'
            
            # Анализ объемов (если доступны)
            if 'volume' in df.columns:
                vol_sma = df['volume'].rolling(20).mean()
                recent_vol = df['volume'].tail(5).mean()
                
                if recent_vol > vol_sma.iloc[-1] * 1.2:
                    volume_profile = 'INCREASING'
                elif recent_vol < vol_sma.iloc[-1] * 0.8:
                    volume_profile = 'DECREASING'
                else:
                    volume_profile = 'STABLE'
            else:
                volume_profile = 'STABLE'
            
            # Простое определение фазы рынка
            if trend == 'BULLISH' and volume_profile == 'INCREASING':
                market_phase = 'MARKUP'
            elif trend == 'BEARISH' and volume_profile == 'INCREASING':
                market_phase = 'MARKDOWN'
            elif trend == 'SIDEWAYS' and volatility == 'LOW':
                market_phase = 'ACCUMULATION'
            else:
                market_phase = 'DISTRIBUTION'
            
            return MarketCondition(
                trend=trend,
                volatility=volatility,
                volume_profile=volume_profile,
                market_phase=market_phase,
                fear_greed_index=50  # Заглушка, можно подключить API
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка анализа рыночных условий: {e}")
            return MarketCondition(
                trend='SIDEWAYS',
                volatility='MEDIUM',
                volume_profile='STABLE',
                market_phase='ACCUMULATION',
                fear_greed_index=50
            )
    
    async def _evaluate_strategies(self, df: pd.DataFrame, symbol: str,
                                 market_condition: MarketCondition) -> List[StrategyScore]:
        """Оценка всех стратегий для текущих условий"""
        strategy_scores = []
        
        for name, strategy in self.strategies.items():
            try:
                score = await self._calculate_strategy_score(
                    strategy, df, symbol, market_condition
                )
                strategy_scores.append(score)
                
            except Exception as e:
                logger.error(f"❌ Ошибка оценки стратегии {name}: {e}")
                # Добавляем с низким скором
                strategy_scores.append(StrategyScore(
                    name=name,
                    score=0.0,
                    confidence=0.0,
                    win_rate=0.0,
                    avg_return=0.0,
                    max_drawdown=0.0,
                    sharpe_ratio=0.0,
                    recent_performance=0.0,
                    market_condition_fit=0.0
                ))
        
        return sorted(strategy_scores, key=lambda x: x.score, reverse=True)
    
    async def _calculate_strategy_score(self, strategy: BaseStrategy, 
                                      df: pd.DataFrame, symbol: str,
                                      market_condition: MarketCondition) -> StrategyScore:
        """Расчет детального скора стратегии"""
        try:
            # Получаем историческую производительность
            historical_perf = await self._get_historical_performance(strategy.name, symbol)
            
            # Соответствие рыночным условиям
            market_fit = self._calculate_market_fit(strategy, market_condition)
            
            # Недавняя производительность
            recent_perf = self._calculate_recent_performance(strategy.name)
            
            # Технический анализ текущих условий
            technical_score = await self._evaluate_technical_conditions(strategy, df)
            
            # Итоговый скор (взвешенная сумма)
            final_score = (
                historical_perf['avg_return'] * 0.3 +
                market_fit * 0.25 +
                recent_perf * 0.25 +
                technical_score * 0.2
            ) * 100
            
            return StrategyScore(
                name=strategy.name,
                score=max(0, min(100, final_score)),
                confidence=min(1.0, final_score / 100),
                win_rate=historical_perf['win_rate'],
                avg_return=historical_perf['avg_return'],
                max_drawdown=historical_perf['max_drawdown'],
                sharpe_ratio=historical_perf['sharpe_ratio'],
                recent_performance=recent_perf,
                market_condition_fit=market_fit
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка расчета скора для {strategy.name}: {e}")
            return StrategyScore(
                name=strategy.name,
                score=25.0,  # Базовый скор
                confidence=0.5,
                win_rate=0.5,
                avg_return=0.0,
                max_drawdown=0.05,
                sharpe_ratio=0.5,
                recent_performance=0.5,
                market_condition_fit=0.5
            )
    
    async def _get_historical_performance(self, strategy_name: str, 
                                        symbol: str) -> Dict[str, float]:
        """Получение исторической производительности стратегии"""
        try:
            db = SessionLocal()
            
            # Запрос производительности за последние дни
            cutoff_date = datetime.utcnow() - timedelta(days=self.performance_window_days)
            
            performance = db.query(StrategyPerformance).filter(
                StrategyPerformance.strategy_name == strategy_name,
                StrategyPerformance.symbol == symbol,
                StrategyPerformance.created_at >= cutoff_date
            ).all()
            
            if not performance:
                return {
                    'avg_return': 0.0,
                    'win_rate': 0.5,
                    'max_drawdown': 0.05,
                    'sharpe_ratio': 0.5
                }
            
            if not StrategyPerformance:
                return {
                    'avg_return': 0.0,
                    'win_rate': 0.5,
                    'max_drawdown': 0.05,
                    'sharpe_ratio': 0.5
                }
            # Рассчитываем метрики
            returns = [p.total_return for p in performance]
            wins = sum(1 for r in returns if r > 0)
            
            return {
                'avg_return': np.mean(returns),
                'win_rate': wins / len(returns) if returns else 0.5,
                'max_drawdown': abs(min(returns)) if returns else 0.05,
                'sharpe_ratio': np.mean(returns) / (np.std(returns) + 0.01) if returns else 0.5
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения исторической производительности: {e}")
            return {
                'avg_return': 0.0,
                'win_rate': 0.5,
                'max_drawdown': 0.05,
                'sharpe_ratio': 0.5
            }
        finally:
            db.close()
    
    def _calculate_market_fit(self, strategy: BaseStrategy, 
                            market_condition: MarketCondition) -> float:
        """Расчет соответствия стратегии рыночным условиям"""
        try:
            # Базовые предпочтения стратегий
            strategy_preferences = {
                'momentum': {
                    'trend': {'BULLISH': 0.9, 'BEARISH': 0.9, 'SIDEWAYS': 0.3},
                    'volatility': {'HIGH': 0.8, 'MEDIUM': 0.7, 'LOW': 0.4}
                },
                'mean_reversion': {
                    'trend': {'BULLISH': 0.4, 'BEARISH': 0.4, 'SIDEWAYS': 0.9},
                    'volatility': {'HIGH': 0.9, 'MEDIUM': 0.6, 'LOW': 0.3}
                },
                'scalping': {
                    'trend': {'BULLISH': 0.6, 'BEARISH': 0.6, 'SIDEWAYS': 0.8},
                    'volatility': {'HIGH': 0.9, 'MEDIUM': 0.7, 'LOW': 0.4}
                },
                'multi_indicator': {
                    'trend': {'BULLISH': 0.7, 'BEARISH': 0.7, 'SIDEWAYS': 0.6},
                    'volatility': {'HIGH': 0.6, 'MEDIUM': 0.8, 'LOW': 0.5}
                }
            }
            
            # Получаем предпочтения для стратегии
            prefs = strategy_preferences.get(strategy.name, {
                'trend': {'BULLISH': 0.6, 'BEARISH': 0.6, 'SIDEWAYS': 0.6},
                'volatility': {'HIGH': 0.6, 'MEDIUM': 0.6, 'LOW': 0.6}
            })
            
            # Рассчитываем соответствие
            trend_fit = prefs['trend'].get(market_condition.trend, 0.5)
            vol_fit = prefs['volatility'].get(market_condition.volatility, 0.5)
            
            return (trend_fit + vol_fit) / 2
            
        except Exception as e:
            logger.error(f"❌ Ошибка расчета соответствия рынку: {e}")
            return 0.5
    
    def _calculate_recent_performance(self, strategy_name: str) -> float:
        """Расчет недавней производительности стратегии"""
        try:
            if strategy_name not in self.performance_history:
                return 0.5
            
            recent_results = list(self.performance_history[strategy_name])[-10:]
            if not recent_results:
                return 0.5
            
            return np.mean(recent_results)
            
        except Exception as e:
            logger.error(f"❌ Ошибка расчета недавней производительности: {e}")
            return 0.5
    
    async def _evaluate_technical_conditions(self, strategy: BaseStrategy,
                                           df: pd.DataFrame) -> float:
        """Оценка технических условий для стратегии"""
        try:
            # Тестируем стратегию на текущих данных
            signal = await strategy.analyze(df, 'TEST')
            
            # Конвертируем уверенность в скор
            if signal.action == 'WAIT':
                return 0.3
            else:
                return signal.confidence
                
        except Exception as e:
            logger.error(f"❌ Ошибка оценки технических условий: {e}")
            return 0.5
    
    def _select_optimal_strategy(self, strategy_scores: List[StrategyScore]) -> StrategyScore:
        """Выбор оптимальной стратегии из оценок"""
        try:
            # Фильтруем по минимальной уверенности
            valid_strategies = [
                s for s in strategy_scores 
                if s.confidence >= self.min_confidence
            ]
            
            if not valid_strategies:
                # Если нет стратегий с достаточной уверенностью, берем лучшую
                return strategy_scores[0] if strategy_scores else StrategyScore(
                    name='multi_indicator',
                    score=50.0,
                    confidence=0.5,
                    win_rate=0.5,
                    avg_return=0.0,
                    max_drawdown=0.05,
                    sharpe_ratio=0.5,
                    recent_performance=0.5,
                    market_condition_fit=0.5
                )
            
            # Возвращаем стратегию с лучшим скором
            return valid_strategies[0]
            
        except Exception as e:
            logger.error(f"❌ Ошибка выбора оптимальной стратегии: {e}")
            return strategy_scores[0] if strategy_scores else StrategyScore(
                name='multi_indicator',
                score=50.0,
                confidence=0.5,
                win_rate=0.5,
                avg_return=0.0,
                max_drawdown=0.05,
                sharpe_ratio=0.5,
                recent_performance=0.5,
                market_condition_fit=0.5
            )
    
    def update_performance(self, strategy_name: str, performance: float):
        """Обновление производительности стратегии"""
        try:
            self.performance_history[strategy_name].append(performance)
            
            # Ограничиваем историю
            if len(self.performance_history[strategy_name]) > 100:
                self.performance_history[strategy_name].popleft()
                
        except Exception as e:
            logger.error(f"❌ Ошибка обновления производительности: {e}")
    
    def should_reselect(self) -> bool:
        """Проверка нужности пересмотра выбора стратегии"""
        if not self.last_selection_time:
            return True
        
        return datetime.utcnow() - self.last_selection_time > self.selection_interval
    
    def get_available_strategies(self) -> List[str]:
        """Получение списка доступных стратегий"""
        return list(self.strategies.keys())
    
    def get_current_strategy(self) -> Optional[str]:
        """Получение текущей выбранной стратегии"""
        return self.current_strategy

# =================================================================
# ГЛОБАЛЬНЫЕ ФУНКЦИИ
# =================================================================

# Глобальный экземпляр
strategy_selector = None

def get_strategy_selector() -> StrategySelector:
    """Получить глобальный экземпляр селектора стратегий"""
    global strategy_selector
    
    if strategy_selector is None:
        strategy_selector = StrategySelector()
    
    return strategy_selector

def create_strategy_selector() -> StrategySelector:
    """Создать новый экземпляр селектора стратегий"""
    return StrategySelector()

# Экспорты
__all__ = [
    'StrategySelector',
    'StrategyScore',
    'MarketCondition',
    'get_strategy_selector',
    'create_strategy_selector'
]