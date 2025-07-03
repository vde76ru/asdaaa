#!/usr/bin/env python3
"""
ОБНОВЛЕННЫЙ SIGNAL PROCESSOR - Центральный обработчик торговых сигналов
Файл: src/bot/signal_processor.py

✅ ОБЪЕДИНЕНО:
- Существующая функциональность из проекта
- Безопасная работа с весами стратегий
- Улучшенная обработка конфигурации
- Расширенная система валидации
"""

import asyncio
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
import logging
import json

# ✅ Безопасный импорт конфигурации
try:
    from ..core.unified_config import unified_config as config
    CONFIG_AVAILABLE = True
except ImportError:
    CONFIG_AVAILABLE = False
    config = None

# Попытка импорта существующих компонентов
try:
    from ..common.types import UnifiedTradingSignal as TradingSignal
    TRADING_SIGNAL_AVAILABLE = True
except ImportError:
    TRADING_SIGNAL_AVAILABLE = False
    TradingSignal = None

try:
    from ..core.database import SessionLocal
    from ..core.models import Signal, Trade
    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False
    SessionLocal = None

logger = logging.getLogger(__name__)

class SignalQuality(Enum):
    """Качество торгового сигнала"""
    EXCELLENT = "excellent"    # >0.8 уверенности
    GOOD = "good"             # 0.6-0.8 уверенности
    AVERAGE = "average"       # 0.4-0.6 уверенности
    POOR = "poor"             # 0.2-0.4 уверенности
    INVALID = "invalid"       # <0.2 уверенности

class SignalStatus(Enum):
    """Статус обработки сигнала"""
    PENDING = "pending"
    VALIDATED = "validated"
    FILTERED = "filtered"
    AGGREGATED = "aggregated"
    PROCESSED = "processed"
    REJECTED = "rejected"

@dataclass
class ProcessedSignal:
    """Обработанный торговый сигнал"""
    original_signal: TradingSignal
    strategy_name: str
    symbol: str
    quality: SignalQuality
    confidence_adjusted: float     # Скорректированная уверенность
    priority: int                  # Приоритет 1-10 (10 - наивысший)
    risk_score: float             # Оценка риска 0-1
    timestamp: datetime
    validation_results: Dict[str, Any] = field(default_factory=dict)
    status: SignalStatus = SignalStatus.PENDING
    # ✅ Добавлены недостающие поля для совместимости
    contributing_strategies: List[str] = field(default_factory=list)
    strategy_weights: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    aggregated_stop_loss: Optional[float] = None
    aggregated_take_profit: Optional[float] = None

@dataclass 
class AggregatedSignal:
    """Агрегированный сигнал от нескольких стратегий"""
    symbol: str
    action: str                   # BUY, SELL, WAIT
    confidence: float            # Консенсус уверенности
    strategies_count: int        # Количество стратегий
    strategy_names: List[str]    # Имена стратегий
    individual_signals: List[ProcessedSignal]
    consensus_strength: float    # Сила консенсуса 0-1
    conflicting_signals: int     # Количество противоречивых
    avg_stop_loss: float
    avg_take_profit: float
    recommended_position_size: float
    timestamp: datetime
    # ✅ Добавлены поля для совместимости
    price: float = 0.0
    contributing_strategies: List[str] = field(default_factory=list)
    strategy_weights: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    risk_score: float = 0.0

class SignalProcessor:
    """
    ✅ ОБНОВЛЕННЫЙ ПРОЦЕССОР СИГНАЛОВ
    
    Агрегирует и обрабатывает торговые сигналы от различных стратегий
    с безопасной обработкой весов и конфигурации.
    
    Архитектура:
    ┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
    │   ВХОДЯЩИЕ      │───▶│   ВАЛИДАЦИЯ      │───▶│   ФИЛЬТРАЦИЯ    │
    │   СИГНАЛЫ       │    │   - Качество     │    │   - Дубликаты   │
    │   - Стратегии   │    │   - Полнота      │    │   - Слабые       │
    │   - ML модели   │    │   - Логичность   │    │   - Устаревшие   │
    └─────────────────┘    └──────────────────┘    └─────────────────┘
             │                        │                        │
             ▼                        ▼                        ▼
    ┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
    │   АГРЕГАЦИЯ     │    │   ПРИОРИТИЗАЦИЯ  │    │   ИСПОЛНЕНИЕ    │
    │   - Консенсус   │    │   - Качество     │    │   - Лучшие      │
    │   - Противоречия│    │   - Срочность    │    │   - Вовремя     │
    │   - Веса        │    │   - Риски        │    │   - Корректно   │
    └─────────────────┘    └──────────────────┘    └─────────────────┘
    """
    
    def __init__(self, max_signal_age_minutes: int = 5):
        """
        Инициализация процессора сигналов
        
        Args:
            max_signal_age_minutes: Максимальный возраст сигнала в минутах
        """
        self.max_signal_age = timedelta(minutes=max_signal_age_minutes)
        self.processed_signals = deque(maxlen=1000)
        self.signal_cache = {}
        self.last_signals_by_strategy = defaultdict(lambda: None)
        
        # ✅ ИСПРАВЛЕНО: Безопасная загрузка настроек
        self._load_settings()
        
        # ✅ ИСПРАВЛЕНО: Безопасная инициализация весов стратегий
        self._initialize_strategy_weights()
        
        logger.info("✅ SignalProcessor инициализирован")
        logger.info(f"📋 Конфигурация доступна: {CONFIG_AVAILABLE}")
        logger.info(f"🎯 Min confidence: {self.min_confidence}")
    
    def _load_settings(self):
        """✅ ИСПРАВЛЕНО: Безопасная загрузка настроек из конфигурации"""
        if CONFIG_AVAILABLE and config:
            try:
                self.min_confidence = getattr(config, 'MIN_STRATEGY_CONFIDENCE', 0.6)
            except:
                self.min_confidence = 0.6
        else:
            self.min_confidence = 0.6
        
        # Настройки фильтрации
        self.consensus_threshold = 0.6  # Минимальный консенсус для агрегации
        self.max_conflicting_ratio = 0.3  # Максимум противоречий
        
        logger.info(f"📋 Настройки загружены: min_confidence={self.min_confidence}")
    
    def _initialize_strategy_weights(self):
        """✅ ИСПРАВЛЕНО: Безопасная инициализация весов стратегий"""
        # Веса по умолчанию
        default_weights = {
            'multi_indicator': 0.25,  # 25%
            'momentum': 0.20,         # 20%
            'mean_reversion': 0.15,   # 15%
            'breakout': 0.15,         # 15%
            'scalping': 0.10,         # 10%
            'swing': 0.10,            # 10%
            'ml_prediction': 0.05     # 5%
        }
        
        # Пытаемся загрузить из конфигурации
        if CONFIG_AVAILABLE and config:
            try:
                config_weights = {}
                
                # Безопасно получаем веса из конфигурации
                weight_attributes = [
                    ('multi_indicator', 'WEIGHT_MULTI_INDICATOR'),
                    ('momentum', 'WEIGHT_MOMENTUM'),
                    ('mean_reversion', 'WEIGHT_MEAN_REVERSION'),
                    ('breakout', 'WEIGHT_BREAKOUT'),
                    ('scalping', 'WEIGHT_SCALPING'),
                    ('swing', 'WEIGHT_SWING'),
                    ('ml_prediction', 'WEIGHT_ML_PREDICTION')
                ]
                
                for strategy_name, attr_name in weight_attributes:
                    try:
                        weight = getattr(config, attr_name, default_weights[strategy_name])
                        config_weights[strategy_name] = float(weight)
                    except (AttributeError, ValueError):
                        config_weights[strategy_name] = default_weights[strategy_name]
                        logger.warning(f"⚠️ Не удалось загрузить {attr_name}, используем значение по умолчанию")
                
                # Проверяем сумму весов
                total_weight = sum(config_weights.values())
                if abs(total_weight - 1.0) > 0.01:
                    logger.warning(f"⚠️ Сумма весов ({total_weight:.3f}) != 1.0, нормализуем")
                    # Нормализуем веса
                    for strategy in config_weights:
                        config_weights[strategy] /= total_weight
                
                self.strategy_weights = config_weights
                logger.info("✅ Веса стратегий загружены из конфигурации")
                
            except Exception as e:
                logger.warning(f"⚠️ Ошибка загрузки весов из конфигурации: {e}")
                self.strategy_weights = default_weights
        else:
            self.strategy_weights = default_weights
            logger.info("📋 Используются веса стратегий по умолчанию")
        
        # Логируем веса
        logger.info("⚖️ Веса стратегий:")
        for strategy, weight in self.strategy_weights.items():
            logger.info(f"   {strategy}: {weight:.2%}")
    
    async def process_signal(self, signal: TradingSignal, strategy_name: str,
                           symbol: str) -> Optional[ProcessedSignal]:
        """
        Основная функция обработки одиночного сигнала
        
        Args:
            signal: Торговый сигнал от стратегии
            strategy_name: Имя стратегии
            symbol: Торговая пара
            
        Returns:
            ProcessedSignal или None если сигнал отклонен
        """
        try:
            logger.debug(
                f"🔄 Обработка сигнала {strategy_name}: {signal.action} "
                f"для {symbol} (confidence: {signal.confidence:.2f})"
            )
            
            # Шаг 1: Валидация сигнала
            validation_results = await self._validate_signal(signal, strategy_name, symbol)
            if not validation_results['is_valid']:
                logger.debug(f"❌ Сигнал отклонен: {validation_results['reason']}")
                return None
            
            # Шаг 2: Определение качества
            quality = self._determine_signal_quality(signal, validation_results)
            
            # Шаг 3: Корректировка уверенности
            adjusted_confidence = self._adjust_confidence(
                signal, strategy_name, validation_results
            )
            
            # Шаг 4: Расчет приоритета
            priority = self._calculate_priority(signal, strategy_name, quality)
            
            # Шаг 5: Оценка риска
            risk_score = await self._assess_risk(signal, symbol)
            
            # Создаем обработанный сигнал
            processed = ProcessedSignal(
                original_signal=signal,
                strategy_name=strategy_name,
                symbol=symbol,
                quality=quality,
                confidence_adjusted=adjusted_confidence,
                priority=priority,
                risk_score=risk_score,
                timestamp=datetime.utcnow(),
                validation_results=validation_results,
                status=SignalStatus.VALIDATED,
                # Добавляем новые поля
                contributing_strategies=[strategy_name],
                strategy_weights={strategy_name: self.strategy_weights.get(strategy_name, 1.0)},
                metadata={
                    'processor_version': '2.0',
                    'config_available': CONFIG_AVAILABLE
                }
            )
            
            # Сохраняем в кеше
            self._cache_signal(processed)
            
            logger.info(
                f"✅ Сигнал обработан: {strategy_name} → {signal.action} "
                f"(quality: {quality.value}, priority: {priority})"
            )
            
            return processed
            
        except Exception as e:
            logger.error(f"❌ Ошибка обработки сигнала: {e}")
            return None
    
    async def aggregate_signals(self, signals: List[ProcessedSignal],
                              symbol: str) -> Optional[AggregatedSignal]:
        """
        ✅ УЛУЧШЕНО: Агрегация нескольких сигналов в один консенсусный
        
        Args:
            signals: Список обработанных сигналов
            symbol: Торговая пара
            
        Returns:
            AggregatedSignal или None если консенсус не достигнут
        """
        try:
            if not signals:
                return None
            
            logger.debug(f"🔄 Агрегация {len(signals)} сигналов для {symbol}")
            
            # Фильтруем валидные сигналы
            valid_signals = self._filter_valid_signals(signals)
            if not valid_signals:
                logger.debug(f"❌ Нет валидных сигналов для агрегации")
                return None
            
            # Группируем по действиям
            actions_groups = self._group_signals_by_action(valid_signals)
            
            # Ищем консенсус
            consensus_action, consensus_signals = self._find_consensus(actions_groups)
            if not consensus_action:
                logger.debug(f"❌ Не найден консенсус для {symbol}")
                return None
            
            # Рассчитываем агрегированные параметры
            aggregated_params = self._calculate_aggregated_parameters(consensus_signals)
            
            # Создаем агрегированный сигнал
            aggregated = AggregatedSignal(
                symbol=symbol,
                action=consensus_action,
                confidence=aggregated_params['confidence'],
                strategies_count=len(consensus_signals),
                strategy_names=[s.strategy_name for s in consensus_signals],
                individual_signals=consensus_signals,
                consensus_strength=len(consensus_signals) / len(valid_signals),
                conflicting_signals=len(valid_signals) - len(consensus_signals),
                avg_stop_loss=aggregated_params['stop_loss'],
                avg_take_profit=aggregated_params['take_profit'],
                recommended_position_size=aggregated_params['position_size'],
                timestamp=datetime.utcnow(),
                # Добавляем новые поля
                price=aggregated_params.get('price', 0.0),
                contributing_strategies=[s.strategy_name for s in consensus_signals],
                strategy_weights=self._get_contributing_weights(consensus_signals),
                metadata={
                    'aggregation_method': 'weighted_consensus',
                    'total_signals': len(signals),
                    'valid_signals': len(valid_signals),
                    'processor_version': '2.0'
                },
                risk_score=self._calculate_aggregated_risk(consensus_signals)
            )
            
            logger.info(
                f"✅ Агрегирован сигнал для {symbol}: {consensus_action} "
                f"(стратегий: {len(consensus_signals)}, консенсус: {aggregated.consensus_strength:.2f})"
            )
            
            return aggregated
            
        except Exception as e:
            logger.error(f"❌ Ошибка агрегации сигналов: {e}")
            return None
    
    def _get_contributing_weights(self, signals: List[ProcessedSignal]) -> Dict[str, float]:
        """Получить веса участвующих стратегий"""
        weights = {}
        for signal in signals:
            strategy = signal.strategy_name
            weights[strategy] = self.strategy_weights.get(strategy, 1.0)
        return weights
    
    def _calculate_aggregated_risk(self, signals: List[ProcessedSignal]) -> float:
        """Расчет агрегированного риска"""
        if not signals:
            return 0.5
        
        # Средневзвешенный риск
        total_weight = sum(self.strategy_weights.get(s.strategy_name, 1.0) for s in signals)
        if total_weight == 0:
            return 0.5
        
        weighted_risk = sum(
            s.risk_score * self.strategy_weights.get(s.strategy_name, 1.0)
            for s in signals
        ) / total_weight
        
        return weighted_risk
    
    async def _validate_signal(self, signal: TradingSignal, strategy_name: str, 
                             symbol: str) -> Dict[str, Any]:
        """Валидация входящего сигнала"""
        try:
            # Проверка базовых полей
            if not signal.symbol or not signal.action:
                return {'is_valid': False, 'reason': 'Неполный сигнал'}
            
            # Проверка действия
            if signal.action not in ['BUY', 'SELL', 'HOLD', 'WAIT']:
                return {'is_valid': False, 'reason': f'Неизвестное действие: {signal.action}'}
            
            # Проверка уверенности
            if signal.confidence < self.min_confidence:
                return {'is_valid': False, 'reason': f'Низкая уверенность: {signal.confidence:.2f}'}
            
            # Проверка возраста сигнала
            if datetime.utcnow() - signal.timestamp > self.max_signal_age:
                return {'is_valid': False, 'reason': 'Устаревший сигнал'}
            
            # Проверка цены
            if signal.price <= 0:
                return {'is_valid': False, 'reason': f'Некорректная цена: {signal.price}'}
            
            return {
                'is_valid': True,
                'checks_passed': ['symbol', 'action', 'confidence', 'age', 'price'],
                'signal_age_seconds': (datetime.utcnow() - signal.timestamp).total_seconds()
            }
            
        except Exception as e:
            return {'is_valid': False, 'reason': f'Ошибка валидации: {str(e)}'}
    
    def _determine_signal_quality(self, signal: TradingSignal, 
                                validation_results: Dict[str, Any]) -> SignalQuality:
        """Определение качества сигнала"""
        confidence = signal.confidence
        
        if confidence >= 0.8:
            return SignalQuality.EXCELLENT
        elif confidence >= 0.6:
            return SignalQuality.GOOD
        elif confidence >= 0.4:
            return SignalQuality.AVERAGE
        elif confidence >= 0.2:
            return SignalQuality.POOR
        else:
            return SignalQuality.INVALID
    
    def _adjust_confidence(self, signal: TradingSignal, strategy_name: str,
                         validation_results: Dict[str, Any]) -> float:
        """Корректировка уверенности на основе качества стратегии"""
        base_confidence = signal.confidence
        
        # Применяем вес стратегии
        strategy_weight = self.strategy_weights.get(strategy_name, 1.0)
        adjusted = base_confidence * strategy_weight
        
        # Учитываем возраст сигнала
        signal_age = validation_results.get('signal_age_seconds', 0)
        age_factor = max(0.5, 1.0 - (signal_age / 300))  # Снижение за 5 минут
        
        return min(1.0, adjusted * age_factor)
    
    def _calculate_priority(self, signal: TradingSignal, strategy_name: str,
                          quality: SignalQuality) -> int:
        """Расчет приоритета сигнала"""
        # Базовый приоритет по качеству
        quality_priority = {
            SignalQuality.EXCELLENT: 10,
            SignalQuality.GOOD: 8,
            SignalQuality.AVERAGE: 6,
            SignalQuality.POOR: 4,
            SignalQuality.INVALID: 1
        }
        
        base_priority = quality_priority.get(quality, 1)
        
        # Бонус за стратегию
        strategy_weight = self.strategy_weights.get(strategy_name, 1.0)
        strategy_bonus = int(strategy_weight * 2)
        
        return min(10, base_priority + strategy_bonus)
    
    async def _assess_risk(self, signal: TradingSignal, symbol: str) -> float:
        """Оценка риска сигнала"""
        base_risk = 1.0 - signal.confidence
        
        # Дополнительные факторы риска можно добавить здесь
        # например, волатильность символа, время суток и т.д.
        
        return max(0.0, min(1.0, base_risk))
    
    def _cache_signal(self, signal: ProcessedSignal):
        """Сохранение сигнала в кеш"""
        cache_key = f"{signal.strategy_name}_{signal.symbol}_{signal.original_signal.action}"
        self.signal_cache[cache_key] = signal
        self.last_signals_by_strategy[signal.strategy_name] = signal
        self.processed_signals.append(signal)
        
        # Очистка старых сигналов
        self._cleanup_old_signals()
    
    def _cleanup_old_signals(self):
        """Очистка устаревших сигналов из кеша"""
        current_time = datetime.utcnow()
        keys_to_remove = []
        
        for key, signal in self.signal_cache.items():
            if current_time - signal.timestamp > self.max_signal_age:
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self.signal_cache[key]
    
    def _filter_valid_signals(self, signals: List[ProcessedSignal]) -> List[ProcessedSignal]:
        """Фильтрация валидных сигналов"""
        try:
            valid = []
            current_time = datetime.utcnow()
            
            for signal in signals:
                # Проверяем возраст
                if current_time - signal.timestamp > self.max_signal_age:
                    continue
                
                # Проверяем качество
                if signal.quality in [SignalQuality.INVALID, SignalQuality.POOR]:
                    continue
                
                # Проверяем не WAIT сигналы
                if signal.original_signal.action == 'WAIT':
                    continue
                
                valid.append(signal)
            
            return valid
            
        except Exception as e:
            logger.error(f"❌ Ошибка фильтрации сигналов: {e}")
            return signals
    
    def _group_signals_by_action(self, signals: List[ProcessedSignal]) -> Dict[str, List[ProcessedSignal]]:
        """Группировка сигналов по действиям"""
        groups = defaultdict(list)
        
        for signal in signals:
            action = signal.original_signal.action
            groups[action].append(signal)
        
        return dict(groups)
    
    def _find_consensus(self, actions_groups: Dict[str, List[ProcessedSignal]]) -> Tuple[Optional[str], List[ProcessedSignal]]:
        """Поиск консенсуса среди сигналов"""
        try:
            if not actions_groups:
                return None, []
            
            # Находим действие с наибольшим взвешенным голосованием
            weighted_votes = {}
            
            for action, signals in actions_groups.items():
                total_weight = sum(
                    signal.confidence_adjusted * self.strategy_weights.get(signal.strategy_name, 1.0)
                    for signal in signals
                )
                weighted_votes[action] = total_weight
            
            # Находим лучшее действие
            best_action = max(weighted_votes.keys(), key=lambda x: weighted_votes[x])
            best_signals = actions_groups[best_action]
            
            # Проверяем силу консенсуса
            total_weight = sum(weighted_votes.values())
            consensus_ratio = weighted_votes[best_action] / total_weight if total_weight > 0 else 0
            
            if consensus_ratio >= self.consensus_threshold:
                return best_action, best_signals
            else:
                return None, []
                
        except Exception as e:
            logger.error(f"❌ Ошибка поиска консенсуса: {e}")
            return None, []
    
    def _calculate_aggregated_parameters(self, signals: List[ProcessedSignal]) -> Dict[str, float]:
        """Расчет агрегированных параметров"""
        try:
            if not signals:
                return {
                    'confidence': 0.0,
                    'stop_loss': 0.0,
                    'take_profit': 0.0,
                    'position_size': 0.0,
                    'price': 0.0
                }
            
            # Взвешенные параметры по уверенности
            total_weight = sum(s.confidence_adjusted for s in signals)
            
            if total_weight == 0:
                weights = [1/len(signals)] * len(signals)
            else:
                weights = [s.confidence_adjusted / total_weight for s in signals]
            
            # Агрегированная уверенность
            confidence = sum(s.confidence_adjusted * w for s, w in zip(signals, weights))
            
            # Средние stop_loss и take_profit
            stop_losses = [getattr(s.original_signal, 'stop_loss', None) for s in signals]
            take_profits = [getattr(s.original_signal, 'take_profit', None) for s in signals]
            prices = [s.original_signal.price for s in signals]
            
            stop_loss = np.mean([sl for sl in stop_losses if sl is not None]) if any(stop_losses) else 0.0
            take_profit = np.mean([tp for tp in take_profits if tp is not None]) if any(take_profits) else 0.0
            price = np.mean(prices) if prices else 0.0
            
            # Размер позиции на основе консенсуса
            position_size = min(1.0, confidence * len(signals) / 3)
            
            return {
                'confidence': confidence,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'position_size': position_size,
                'price': price
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка расчета агрегированных параметров: {e}")
            return {
                'confidence': 0.0,
                'stop_loss': 0.0,
                'take_profit': 0.0,
                'position_size': 0.0,
                'price': 0.0
            }
    
    def get_recent_signals(self, symbol: Optional[str] = None, 
                         strategy: Optional[str] = None,
                         limit: int = 10) -> List[ProcessedSignal]:
        """Получение недавних сигналов с фильтрацией"""
        try:
            signals = list(self.processed_signals)
            
            # Фильтрация по символу
            if symbol:
                signals = [s for s in signals if s.symbol == symbol]
            
            # Фильтрация по стратегии
            if strategy:
                signals = [s for s in signals if s.strategy_name == strategy]
            
            # Сортировка по времени (новые первые)
            signals.sort(key=lambda x: x.timestamp, reverse=True)
            
            return signals[:limit]
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения недавних сигналов: {e}")
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """Получение статистики работы процессора"""
        try:
            total_signals = len(self.processed_signals)
            
            if total_signals == 0:
                return {
                    'total_processed': 0,
                    'quality_distribution': {},
                    'strategy_distribution': {},
                    'avg_confidence': 0.0,
                    'strategy_weights': self.strategy_weights.copy(),
                    'config_available': CONFIG_AVAILABLE
                }
            
            # Распределение по качеству
            quality_dist = defaultdict(int)
            for signal in self.processed_signals:
                quality_dist[signal.quality.value] += 1
            
            # Распределение по стратегиям
            strategy_dist = defaultdict(int)
            for signal in self.processed_signals:
                strategy_dist[signal.strategy_name] += 1
            
            # Средняя уверенность
            avg_confidence = np.mean([
                s.confidence_adjusted for s in self.processed_signals
            ])
            
            return {
                'total_processed': total_signals,
                'quality_distribution': dict(quality_dist),
                'strategy_distribution': dict(strategy_dist),
                'avg_confidence': avg_confidence,
                'active_signals': len(self.signal_cache),
                'strategy_weights': self.strategy_weights.copy(),
                'min_confidence': self.min_confidence,
                'consensus_threshold': self.consensus_threshold,
                'config_available': CONFIG_AVAILABLE
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики: {e}")
            return {
                'error': str(e),
                'config_available': CONFIG_AVAILABLE
            }

# =================================================================
# ГЛОБАЛЬНЫЕ ФУНКЦИИ
# =================================================================

# Глобальный экземпляр
signal_processor = None

def get_signal_processor() -> SignalProcessor:
    """Получить глобальный экземпляр процессора сигналов"""
    global signal_processor
    
    if signal_processor is None:
        signal_processor = SignalProcessor()
    
    return signal_processor

def create_signal_processor(**kwargs) -> SignalProcessor:
    """Создать новый экземпляр процессора сигналов"""
    return SignalProcessor(**kwargs)

# ✅ Создаем глобальный экземпляр
signal_processor = SignalProcessor()

# Экспорты
__all__ = [
    'SignalProcessor',
    'ProcessedSignal',
    'AggregatedSignal',
    'SignalQuality',
    'SignalStatus',
    'TradingSignal',
    'get_signal_processor',
    'create_signal_processor',
    'signal_processor'
]