"""
ML-based Strategy Selector для выбора оптимальных стратегий
Файл: src/ml/strategy_selector.py
"""
# ВАЖНО: Все импорты моделей БД должны быть из core.models!
from ..core.models import (
    TradingLog, BotState, Trade, Signal, 
    Balance, TradingPair, MLModel, User
)
from ..core.database import db, SessionLocal

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import asyncio
from collections import defaultdict

from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from ..logging.smart_logger import SmartLogger

# ML импорты с защитой
try:
    from .features.feature_engineering import FeatureEngineer
except ImportError:
    FeatureEngineer = None

try:
    from .training.trainer import MLTrainer
except ImportError:
    MLTrainer = None


class MLStrategySelector:
    """
    Интеллектуальный селектор стратегий на основе ML
    """
    
    def __init__(self):
        self.logger = SmartLogger("ml.strategy_selector")
        self.feature_engineer = FeatureEngineer() if FeatureEngineer else None
        self.ml_trainer = None  # Инициализируется позже
        
        # Кэш производительности стратегий
        self.performance_cache = {}
        self.cache_ttl = 3600  # 1 час
        
        # Параметры селектора
        self.config = {
            'min_trades_for_stats': 10,  # Минимум сделок для статистики
            'lookback_days': 30,         # Период анализа производительности
            'confidence_threshold': 0.6,  # Минимальная уверенность ML
            'strategy_weights': {
                'historical_performance': 0.4,
                'ml_prediction': 0.3,
                'market_conditions': 0.2,
                'recent_performance': 0.1
            }
        }
        
        # Активные стратегии по символам
        self.active_strategies = defaultdict(dict)
        
        if not self.feature_engineer:
            self.logger.warning("FeatureEngineer недоступен - используем упрощенную логику")
    
    async def initialize(self, ml_trainer: Optional[MLTrainer] = None):
        """Инициализация селектора"""
        self.ml_trainer = ml_trainer or (MLTrainer() if MLTrainer else None)
        await self.load_strategy_performance()
        
        self.logger.info(
            "Strategy Selector инициализирован",
            category='strategy',
            config=self.config
        )
    
    async def select_best_strategy(self, symbol: str, current_features: pd.DataFrame) -> Dict[str, Any]:
        """
        Выбирает лучшую стратегию для текущих условий
        
        Args:
            symbol: Торговая пара
            current_features: Текущие рыночные признаки
            
        Returns:
            Dict с выбранной стратегией и метаданными
        """
        self.logger.info(
            f"Выбор стратегии для {symbol}",
            category='strategy',
            symbol=symbol
        )
        
        # 1. Получаем ML предсказание
        ml_prediction = await self.ml_trainer.predict_direction(symbol, current_features)
        if not ml_prediction:
            self.logger.warning(
                f"Нет ML предсказания для {symbol}",
                category='strategy',
                symbol=symbol
            )
            ml_prediction = {'direction': 'SIDEWAYS', 'confidence': 0.5}
        
        # 2. Анализируем текущие рыночные условия
        market_conditions = await self._analyze_market_conditions(symbol, current_features)
        
        # 3. Получаем производительность стратегий
        strategy_performance = await self._get_strategy_performance(symbol, market_conditions)
        
        # 4. Рассчитываем скоры для каждой стратегии
        strategy_scores = await self._calculate_strategy_scores(
            symbol,
            ml_prediction,
            market_conditions,
            strategy_performance
        )
        
        # 5. Выбираем лучшую стратегию
        if not strategy_scores:
            # Fallback на дефолтную стратегию
            return {
                'strategy': 'RSIStrategy',
                'confidence': 0.5,
                'reason': 'No data, using default',
                'ml_prediction': ml_prediction,
                'market_conditions': market_conditions
            }
        
        # Сортируем по скору
        best_strategy = max(strategy_scores.items(), key=lambda x: x[1]['total_score'])
        strategy_name = best_strategy[0]
        strategy_data = best_strategy[1]
        
        # Проверяем минимальную уверенность
        if ml_prediction['confidence'] < self.config['confidence_threshold']:
            # Используем консервативную стратегию при низкой уверенности
            if ml_prediction['direction'] == 'SIDEWAYS':
                strategy_name = 'BollingerBandsStrategy'  # Хорошо для боковика
                strategy_data['reason'] = 'Low ML confidence, using range strategy'
        
        # Сохраняем выбор
        self.active_strategies[symbol] = {
            'strategy': strategy_name,
            'selected_at': datetime.utcnow(),
            'score': strategy_data['total_score'],
            'ml_confidence': ml_prediction['confidence']
        }
        
        result = {
            'strategy': strategy_name,
            'confidence': strategy_data['total_score'],
            'reason': strategy_data.get('reason', 'Best overall score'),
            'ml_prediction': ml_prediction,
            'market_conditions': market_conditions,
            'scores': strategy_scores,
            'parameters': await self._get_optimal_parameters(strategy_name, symbol, market_conditions)
        }
        
        self.logger.info(
            f"Выбрана стратегия {strategy_name} для {symbol}",
            category='strategy',
            symbol=symbol,
            strategy=strategy_name,
            confidence=result['confidence'],
            ml_direction=ml_prediction['direction']
        )
        
        # Сохраняем выбор в БД
        await self._save_strategy_selection(symbol, result)
        
        return result
    
    async def _analyze_market_conditions(self, symbol: str, features: pd.DataFrame) -> Dict[str, Any]:
        """Анализирует текущие рыночные условия"""
        conditions = {}
        
        if features.empty:
            return {'condition': 'unknown', 'volatility': 'normal', 'trend': 'neutral'}
        
        latest = features.iloc[-1]
        
        # Тренд (на основе EMA)
        if 'ema_21' in features.columns and 'ema_50' in features.columns:
            if latest['close'] > latest['ema_21'] > latest['ema_50']:
                conditions['trend'] = 'bullish'
            elif latest['close'] < latest['ema_21'] < latest['ema_50']:
                conditions['trend'] = 'bearish'
            else:
                conditions['trend'] = 'neutral'
        
        # Волатильность (на основе ATR)
        if 'atr_pct' in features.columns:
            atr_pct = latest['atr_pct']
            if atr_pct > 3:
                conditions['volatility'] = 'high'
            elif atr_pct < 1:
                conditions['volatility'] = 'low'
            else:
                conditions['volatility'] = 'normal'
        
        # Моментум (на основе RSI)
        if 'rsi' in features.columns:
            rsi = latest['rsi']
            if rsi > 70:
                conditions['momentum'] = 'overbought'
            elif rsi < 30:
                conditions['momentum'] = 'oversold'
            else:
                conditions['momentum'] = 'neutral'
        
        # Объем
        if 'volume_change_pct' in features.columns:
            vol_change = latest['volume_change_pct']
            if vol_change > 50:
                conditions['volume'] = 'increasing'
            elif vol_change < -30:
                conditions['volume'] = 'decreasing'
            else:
                conditions['volume'] = 'stable'
        
        # Общее состояние рынка
        if conditions.get('trend') == 'bullish' and conditions.get('volatility') == 'low':
            conditions['condition'] = 'trending_up'
        elif conditions.get('trend') == 'bearish' and conditions.get('volatility') == 'low':
            conditions['condition'] = 'trending_down'
        elif conditions.get('volatility') == 'high':
            conditions['condition'] = 'volatile'
        else:
            conditions['condition'] = 'sideways'
        
        return conditions
    
    async def _get_strategy_performance(self, symbol: str, 
                                      market_conditions: Dict[str, Any]) -> Dict[str, Dict]:
        """Получает производительность стратегий"""
        # Проверяем кэш
        cache_key = f"{symbol}_{market_conditions.get('condition', 'unknown')}"
        if cache_key in self.performance_cache:
            cached_data, cached_time = self.performance_cache[cache_key]
            if (datetime.utcnow() - cached_time).total_seconds() < self.cache_ttl:
                return cached_data
        
        db = SessionLocal()
        try:
            # Получаем статистику по стратегиям за последний период
            cutoff_date = datetime.utcnow() - timedelta(days=self.config['lookback_days'])
            
            # Запрос производительности стратегий
            strategy_stats = db.query(
                Trade.strategy,
                func.count(Trade.id).label('total_trades'),
                func.avg(Trade.profit_percent).label('avg_profit'),
                func.sum(Trade.profit).label('total_profit'),
                func.count(func.nullif(Trade.profit > 0, False)).label('winning_trades')
            ).filter(
                and_(
                    Trade.symbol == symbol,
                    Trade.status == 'closed',
                    Trade.closed_at >= cutoff_date
                )
            ).group_by(Trade.strategy).all()
            
            performance = {}
            
            for stat in strategy_stats:
                if stat.total_trades >= self.config['min_trades_for_stats']:
                    win_rate = stat.winning_trades / stat.total_trades if stat.total_trades > 0 else 0
                    
                    performance[stat.strategy] = {
                        'total_trades': stat.total_trades,
                        'avg_profit': float(stat.avg_profit) if stat.avg_profit else 0,
                        'total_profit': float(stat.total_profit) if stat.total_profit else 0,
                        'win_rate': win_rate,
                        'score': self._calculate_performance_score(
                            win_rate, 
                            float(stat.avg_profit) if stat.avg_profit else 0,
                            stat.total_trades
                        )
                    }
            
            # Если нет достаточной статистики, используем дефолтные значения
            if not performance:
                # Дефолтные стратегии с базовыми скорами
                default_strategies = {
                    'RSIStrategy': {'score': 0.5, 'reason': 'Good for oversold/overbought'},
                    'MACDStrategy': {'score': 0.5, 'reason': 'Good for trends'},
                    'BollingerBandsStrategy': {'score': 0.5, 'reason': 'Good for volatility'},
                    'EMAStrategy': {'score': 0.5, 'reason': 'Good for trend following'}
                }
                
                for strategy, data in default_strategies.items():
                    performance[strategy] = {
                        'total_trades': 0,
                        'avg_profit': 0,
                        'total_profit': 0,
                        'win_rate': 0.5,
                        'score': data['score']
                    }
            
            # Кэшируем результат
            self.performance_cache[cache_key] = (performance, datetime.utcnow())
            
            return performance
            
        finally:
            db.close()
    
    def _calculate_performance_score(self, win_rate: float, avg_profit: float, 
                                   total_trades: int) -> float:
        """Рассчитывает скор производительности стратегии"""
        # Базовый скор на основе win rate
        score = win_rate * 0.5
        
        # Добавляем компонент прибыльности
        if avg_profit > 0:
            score += min(avg_profit / 100, 0.3)  # Максимум 0.3 за прибыльность
        else:
            score -= min(abs(avg_profit) / 100, 0.2)  # Штраф за убытки
        
        # Бонус за количество сделок (опыт)
        if total_trades > 50:
            score += 0.1
        elif total_trades > 20:
            score += 0.05
        
        # Ограничиваем скор
        return max(0, min(1, score))
    
    async def _calculate_strategy_scores(self, symbol: str, ml_prediction: Dict[str, Any],
                                       market_conditions: Dict[str, Any],
                                       strategy_performance: Dict[str, Dict]) -> Dict[str, Dict]:
        """Рассчитывает финальные скоры для каждой стратегии"""
        scores = {}
        
        # Матрица соответствия стратегий условиям рынка
        strategy_market_fit = {
            'RSIStrategy': {
                'sideways': 0.8,
                'volatile': 0.6,
                'trending_up': 0.4,
                'trending_down': 0.4
            },
            'MACDStrategy': {
                'trending_up': 0.9,
                'trending_down': 0.9,
                'sideways': 0.3,
                'volatile': 0.5
            },
            'BollingerBandsStrategy': {
                'sideways': 0.9,
                'volatile': 0.7,
                'trending_up': 0.5,
                'trending_down': 0.5
            },
            'EMAStrategy': {
                'trending_up': 0.8,
                'trending_down': 0.8,
                'sideways': 0.4,
                'volatile': 0.6
            },
            'VolumeStrategy': {
                'volatile': 0.8,
                'trending_up': 0.7,
                'trending_down': 0.7,
                'sideways': 0.5
            }
        }
        
        # Матрица соответствия стратегий ML предсказаниям
        strategy_ml_fit = {
            'RSIStrategy': {
                'UP': 0.6,
                'DOWN': 0.6,
                'SIDEWAYS': 0.8
            },
            'MACDStrategy': {
                'UP': 0.9,
                'DOWN': 0.9,
                'SIDEWAYS': 0.3
            },
            'BollingerBandsStrategy': {
                'UP': 0.5,
                'DOWN': 0.5,
                'SIDEWAYS': 0.9
            },
            'EMAStrategy': {
                'UP': 0.8,
                'DOWN': 0.8,
                'SIDEWAYS': 0.4
            },
            'VolumeStrategy': {
                'UP': 0.7,
                'DOWN': 0.7,
                'SIDEWAYS': 0.6
            }
        }
        
        weights = self.config['strategy_weights']
        current_condition = market_conditions.get('condition', 'unknown')
        ml_direction = ml_prediction.get('direction', 'SIDEWAYS')
        
        for strategy_name in strategy_performance:
            score_components = {}
            
            # 1. Историческая производительность
            hist_score = strategy_performance[strategy_name].get('score', 0.5)
            score_components['historical'] = hist_score * weights['historical_performance']
            
            # 2. Соответствие ML предсказанию
            ml_fit = strategy_ml_fit.get(strategy_name, {}).get(ml_direction, 0.5)
            ml_score = ml_fit * ml_prediction.get('confidence', 0.5)
            score_components['ml_prediction'] = ml_score * weights['ml_prediction']
            
            # 3. Соответствие рыночным условиям
            market_fit = strategy_market_fit.get(strategy_name, {}).get(current_condition, 0.5)
            score_components['market_conditions'] = market_fit * weights['market_conditions']
            
            # 4. Недавняя производительность (последние 7 дней)
            recent_perf = await self._get_recent_performance(symbol, strategy_name, days=7)
            score_components['recent_performance'] = recent_perf * weights['recent_performance']
            
            # Финальный скор
            total_score = sum(score_components.values())
            
            scores[strategy_name] = {
                'total_score': total_score,
                'components': score_components,
                'historical_stats': strategy_performance[strategy_name]
            }
        
        return scores
    
    async def _get_recent_performance(self, symbol: str, strategy: str, days: int = 7) -> float:
        """Получает производительность стратегии за последние N дней"""
        db = SessionLocal()
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            recent_trades = db.query(Trade).filter(
                and_(
                    Trade.symbol == symbol,
                    Trade.strategy == strategy,
                    Trade.status == 'closed',
                    Trade.closed_at >= cutoff_date
                )
            ).all()
            
            if not recent_trades:
                return 0.5  # Нейтральный скор
            
            # Рассчитываем метрики
            total_profit = sum(t.profit for t in recent_trades)
            win_rate = len([t for t in recent_trades if t.profit > 0]) / len(recent_trades)
            
            # Простой скор на основе прибыльности
            if total_profit > 0:
                return min(0.5 + (total_profit / 1000), 1.0)  # Максимум 1.0
            else:
                return max(0.5 + (total_profit / 1000), 0.0)  # Минимум 0.0
                
        finally:
            db.close()
    
    async def _get_optimal_parameters(self, strategy: str, symbol: str, 
                                    market_conditions: Dict[str, Any]) -> Dict[str, Any]:
        """Получает оптимальные параметры для стратегии"""
        # Базовые параметры для каждой стратегии
        base_params = {
            'RSIStrategy': {
                'period': 14,
                'overbought': 70,
                'oversold': 30,
                'take_profit': 0.02,
                'stop_loss': 0.01
            },
            'MACDStrategy': {
                'fast_period': 12,
                'slow_period': 26,
                'signal_period': 9,
                'take_profit': 0.025,
                'stop_loss': 0.015
            },
            'BollingerBandsStrategy': {
                'period': 20,
                'std_dev': 2,
                'take_profit': 0.015,
                'stop_loss': 0.01
            },
            'EMAStrategy': {
                'fast_period': 9,
                'slow_period': 21,
                'take_profit': 0.02,
                'stop_loss': 0.012
            },
            'VolumeStrategy': {
                'volume_threshold': 1.5,
                'price_change_threshold': 0.005,
                'take_profit': 0.018,
                'stop_loss': 0.01
            }
        }
        
        params = base_params.get(strategy, {}).copy()
        
        # Адаптация параметров под рыночные условия
        if market_conditions.get('volatility') == 'high':
            # Увеличиваем стопы и тейки при высокой волатильности
            params['take_profit'] = params.get('take_profit', 0.02) * 1.5
            params['stop_loss'] = params.get('stop_loss', 0.01) * 1.5
        elif market_conditions.get('volatility') == 'low':
            # Уменьшаем при низкой волатильности
            params['take_profit'] = params.get('take_profit', 0.02) * 0.7
            params['stop_loss'] = params.get('stop_loss', 0.01) * 0.8
        
        # Адаптация под тренд
        if market_conditions.get('trend') == 'bullish':
            # При бычьем тренде увеличиваем тейк профит
            params['take_profit'] = params.get('take_profit', 0.02) * 1.2
        elif market_conditions.get('trend') == 'bearish':
            # При медвежьем тренде уменьшаем стоп лосс
            params['stop_loss'] = params.get('stop_loss', 0.01) * 0.8
        
        return params
    
    async def _save_strategy_selection(self, symbol: str, selection: Dict[str, Any]):
        """Сохраняет выбор стратегии в БД для анализа"""
        # Здесь можно сохранить выбор в отдельную таблицу для последующего анализа
        # Это поможет улучшить алгоритм выбора стратегий
        pass
    
    async def load_strategy_performance(self):
        """Загружает историческую производительность стратегий"""
        db = SessionLocal()
        try:
            # Загружаем агрегированную статистику из таблицы strategy_performance
            # если она существует
            pass
        finally:
            db.close()
    
    async def update_strategy_performance(self):
        """Обновляет статистику производительности стратегий"""
        db = SessionLocal()
        try:
            # Агрегируем данные по закрытым сделкам
            # и обновляем таблицу strategy_performance
            symbols = db.query(Trade.symbol).distinct().all()
            
            for symbol_tuple in symbols:
                symbol = symbol_tuple[0]
                
                # Анализируем по разным рыночным условиям
                for condition in ['trending_up', 'trending_down', 'sideways', 'volatile']:
                    # Здесь нужно сопоставить сделки с рыночными условиями
                    # и рассчитать производительность
                    pass
                    
        finally:
            db.close()
    
    def get_active_strategy(self, symbol: str) -> Optional[str]:
        """Получает текущую активную стратегию для символа"""
        if symbol in self.active_strategies:
            return self.active_strategies[symbol].get('strategy')
        return None
    
    def get_strategy_confidence(self, symbol: str) -> float:
        """Получает уверенность в текущей стратегии"""
        if symbol in self.active_strategies:
            return self.active_strategies[symbol].get('score', 0)
        return 0
    
    async def should_switch_strategy(self, symbol: str, current_features: pd.DataFrame) -> bool:
        """Определяет, нужно ли переключить стратегию"""
        if symbol not in self.active_strategies:
            return True
        
        active_strategy = self.active_strategies[symbol]
        
        # Проверяем время с последнего выбора
        time_since_selection = (datetime.utcnow() - active_strategy['selected_at']).total_seconds()
        
        # Не меняем стратегию слишком часто
        if time_since_selection < 300:  # 5 минут
            return False
        
        # Получаем новое ML предсказание
        ml_prediction = await self.ml_trainer.predict_direction(symbol, current_features)
        
        # Если уверенность ML сильно изменилась
        if ml_prediction and abs(ml_prediction['confidence'] - active_strategy['ml_confidence']) > 0.2:
            return True
        
        # Если производительность стратегии упала
        recent_perf = await self._get_recent_performance(symbol, active_strategy['strategy'], days=1)
        if recent_perf < 0.3:  # Плохая производительность
            return True
        
        return False