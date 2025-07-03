"""
Динамический калькулятор размера позиций
Файл: src/risk/position_sizer.py
"""
import numpy as np
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta

from ..logging.smart_logger import SmartLogger
from ..core.database import SessionLocal
from ..core.models import Trade, StrategyPerformance

logger = SmartLogger(__name__)


@dataclass
class SizingParameters:
    """Параметры для расчета размера позиции"""
    min_position_size: float = 0.001  # Минимальный размер
    max_position_percent: float = 0.1  # Максимум 10% от баланса
    kelly_fraction: float = 0.25      # Доля Kelly для консервативности
    confidence_multiplier: bool = True # Учитывать уверенность ML
    market_regime_adjust: bool = True  # Адаптация к рыночному режиму
    performance_scaling: bool = True   # Масштабирование по производительности


class DynamicPositionSizer:
    """
    Динамический расчет размера позиций с использованием:
    - Kelly Criterion
    - ML confidence
    - Market regime
    - Historical performance
    """
    
    def __init__(self, initial_balance: float):
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.params = SizingParameters()
        
        # Кеш производительности стратегий
        self.strategy_performance_cache: Dict[str, Dict] = {}
        self.last_cache_update = datetime.utcnow()
        
        # Рыночные режимы
        self.market_regimes = {
            'trending_up': 1.2,
            'trending_down': 0.8,
            'sideways': 0.9,
            'volatile': 0.7,
            'calm': 1.1
        }
    
    def calculate(self, signal: Dict[str, Any], 
                 market_conditions: Dict[str, Any],
                 ml_confidence: float) -> Dict[str, Any]:
        """
        Рассчитывает оптимальный размер позиции
        
        Args:
            signal: Торговый сигнал
            market_conditions: Текущие рыночные условия
            ml_confidence: Уверенность ML модели (0-1)
            
        Returns:
            Dict с размером позиции и деталями расчета
        """
        try:
            symbol = signal['symbol']
            strategy = signal['strategy']
            entry_price = signal['entry_price']
            stop_loss = signal.get('stop_loss', entry_price * 0.98)
            
            # 1. Базовый размер по Kelly Criterion
            kelly_size = self._calculate_kelly_size(strategy, symbol)
            
            # 2. Корректировка на уверенность ML
            if self.params.confidence_multiplier:
                kelly_size *= self._get_confidence_multiplier(ml_confidence)
            
            # 3. Корректировка на рыночный режим
            if self.params.market_regime_adjust:
                regime_multiplier = self._get_regime_multiplier(market_conditions)
                kelly_size *= regime_multiplier
            
            # 4. Корректировка на производительность стратегии
            if self.params.performance_scaling:
                performance_multiplier = self._get_performance_multiplier(strategy, symbol)
                kelly_size *= performance_multiplier
            
            # 5. Применение лимитов
            max_position_value = self.current_balance * self.params.max_position_percent
            max_units = max_position_value / entry_price
            
            # Финальный размер
            final_size = max(
                self.params.min_position_size,
                min(kelly_size, max_units)
            )
            
            # Детали расчета для логирования
            calculation_details = {
                'base_kelly_size': kelly_size,
                'ml_confidence': ml_confidence,
                'regime_multiplier': regime_multiplier if self.params.market_regime_adjust else 1.0,
                'performance_multiplier': performance_multiplier if self.params.performance_scaling else 1.0,
                'max_allowed': max_units,
                'final_size': final_size,
                'position_value': final_size * entry_price,
                'position_percent': (final_size * entry_price) / self.current_balance * 100
            }
            
            logger.info(
                f"Рассчитан размер позиции: {final_size:.4f} {symbol}",
                category='risk',
                symbol=symbol,
                strategy=strategy,
                **calculation_details
            )
            
            return {
                'size': final_size,
                'details': calculation_details
            }
            
        except Exception as e:
            logger.error(
                f"Ошибка расчета размера позиции: {e}",
                category='risk',
                symbol=signal.get('symbol'),
                error=str(e)
            )
            
            # Возвращаем минимальный размер при ошибке
            return {
                'size': self.params.min_position_size,
                'details': {'error': str(e)}
            }
    
    def _calculate_kelly_size(self, strategy: str, symbol: str) -> float:
        """
        Расчет размера по Kelly Criterion
        
        Kelly % = (p * b - q) / b
        где:
        p = вероятность выигрыша
        q = вероятность проигрыша (1 - p)
        b = отношение выигрыша к проигрышу
        """
        # Получаем статистику стратегии
        stats = self._get_strategy_stats(strategy, symbol)
        
        if not stats or stats['total_trades'] < 10:
            # Недостаточно данных - используем минимальный размер
            return self.params.min_position_size
        
        win_rate = stats['win_rate']
        avg_win = stats['avg_win']
        avg_loss = abs(stats['avg_loss'])
        
        # Защита от деления на ноль
        if avg_loss == 0:
            avg_loss = 0.01
        
        # Kelly formula
        p = win_rate
        q = 1 - win_rate
        b = avg_win / avg_loss
        
        kelly_percent = (p * b - q) / b
        
        # Применяем Kelly fraction для консервативности
        kelly_percent *= self.params.kelly_fraction
        
        # Ограничения
        kelly_percent = max(0.01, min(kelly_percent, 0.25))  # 1-25%
        
        # Конвертируем в размер позиции
        position_value = self.current_balance * kelly_percent
        
        # Предполагаемая цена для расчета (будет скорректирована позже)
        return position_value / 1000  # Временное значение
    
    def _get_strategy_stats(self, strategy: str, symbol: str) -> Optional[Dict]:
        """Получает статистику производительности стратегии"""
        # Проверяем кеш
        cache_key = f"{strategy}:{symbol}"
        
        # Обновляем кеш каждый час
        if (datetime.utcnow() - self.last_cache_update).total_seconds() > 3600:
            self.strategy_performance_cache.clear()
            self.last_cache_update = datetime.utcnow()
        
        if cache_key in self.strategy_performance_cache:
            return self.strategy_performance_cache[cache_key]
        
        # Загружаем из БД
        db = SessionLocal()
        try:
            # Получаем последние данные о производительности
            perf = db.query(StrategyPerformance).filter(
                StrategyPerformance.strategy_name == strategy,
                StrategyPerformance.symbol == symbol
            ).order_by(
                StrategyPerformance.period_end.desc()
            ).first()
            
            if perf:
                stats = {
                    'win_rate': perf.win_rate,
                    'avg_win': perf.avg_profit if perf.avg_profit > 0 else 0.01,
                    'avg_loss': perf.avg_loss if hasattr(perf, 'avg_loss') else perf.avg_profit * -0.5,
                    'total_trades': perf.total_trades,
                    'profit_factor': perf.profit_factor if hasattr(perf, 'profit_factor') else 1.0,
                    'sharpe_ratio': perf.sharpe_ratio if hasattr(perf, 'sharpe_ratio') else 0
                }
            else:
                # Значения по умолчанию для новой стратегии
                stats = {
                    'win_rate': 0.5,
                    'avg_win': 0.02,
                    'avg_loss': -0.01,
                    'total_trades': 0,
                    'profit_factor': 1.0,
                    'sharpe_ratio': 0
                }
            
            # Кешируем
            self.strategy_performance_cache[cache_key] = stats
            return stats
            
        except Exception as e:
            logger.error(
                f"Ошибка загрузки статистики стратегии: {e}",
                category='risk',
                strategy=strategy,
                symbol=symbol
            )
            return None
        finally:
            db.close()
    
    def _get_confidence_multiplier(self, ml_confidence: float) -> float:
        """
        Множитель на основе уверенности ML
        
        Высокая уверенность (>0.8) -> увеличиваем размер
        Низкая уверенность (<0.6) -> уменьшаем размер
        """
        if ml_confidence >= 0.8:
            return 1.2
        elif ml_confidence >= 0.7:
            return 1.0
        elif ml_confidence >= 0.6:
            return 0.8
        else:
            return 0.5
    
    def _get_regime_multiplier(self, market_conditions: Dict[str, Any]) -> float:
        """Множитель на основе рыночного режима"""
        regime = market_conditions.get('regime', 'sideways')
        volatility = market_conditions.get('volatility', 'normal')
        
        # Базовый множитель
        multiplier = self.market_regimes.get(regime, 1.0)
        
        # Дополнительная корректировка на волатильность
        if volatility == 'high':
            multiplier *= 0.8
        elif volatility == 'extreme':
            multiplier *= 0.5
        
        return multiplier
    
    def _get_performance_multiplier(self, strategy: str, symbol: str) -> float:
        """
        Множитель на основе недавней производительности
        
        Если стратегия показывает хорошие результаты - увеличиваем размер
        Если плохие - уменьшаем
        """
        stats = self._get_strategy_stats(strategy, symbol)
        
        if not stats or stats['total_trades'] < 20:
            return 1.0
        
        # Анализируем profit factor и Sharpe ratio
        profit_factor = stats.get('profit_factor', 1.0)
        sharpe_ratio = stats.get('sharpe_ratio', 0)
        
        if profit_factor > 2.0 and sharpe_ratio > 1.5:
            return 1.3  # Отличная производительность
        elif profit_factor > 1.5 and sharpe_ratio > 1.0:
            return 1.15  # Хорошая производительность
        elif profit_factor > 1.2 and sharpe_ratio > 0.5:
            return 1.0  # Нормальная производительность
        elif profit_factor < 0.8 or sharpe_ratio < 0:
            return 0.7  # Плохая производительность
        else:
            return 0.85  # Ниже среднего
    
    def update_balance(self, new_balance: float):
        """Обновляет текущий баланс"""
        self.current_balance = new_balance
        
        # Логируем значительные изменения
        change_percent = ((new_balance - self.initial_balance) / self.initial_balance) * 100
        
        if abs(change_percent) > 10:
            logger.info(
                f"Значительное изменение баланса: {change_percent:+.2f}%",
                category='risk',
                old_balance=self.initial_balance,
                new_balance=new_balance,
                change_percent=change_percent
            )
    
    def get_position_limits(self, symbol: str) -> Dict[str, float]:
        """Возвращает лимиты для позиции"""
        max_position_value = self.current_balance * self.params.max_position_percent
        
        return {
            'max_position_value': max_position_value,
            'max_loss_per_trade': self.current_balance * 0.02,  # 2% максимальный убыток
            'min_position_size': self.params.min_position_size,
            'current_balance': self.current_balance
        }
    
    def adjust_parameters(self, market_analysis: Dict[str, Any]):
        """
        Динамическая корректировка параметров на основе анализа рынка
        """
        # В периоды высокой неопределенности уменьшаем риски
        if market_analysis.get('uncertainty', 0) > 0.7:
            self.params.max_position_percent = 0.05
            self.params.kelly_fraction = 0.15
            logger.warning(
                "Параметры размера позиций уменьшены из-за высокой неопределенности",
                category='risk',
                max_position_percent=self.params.max_position_percent,
                kelly_fraction=self.params.kelly_fraction
            )
        
        # В стабильные периоды можем увеличить
        elif market_analysis.get('stability', 0) > 0.8:
            self.params.max_position_percent = 0.15
            self.params.kelly_fraction = 0.3
            logger.info(
                "Параметры размера позиций увеличены в стабильном рынке",
                category='risk',
                max_position_percent=self.params.max_position_percent,
                kelly_fraction=self.params.kelly_fraction
            )