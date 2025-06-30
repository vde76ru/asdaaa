"""
Автоматический селектор стратегий с машинным обучением
Путь: src/strategies/auto_strategy_selector.py

Этот модуль анализирует рыночные условия и автоматически выбирает
оптимальную стратегию для каждой торговой пары.
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import ta
import logging
from dataclasses import dataclass
from collections import defaultdict
import pickle
import json
from pathlib import Path

from ..core.database import SessionLocal
from ..core.models import Trade, Signal, TradeStatus
from ..logging.smart_logger import get_clean_logger
from ..analysis.market_analyzer import MarketAnalyzer

logger = get_clean_logger(__name__)

@dataclass
class MarketCondition:
    """Описание текущего состояния рынка"""
    trend: str  # 'UPTREND', 'DOWNTREND', 'SIDEWAYS'
    volatility: str  # 'LOW', 'MEDIUM', 'HIGH'
    volume: str  # 'LOW', 'NORMAL', 'HIGH'
    momentum: float  # -100 to 100
    support_resistance_ratio: float  # Близость к уровням
    market_phase: str  # 'ACCUMULATION', 'MARKUP', 'DISTRIBUTION', 'MARKDOWN'
    confidence: float  # 0-1

@dataclass
class StrategyPerformance:
    """Производительность стратегии в определенных условиях"""
    strategy_name: str
    win_rate: float
    average_profit: float
    profit_factor: float
    max_drawdown: float
    sharpe_ratio: float
    trades_count: int
    last_updated: datetime

class AutoStrategySelector:
    """
    Интеллектуальный селектор стратегий
    
    Особенности:
    1. Анализирует текущие рыночные условия
    2. Изучает историческую производительность стратегий
    3. Адаптируется к изменениям рынка
    4. Использует машинное обучение для улучшения выбора
    """
    
    def __init__(self):
        self.analyzer = MarketAnalyzer()
        
        # Доступные стратегии
        self.available_strategies = [
            'momentum',           # Для трендовых рынков
            'multi_indicator',    # Универсальная
            'scalping',          # Для боковых рынков с низкой волатильностью
            'safe_multi_indicator',  # Консервативная для высокой волатильности
            'conservative'       # Для неопределенных условий
        ]
        
        # Кэш производительности стратегий
        self.performance_cache: Dict[str, Dict[str, StrategyPerformance]] = defaultdict(dict)
        
        # Путь для сохранения обученной модели
        self.model_path = Path("models/strategy_selector.pkl")
        self.model_path.parent.mkdir(exist_ok=True)
        
        # Загружаем обученную модель если есть
        self.ml_model = self._load_model()
        
        # История выбора стратегий для обучения
        self.selection_history = []
        
        logger.info("✅ AutoStrategySelector инициализирован")
    
    async def select_best_strategy(self, symbol: str, timeframe: str = '5m') -> Tuple[str, float]:
        """
        Выбрать лучшую стратегию для символа
        
        Args:
            symbol: Торговая пара
            timeframe: Временной интервал
            
        Returns:
            Tuple[стратегия, уверенность]
        """
        try:
            logger.info(f"🎯 Выбираем стратегию для {symbol}")
            
            # Анализируем рынок
            market_data = await self.analyzer.analyze_symbol(symbol)
            if not market_data:
                logger.warning(f"Нет данных для {symbol}, используем дефолтную стратегию")
                return 'safe_multi_indicator', 0.5
            
            # Определяем рыночные условия
            market_condition = self._analyze_market_conditions(market_data)
            logger.info(f"📊 Рыночные условия {symbol}: {market_condition.trend}, "
                       f"волатильность: {market_condition.volatility}, "
                       f"фаза: {market_condition.market_phase}")
            
            # Получаем историческую производительность
            performance_data = self._get_historical_performance(symbol, market_condition)
            
            # Выбираем стратегию
            if self.ml_model:
                # Используем ML модель
                best_strategy, confidence = self._ml_select_strategy(
                    symbol, market_condition, performance_data
                )
            else:
                # Используем правила
                best_strategy, confidence = self._rule_based_selection(
                    market_condition, performance_data
                )
            
            # Сохраняем выбор для обучения
            self._save_selection(symbol, market_condition, best_strategy)
            
            logger.info(f"✅ Выбрана стратегия '{best_strategy}' для {symbol} "
                       f"с уверенностью {confidence:.1%}")
            
            return best_strategy, confidence
            
        except Exception as e:
            logger.error(f"Ошибка выбора стратегии для {symbol}: {e}")
            return 'safe_multi_indicator', 0.3
    
    def _analyze_market_conditions(self, market_data: Dict) -> MarketCondition:
        """Анализ текущих рыночных условий"""
        try:
            df = market_data['df']
            current_price = market_data['current_price']
            
            # Определяем тренд
            trend = market_data['trend']['direction']
            trend_strength = market_data['trend']['strength']
            
            # Определяем волатильность
            volatility = market_data['volatility']
            if volatility['daily'] < 0.01:  # < 1%
                volatility_level = 'LOW'
            elif volatility['daily'] < 0.03:  # < 3%
                volatility_level = 'MEDIUM'
            else:
                volatility_level = 'HIGH'
            
            # Анализ объема
            volume_analysis = market_data['volume_analysis']
            if volume_analysis['ratio'] < 0.7:
                volume_level = 'LOW'
            elif volume_analysis['ratio'] < 1.3:
                volume_level = 'NORMAL'
            else:
                volume_level = 'HIGH'
            
            # Рассчитываем momentum
            momentum = self._calculate_momentum(df)
            
            # Близость к уровням поддержки/сопротивления
            sr_ratio = 0.5  # По умолчанию
            if market_data['support'] and market_data['resistance']:
                price_range = market_data['resistance'] - market_data['support']
                if price_range > 0:
                    sr_ratio = (current_price - market_data['support']) / price_range
            
            # Определяем рыночную фазу (упрощенный метод Вайкоффа)
            market_phase = self._determine_market_phase(
                df, trend, volume_analysis, volatility
            )
            
            # Рассчитываем общую уверенность
            confidence = self._calculate_condition_confidence(
                trend_strength, volatility, volume_analysis
            )
            
            return MarketCondition(
                trend=trend,
                volatility=volatility_level,
                volume=volume_level,
                momentum=momentum,
                support_resistance_ratio=sr_ratio,
                market_phase=market_phase,
                confidence=confidence
            )
            
        except Exception as e:
            logger.error(f"Ошибка анализа рыночных условий: {e}")
            # Возвращаем безопасные дефолтные значения
            return MarketCondition(
                trend='SIDEWAYS',
                volatility='MEDIUM',
                volume='NORMAL',
                momentum=0,
                support_resistance_ratio=0.5,
                market_phase='UNKNOWN',
                confidence=0.3
            )
    
    def _calculate_momentum(self, df: pd.DataFrame) -> float:
        """Расчет общего momentum (-100 to 100)"""
        try:
            # RSI momentum
            rsi = ta.momentum.rsi(df['close'], window=14).iloc[-1]
            rsi_momentum = (rsi - 50) * 2  # Масштабируем к -100...100
            
            # Price momentum
            price_change_5 = ((df['close'].iloc[-1] - df['close'].iloc[-5]) / 
                            df['close'].iloc[-5] * 100)
            price_change_10 = ((df['close'].iloc[-1] - df['close'].iloc[-10]) / 
                             df['close'].iloc[-10] * 100)
            
            # MACD momentum
            macd = ta.trend.MACD(df['close'])
            macd_momentum = macd.macd_diff().iloc[-1] * 100  # Масштабируем
            
            # Комбинированный momentum
            momentum = (rsi_momentum * 0.3 + 
                       price_change_5 * 0.2 + 
                       price_change_10 * 0.2 + 
                       np.clip(macd_momentum, -100, 100) * 0.3)
            
            return np.clip(momentum, -100, 100)
            
        except Exception as e:
            logger.error(f"Ошибка расчета momentum: {e}")
            return 0
    
    def _determine_market_phase(self, df: pd.DataFrame, trend: str, 
                               volume: Dict, volatility: Dict) -> str:
        """Определение фазы рынка по методу Вайкоффа"""
        try:
            # Упрощенное определение фазы
            if trend == 'SIDEWAYS' and volume['trend'] == 'DECREASING':
                return 'ACCUMULATION'  # Накопление
            elif trend == 'UPTREND' and volume['trend'] == 'INCREASING':
                return 'MARKUP'  # Рост
            elif trend == 'SIDEWAYS' and volume['trend'] == 'INCREASING':
                return 'DISTRIBUTION'  # Распределение
            elif trend == 'DOWNTREND':
                return 'MARKDOWN'  # Снижение
            else:
                return 'UNKNOWN'
                
        except Exception as e:
            logger.error(f"Ошибка определения фазы рынка: {e}")
            return 'UNKNOWN'
    
    def _calculate_condition_confidence(self, trend_strength: float, 
                                      volatility: Dict, volume: Dict) -> float:
        """Расчет уверенности в определении условий"""
        confidence = 0.5  # Базовая уверенность
        
        # Сильный тренд повышает уверенность
        if trend_strength > 5:
            confidence += 0.2
        
        # Нормальная волатильность повышает уверенность
        if 0.5 < volatility['daily'] < 3:
            confidence += 0.15
        
        # Подтверждение объемом
        if volume['price_correlation'] > 0.5:
            confidence += 0.15
        
        return min(confidence, 1.0)
    
    def _get_historical_performance(self, symbol: str, 
                                  condition: MarketCondition) -> Dict[str, StrategyPerformance]:
        """Получение исторической производительности стратегий"""
        # Проверяем кэш
        cache_key = f"{symbol}_{condition.trend}_{condition.volatility}"
        if cache_key in self.performance_cache:
            cached_data = self.performance_cache[cache_key]
            # Проверяем актуальность (обновляем раз в час)
            if any(p.last_updated > datetime.utcnow() - timedelta(hours=1) 
                   for p in cached_data.values()):
                return cached_data
        
        # Загружаем из базы данных
        performance_data = self._load_performance_from_db(symbol, condition)
        
        # Сохраняем в кэш
        self.performance_cache[cache_key] = performance_data
        
        return performance_data
    
    def _load_performance_from_db(self, symbol: str, 
                                condition: MarketCondition) -> Dict[str, StrategyPerformance]:
        """Загрузка производительности из БД"""
        db = SessionLocal()
        performance_data = {}
        
        try:
            # Для каждой стратегии считаем метрики
            for strategy in self.available_strategies:
                # Получаем сделки за последние 30 дней
                trades = db.query(Trade).filter(
                    Trade.symbol == symbol,
                    Trade.strategy == strategy,
                    Trade.status == TradeStatus.CLOSED,
                    Trade.created_at >= datetime.utcnow() - timedelta(days=30)
                ).all()
                
                if len(trades) < 5:  # Недостаточно данных
                    # Используем дефолтные значения
                    performance_data[strategy] = StrategyPerformance(
                        strategy_name=strategy,
                        win_rate=0.5,
                        average_profit=0,
                        profit_factor=1.0,
                        max_drawdown=0,
                        sharpe_ratio=0,
                        trades_count=len(trades),
                        last_updated=datetime.utcnow()
                    )
                    continue
                
                # Рассчитываем метрики
                profitable_trades = [t for t in trades if t.profit and t.profit > 0]
                win_rate = len(profitable_trades) / len(trades)
                
                profits = [t.profit for t in trades if t.profit is not None]
                average_profit = np.mean(profits) if profits else 0
                
                # Profit factor
                gross_profit = sum(p for p in profits if p > 0)
                gross_loss = abs(sum(p for p in profits if p < 0))
                profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
                
                # Max drawdown
                cumulative_profits = np.cumsum(profits)
                running_max = np.maximum.accumulate(cumulative_profits)
                drawdown = (running_max - cumulative_profits) / running_max
                max_drawdown = np.max(drawdown) if len(drawdown) > 0 else 0
                
                # Sharpe ratio (упрощенный)
                if len(profits) > 1:
                    returns = np.array(profits) / 1000  # Нормализация
                    sharpe_ratio = np.mean(returns) / np.std(returns) if np.std(returns) > 0 else 0
                else:
                    sharpe_ratio = 0
                
                performance_data[strategy] = StrategyPerformance(
                    strategy_name=strategy,
                    win_rate=win_rate,
                    average_profit=average_profit,
                    profit_factor=min(profit_factor, 10),  # Ограничиваем
                    max_drawdown=max_drawdown,
                    sharpe_ratio=sharpe_ratio,
                    trades_count=len(trades),
                    last_updated=datetime.utcnow()
                )
                
        except Exception as e:
            logger.error(f"Ошибка загрузки производительности: {e}")
        finally:
            db.close()
        
        return performance_data
    
    def _rule_based_selection(self, condition: MarketCondition, 
                            performance: Dict[str, StrategyPerformance]) -> Tuple[str, float]:
        """Выбор стратегии на основе правил"""
        scores = {}
        
        for strategy in self.available_strategies:
            score = 0
            
            # Базовый счет на основе производительности
            if strategy in performance:
                perf = performance[strategy]
                score += perf.win_rate * 30  # Win rate важнее всего
                score += min(perf.profit_factor, 3) * 20  # Profit factor
                score += (1 - perf.max_drawdown) * 15  # Меньше drawdown - лучше
                score += min(perf.sharpe_ratio, 2) * 10  # Sharpe ratio
                
                # Учитываем количество сделок (больше данных - больше доверия)
                confidence_factor = min(perf.trades_count / 20, 1.0)
                score *= confidence_factor
            
            # Корректировка на основе рыночных условий
            if strategy == 'momentum':
                # Momentum стратегия хороша для трендов
                if condition.trend in ['UPTREND', 'DOWNTREND']:
                    score *= 1.5
                if abs(condition.momentum) > 50:
                    score *= 1.3
                if condition.volatility == 'HIGH':
                    score *= 0.7  # Не очень для высокой волатильности
                    
            elif strategy == 'scalping':
                # Скальпинг для боковых рынков с низкой волатильностью
                if condition.trend == 'SIDEWAYS':
                    score *= 1.5
                if condition.volatility == 'LOW':
                    score *= 1.4
                if condition.volume == 'HIGH':
                    score *= 1.2
                    
            elif strategy == 'multi_indicator':
                # Универсальная стратегия
                score *= 1.1  # Небольшой бонус за универсальность
                if condition.confidence > 0.7:
                    score *= 1.2
                    
            elif strategy == 'safe_multi_indicator':
                # Безопасная для неопределенности
                if condition.confidence < 0.5:
                    score *= 1.5
                if condition.volatility == 'HIGH':
                    score *= 1.3
                    
            elif strategy == 'conservative':
                # Консервативная для защиты капитала
                if condition.market_phase == 'DISTRIBUTION':
                    score *= 1.4
                if condition.volatility == 'HIGH':
                    score *= 1.2
            
            scores[strategy] = score
        
        # Выбираем лучшую стратегию
        best_strategy = max(scores, key=scores.get)
        best_score = scores[best_strategy]
        
        # Нормализуем счет к уверенности (0-1)
        max_possible_score = 100
        confidence = min(best_score / max_possible_score, 1.0)
        
        # Минимальная уверенность
        confidence = max(confidence, 0.3)
        
        return best_strategy, confidence
    
    def _ml_select_strategy(self, symbol: str, condition: MarketCondition,
                          performance: Dict[str, StrategyPerformance]) -> Tuple[str, float]:
        """Выбор стратегии с помощью ML модели"""
        try:
            # Подготавливаем features
            features = self._prepare_ml_features(symbol, condition, performance)
            
            # Предсказание
            prediction = self.ml_model.predict([features])[0]
            confidence = self.ml_model.predict_proba([features]).max()
            
            # Мапим индекс к названию стратегии
            strategy = self.available_strategies[prediction]
            
            return strategy, confidence
            
        except Exception as e:
            logger.error(f"Ошибка ML предсказания: {e}")
            # Fallback к rule-based
            return self._rule_based_selection(condition, performance)
    
    def _prepare_ml_features(self, symbol: str, condition: MarketCondition,
                           performance: Dict[str, StrategyPerformance]) -> List[float]:
        """Подготовка features для ML модели"""
        features = []
        
        # Market condition features
        features.append(1 if condition.trend == 'UPTREND' else 
                       -1 if condition.trend == 'DOWNTREND' else 0)
        features.append(1 if condition.volatility == 'HIGH' else 
                       0.5 if condition.volatility == 'MEDIUM' else 0)
        features.append(1 if condition.volume == 'HIGH' else 
                       0.5 if condition.volume == 'NORMAL' else 0)
        features.append(condition.momentum / 100)  # Нормализованный
        features.append(condition.support_resistance_ratio)
        features.append(condition.confidence)
        
        # Performance features для каждой стратегии
        for strategy in self.available_strategies:
            if strategy in performance:
                perf = performance[strategy]
                features.extend([
                    perf.win_rate,
                    perf.average_profit / 100,  # Нормализация
                    min(perf.profit_factor, 5) / 5,  # Нормализация
                    perf.max_drawdown,
                    min(perf.sharpe_ratio, 3) / 3,  # Нормализация
                    min(perf.trades_count, 50) / 50  # Нормализация
                ])
            else:
                # Дефолтные значения
                features.extend([0.5, 0, 0.2, 0.1, 0, 0])
        
        return features
    
    def _save_selection(self, symbol: str, condition: MarketCondition, strategy: str):
        """Сохранение выбора для последующего обучения"""
        self.selection_history.append({
            'timestamp': datetime.utcnow(),
            'symbol': symbol,
            'condition': condition,
            'selected_strategy': strategy
        })
        
        # Ограничиваем размер истории
        if len(self.selection_history) > 10000:
            self.selection_history = self.selection_history[-5000:]
    
    def train_ml_model(self):
        """Обучение ML модели на исторических данных"""
        logger.info("🎓 Начинаем обучение ML модели...")
        
        try:
            # Загружаем исторические данные
            X, y = self._prepare_training_data()
            
            if len(X) < 100:
                logger.warning("Недостаточно данных для обучения")
                return
            
            # Используем простой RandomForest
            from sklearn.ensemble import RandomForestClassifier
            from sklearn.model_selection import train_test_split
            
            # Разделяем на train/test
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42
            )
            
            # Обучаем модель
            model = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                random_state=42
            )
            model.fit(X_train, y_train)
            
            # Оценка
            train_score = model.score(X_train, y_train)
            test_score = model.score(X_test, y_test)
            
            logger.info(f"✅ Модель обучена. Train score: {train_score:.2f}, "
                       f"Test score: {test_score:.2f}")
            
            # Сохраняем модель
            self.ml_model = model
            self._save_model()
            
        except Exception as e:
            logger.error(f"Ошибка обучения модели: {e}")
    
    def _prepare_training_data(self) -> Tuple[List[List[float]], List[int]]:
        """Подготовка данных для обучения"""
        X = []
        y = []
        
        db = SessionLocal()
        try:
            # Загружаем исторические сделки
            trades = db.query(Trade).filter(
                Trade.status == TradeStatus.CLOSED,
                Trade.created_at >= datetime.utcnow() - timedelta(days=90)
            ).all()
            
            # Группируем по стратегиям и условиям
            for trade in trades:
                # Здесь нужно восстановить условия рынка на момент сделки
                # Это упрощенная версия
                features = self._extract_features_from_trade(trade)
                if features:
                    X.append(features)
                    # Целевая переменная - индекс стратегии
                    strategy_idx = self.available_strategies.index(trade.strategy)
                    y.append(strategy_idx)
            
        finally:
            db.close()
        
        return X, y
    
    def _extract_features_from_trade(self, trade: Trade) -> Optional[List[float]]:
        """Извлечение features из исторической сделки"""
        # Это упрощенная версия - в реальности нужно восстановить
        # рыночные условия на момент сделки
        return None  # TODO: Implement
    
    def _save_model(self):
        """Сохранение обученной модели"""
        if self.ml_model:
            with open(self.model_path, 'wb') as f:
                pickle.dump(self.ml_model, f)
            logger.info(f"✅ Модель сохранена в {self.model_path}")
    
    def _load_model(self):
        """Загрузка обученной модели"""
        if self.model_path.exists():
            try:
                with open(self.model_path, 'rb') as f:
                    model = pickle.load(f)
                logger.info("✅ ML модель загружена")
                return model
            except Exception as e:
                logger.error(f"Ошибка загрузки модели: {e}")
        return None
    
    async def analyze_and_select_all_pairs(self, pairs: List[str]) -> Dict[str, Tuple[str, float]]:
        """
        Анализ и выбор стратегий для всех пар
        
        Returns:
            Dict[symbol, (strategy, confidence)]
        """
        results = {}
        
        for symbol in pairs:
            strategy, confidence = await self.select_best_strategy(symbol)
            results[symbol] = (strategy, confidence)
            
            # Небольшая задержка чтобы не перегружать API
            await asyncio.sleep(0.5)
        
        return results

# Создаем глобальный экземпляр
auto_strategy_selector = AutoStrategySelector()