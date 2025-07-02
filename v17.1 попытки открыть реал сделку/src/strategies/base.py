"""
Базовый класс для торговых стратегий с ML поддержкой - РАСШИРЕННАЯ ВЕРСИЯ
Файл: src/strategies/base.py
"""

import pandas as pd
import numpy as np
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass
import logging
import asyncio

logger = logging.getLogger(__name__)

@dataclass
class TradingSignal:
    """Структура торгового сигнала"""
    action: str  # 'BUY', 'SELL', 'WAIT'
    confidence: float
    price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    reason: str = ""
    risk_reward_ratio: Optional[float] = None
    indicators: Optional[Dict] = None
    ml_prediction: Optional[Dict] = None  # Добавлено для ML
    source: str = "technical"  # 'technical', 'ml', 'combined'

class BaseStrategy(ABC):
    """
    Базовый класс для всех торговых стратегий с ML поддержкой
    ИСПРАВЛЕНО: Обработка параметров конфигурации + ML интеграция
    """
    
    def __init__(self, strategy_name: str = "base", config: Optional[Dict] = None):
        """
        Инициализация базовой стратегии с ML поддержкой
        
        Args:
            strategy_name: Название стратегии (строка)
            config: Конфигурация стратегии (словарь, опционально)
        """
        # ✅ ИСПРАВЛЕНИЕ: Правильная обработка параметров
        self.name = strategy_name
        
        # Если config не передан или это строка, создаем пустой словарь
        if config is None or isinstance(config, str):
            self.config = {}
        else:
            self.config = config
            
        # Базовые настройки стратегии (можно переопределить в конфигурации)
        self.timeframe = self.config.get('timeframe', '1h')
        self.risk_percent = self.config.get('risk_percent', 2.0)
        self.max_positions = self.config.get('max_positions', 1)
        
        # ATR множители для расчета стоп-лоссов и тейк-профитов
        self.atr_multiplier_stop = self.config.get('atr_multiplier_stop', 2.0)
        self.atr_multiplier_take = self.config.get('atr_multiplier_take', 3.0)
        
        # Минимальные требования к данным
        self.min_periods = self.config.get('min_periods', 50)
        
        # === НОВОЕ: ML интеграция ===
        self.use_ml = self.config.get('use_ml', True)
        self.ml_weight = self.config.get('ml_weight', 0.3)
        self.ml_min_confidence = self.config.get('ml_min_confidence', 0.6)
        self.ml_timeout_seconds = self.config.get('ml_timeout_seconds', 5)
        
        # ML тренер (ленивая инициализация)
        self.ml_trainer = None
        self._ml_initialized = False
        
        # Статистика ML
        self.ml_stats = {
            'predictions_made': 0,
            'successful_predictions': 0,
            'failed_predictions': 0,
            'combined_signals': 0,
            'ml_only_signals': 0
        }
        
        logger.debug(f"✅ Инициализирована стратегия {self.name} (ML: {'включен' if self.use_ml else 'отключен'})")
    
    async def _initialize_ml(self):
        """
        Ленивая инициализация ML тренера
        """
        if self._ml_initialized or not self.use_ml:
            return
        
        try:
            from ..ml.training.trainer import ml_trainer
            self.ml_trainer = ml_trainer
            
            # Проверяем, что тренер инициализирован
            if not hasattr(self.ml_trainer, 'models') or not self.ml_trainer.models:
                logger.info(f"Инициализируем ML тренер для стратегии {self.name}")
                await self.ml_trainer.initialize()
            
            self._ml_initialized = True
            logger.info(f"✅ ML поддержка активирована для стратегии {self.name}")
            
        except ImportError:
            logger.warning(f"⚠️ ML модули недоступны для стратегии {self.name}")
            self.use_ml = False
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации ML для {self.name}: {e}")
            self.use_ml = False
    
    @abstractmethod
    async def analyze(self, df: pd.DataFrame, symbol: str) -> TradingSignal:
        """
        Основной метод анализа рынка
        
        Args:
            df: DataFrame с рыночными данными
            symbol: Торговая пара
            
        Returns:
            TradingSignal: Торговый сигнал
        """
        pass
    
    async def get_ml_signal(self, symbol: str, df: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """
        Получение ML сигнала с обработкой ошибок
        
        Args:
            symbol: Торговая пара
            df: DataFrame с рыночными данными
            
        Returns:
            Словарь с ML предсказанием или None
        """
        if not self.use_ml:
            return None
        
        # Инициализируем ML если нужно
        await self._initialize_ml()
        
        if not self.ml_trainer:
            return None
        
        try:
            # Таймаут для ML предсказания
            prediction = await asyncio.wait_for(
                self.ml_trainer.predict(symbol, df),
                timeout=self.ml_timeout_seconds
            )
            
            self.ml_stats['predictions_made'] += 1
            
            if prediction.get('success') and prediction.get('confidence', 0) >= self.ml_min_confidence:
                self.ml_stats['successful_predictions'] += 1
                
                # Преобразуем ML направления в торговые действия
                direction_map = {
                    'UP': 'BUY',
                    'BUY': 'BUY',
                    'DOWN': 'SELL', 
                    'SELL': 'SELL',
                    'SIDEWAYS': 'WAIT',
                    'HOLD': 'WAIT'
                }
                
                ml_direction = direction_map.get(prediction.get('direction', 'WAIT'), 'WAIT')
                
                return {
                    'direction': ml_direction,
                    'confidence': prediction.get('confidence', 0),
                    'ml_weight': self.ml_weight,
                    'probabilities': prediction.get('probabilities', {}),
                    'model_type': prediction.get('model_type', 'unknown'),
                    'prediction_raw': prediction
                }
            else:
                logger.debug(f"ML предсказание для {symbol} отклонено: низкая уверенность ({prediction.get('confidence', 0):.2f} < {self.ml_min_confidence})")
                return None
                
        except asyncio.TimeoutError:
            logger.warning(f"⏰ ML предсказание для {symbol} превысило таймаут ({self.ml_timeout_seconds}с)")
            self.ml_stats['failed_predictions'] += 1
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка ML предсказания для {symbol}: {e}")
            self.ml_stats['failed_predictions'] += 1
            return None
    
    def combine_signals(self, technical_signal: Dict[str, Any], 
                       ml_signal: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Умное комбинирование технического и ML сигналов
        
        Args:
            technical_signal: Технический сигнал
            ml_signal: ML сигнал (может быть None)
            
        Returns:
            Комбинированный сигнал
        """
        # Если нет ML сигнала, возвращаем технический
        if not ml_signal:
            return {
                **technical_signal,
                'source': 'technical_only',
                'ml_available': False
            }
        
        tech_direction = technical_signal.get('direction', 'WAIT')
        tech_confidence = technical_signal.get('confidence', 0)
        
        ml_direction = ml_signal.get('direction', 'WAIT')
        ml_confidence = ml_signal.get('confidence', 0)
        
        # Веса для комбинирования
        tech_weight = 1 - self.ml_weight
        ml_weight = self.ml_weight
        
        # Случай 1: Сигналы согласуются
        if tech_direction == ml_direction and tech_direction != 'WAIT':
            self.ml_stats['combined_signals'] += 1
            
            # Взвешенная уверенность с бонусом за согласованность
            combined_confidence = (
                tech_confidence * tech_weight + 
                ml_confidence * ml_weight
            ) * 1.15  # 15% бонус за согласованность
            
            # Ограничиваем максимальную уверенность
            combined_confidence = min(0.95, combined_confidence)
            
            return {
                **technical_signal,
                'direction': tech_direction,
                'confidence': combined_confidence,
                'source': 'combined_agreement',
                'ml_prediction': ml_signal,
                'agreement': True,
                'tech_confidence': tech_confidence,
                'ml_confidence': ml_confidence
            }
        
        # Случай 2: Противоречивые сигналы
        elif tech_direction != ml_direction:
            logger.debug(f"Противоречие сигналов: Техн={tech_direction}({tech_confidence:.2f}) vs ML={ml_direction}({ml_confidence:.2f})")
            
            # Высокая уверенность ML при низкой технической
            if ml_confidence > 0.8 and tech_confidence < 0.6:
                self.ml_stats['ml_only_signals'] += 1
                return {
                    **technical_signal,
                    'direction': ml_direction,
                    'confidence': ml_confidence * 0.9,  # Небольшое снижение за противоречие
                    'source': 'ml_override',
                    'ml_prediction': ml_signal,
                    'agreement': False,
                    'override_reason': 'high_ml_confidence'
                }
            
            # Высокая техническая уверенность
            elif tech_confidence > 0.7:
                return {
                    **technical_signal,
                    'confidence': tech_confidence * 0.9,  # Небольшое снижение за противоречие
                    'source': 'technical_override',
                    'ml_prediction': ml_signal,
                    'agreement': False,
                    'override_reason': 'high_tech_confidence'
                }
            
            # Средняя уверенность - взвешенное решение
            else:
                if ml_confidence > tech_confidence:
                    chosen_direction = ml_direction
                    chosen_confidence = ml_confidence * 0.8
                    source = 'ml_weighted'
                else:
                    chosen_direction = tech_direction
                    chosen_confidence = tech_confidence * 0.8
                    source = 'technical_weighted'
                
                return {
                    **technical_signal,
                    'direction': chosen_direction,
                    'confidence': chosen_confidence,
                    'source': source,
                    'ml_prediction': ml_signal,
                    'agreement': False,
                    'resolution': 'confidence_based'
                }
        
        # Случай 3: Один из сигналов WAIT
        else:
            # Если технический WAIT, но ML дает сигнал
            if tech_direction == 'WAIT' and ml_direction != 'WAIT' and ml_confidence > 0.7:
                return {
                    **technical_signal,
                    'direction': ml_direction,
                    'confidence': ml_confidence * 0.8,
                    'source': 'ml_when_tech_wait',
                    'ml_prediction': ml_signal
                }
            
            # В остальных случаях используем технический
            return {
                **technical_signal,
                'source': 'technical_default',
                'ml_prediction': ml_signal
            }
    
    async def analyze_with_ml(self, df: pd.DataFrame, symbol: str) -> TradingSignal:
        """
        Анализ с ML поддержкой - шаблонный метод
        
        Args:
            df: DataFrame с рыночными данными
            symbol: Торговая пара
            
        Returns:
            TradingSignal с учетом ML
        """
        # Валидация данных
        if not self.validate_dataframe(df):
            return TradingSignal(action='WAIT', confidence=0.0, price=df['close'].iloc[-1], reason="Invalid data")
        
        # Получаем технический сигнал (основной метод стратегии)
        technical_signal_obj = await self.analyze(df, symbol)
        
        # Преобразуем в словарь для обработки
        technical_signal = {
            'direction': technical_signal_obj.action,
            'confidence': technical_signal_obj.confidence,
            'price': technical_signal_obj.price,
            'stop_loss': technical_signal_obj.stop_loss,
            'take_profit': technical_signal_obj.take_profit,
            'reason': technical_signal_obj.reason,
            'risk_reward_ratio': technical_signal_obj.risk_reward_ratio,
            'indicators': technical_signal_obj.indicators
        }
        
        # Получаем ML сигнал
        ml_signal = await self.get_ml_signal(symbol, df) if self.use_ml else None
        
        # Комбинируем сигналы
        combined_signal = self.combine_signals(technical_signal, ml_signal)
        
        # Возвращаем обновленный TradingSignal
        return TradingSignal(
            action=combined_signal.get('direction', 'WAIT'),
            confidence=combined_signal.get('confidence', 0.0),
            price=combined_signal.get('price', df['close'].iloc[-1]),
            stop_loss=combined_signal.get('stop_loss'),
            take_profit=combined_signal.get('take_profit'),
            reason=self._format_combined_reason(combined_signal),
            risk_reward_ratio=combined_signal.get('risk_reward_ratio'),
            indicators=combined_signal.get('indicators'),
            ml_prediction=combined_signal.get('ml_prediction'),
            source=combined_signal.get('source', 'technical')
        )
    
    def _format_combined_reason(self, combined_signal: Dict) -> str:
        """Форматирование причины комбинированного сигнала"""
        base_reason = combined_signal.get('reason', '')
        source = combined_signal.get('source', 'technical')
        
        if source == 'combined_agreement':
            return f"{base_reason} + ML согласуется (conf: {combined_signal.get('ml_confidence', 0):.2f})"
        elif source == 'ml_override':
            return f"ML override: {combined_signal.get('override_reason', '')} (ML conf: {combined_signal.get('ml_confidence', 0):.2f})"
        elif source == 'technical_override':
            return f"{base_reason} (техн. анализ приоритет)"
        elif source == 'ml_when_tech_wait':
            return f"ML сигнал при ожидании (ML conf: {combined_signal.get('ml_confidence', 0):.2f})"
        else:
            return base_reason
    
    def validate_dataframe(self, df: pd.DataFrame) -> bool:
        """Валидация DataFrame с проверкой на реальные данные"""
        if df.empty or len(df) < self.min_periods:
            return False
        
        # Проверка на моковые данные
        if self._is_mock_data(df):
            logger.warning("Обнаружены моковые данные, пропускаем анализ")
            return False
        
        return True
    
    def _is_mock_data(self, df: pd.DataFrame) -> bool:
        """Проверка на моковые данные"""
        if len(df) < 10:
            return True
        
        # Если стандартное отклонение очень маленькое - возможно моковые данные
        if df['close'].std() < 0.01:
            return True
        
        # Если все цены одинаковые
        if df['close'].nunique() == 1:
            return True
        
        return False
    
    def calculate_stop_loss(self, price: float, action: str, atr: float,
                          multiplier: Optional[float] = None) -> float:
        """
        Расчет уровня стоп-лосса на основе ATR
        
        Args:
            price: Цена входа
            action: Направление (BUY/SELL)
            atr: Average True Range
            multiplier: Множитель ATR
            
        Returns:
            Уровень стоп-лосса
        """
        if multiplier is None:
            multiplier = self.atr_multiplier_stop
            
        if action.upper() == 'BUY':
            return max(0, price - (atr * multiplier))
        else:  # SELL
            return price + (atr * multiplier)
    
    def calculate_take_profit(self, price: float, action: str, atr: float,
                            multiplier: Optional[float] = None) -> float:
        """
        Расчет уровня take-profit на основе ATR
        
        Args:
            price: Цена входа
            action: Направление (BUY/SELL)
            atr: Average True Range
            multiplier: Множитель ATR
            
        Returns:
            Уровень take-profit
        """
        if multiplier is None:
            multiplier = self.atr_multiplier_take
            
        if action.upper() == 'BUY':
            return price + (atr * multiplier)
        else:  # SELL
            return max(0, price - (atr * multiplier))
    
    def calculate_risk_reward(self, entry_price: float, stop_loss: float, 
                            take_profit: float) -> float:
        """
        Расчет соотношения риск/прибыль
        
        Args:
            entry_price: Цена входа
            stop_loss: Уровень стоп-лосса
            take_profit: Уровень тейк-профита
            
        Returns:
            Соотношение риск/прибыль
        """
        try:
            risk = abs(entry_price - stop_loss)
            reward = abs(take_profit - entry_price)
            
            if risk == 0:
                return 0.0
                
            return reward / risk
            
        except (ZeroDivisionError, TypeError):
            return 0.0
    
    def get_strategy_info(self) -> Dict[str, Any]:
        """
        Получение информации о стратегии включая ML статистику
        
        Returns:
            Словарь с информацией о стратегии
        """
        info = {
            'name': self.name,
            'class': self.__class__.__name__,
            'timeframe': self.timeframe,
            'risk_percent': self.risk_percent,
            'max_positions': self.max_positions,
            'min_periods': self.min_periods,
            'config': self.config,
            'ml_enabled': self.use_ml,
            'ml_initialized': self._ml_initialized,
            'ml_weight': self.ml_weight,
            'ml_min_confidence': self.ml_min_confidence,
            'ml_stats': self.ml_stats.copy()
        }
        
        # Добавляем ML эффективность
        total_predictions = self.ml_stats['predictions_made']
        if total_predictions > 0:
            info['ml_success_rate'] = self.ml_stats['successful_predictions'] / total_predictions
        else:
            info['ml_success_rate'] = 0.0
            
        return info
    
    def get_ml_stats(self) -> Dict[str, Any]:
        """Получение детальной статистики ML"""
        total = self.ml_stats['predictions_made']
        return {
            **self.ml_stats,
            'success_rate': self.ml_stats['successful_predictions'] / total if total > 0 else 0,
            'failure_rate': self.ml_stats['failed_predictions'] / total if total > 0 else 0,
            'ml_enabled': self.use_ml,
            'ml_weight': self.ml_weight
        }
    
    def reset_ml_stats(self):
        """Сброс статистики ML"""
        self.ml_stats = {
            'predictions_made': 0,
            'successful_predictions': 0,
            'failed_predictions': 0,
            'combined_signals': 0,
            'ml_only_signals': 0
        }
        logger.info(f"ML статистика сброшена для стратегии {self.name}")
    
    def update_config(self, new_config: Dict[str, Any]):
        """
        Обновление конфигурации стратегии включая ML параметры
        
        Args:
            new_config: Новая конфигурация
        """
        old_ml_config = {
            'use_ml': self.use_ml,
            'ml_weight': self.ml_weight,
            'ml_min_confidence': self.ml_min_confidence
        }
        
        self.config.update(new_config)
        
        # Обновляем основные параметры
        self.timeframe = self.config.get('timeframe', self.timeframe)
        self.risk_percent = self.config.get('risk_percent', self.risk_percent)
        self.max_positions = self.config.get('max_positions', self.max_positions)
        self.atr_multiplier_stop = self.config.get('atr_multiplier_stop', self.atr_multiplier_stop)
        self.atr_multiplier_take = self.config.get('atr_multiplier_take', self.atr_multiplier_take)
        self.min_periods = self.config.get('min_periods', self.min_periods)
        
        # Обновляем ML параметры
        self.use_ml = self.config.get('use_ml', self.use_ml)
        self.ml_weight = self.config.get('ml_weight', self.ml_weight)
        self.ml_min_confidence = self.config.get('ml_min_confidence', self.ml_min_confidence)
        self.ml_timeout_seconds = self.config.get('ml_timeout_seconds', self.ml_timeout_seconds)
        
        # Переинициализируем ML если настройки изменились
        new_ml_config = {
            'use_ml': self.use_ml,
            'ml_weight': self.ml_weight,
            'ml_min_confidence': self.ml_min_confidence
        }
        
        if old_ml_config != new_ml_config:
            self._ml_initialized = False
            logger.info(f"ML конфигурация изменена для стратегии {self.name}, требуется переинициализация")
        
        logger.info(f"✅ Конфигурация стратегии {self.name} обновлена")
    
    def __str__(self) -> str:
        """Строковое представление стратегии"""
        ml_status = "ML+" if self.use_ml else "ML-"
        return f"Strategy(name={self.name}, timeframe={self.timeframe}, {ml_status})"
    
    def __repr__(self) -> str:
        """Подробное строковое представление"""
        return f"<{self.__class__.__name__}(name='{self.name}', ml_enabled={self.use_ml}, config={self.config})>"