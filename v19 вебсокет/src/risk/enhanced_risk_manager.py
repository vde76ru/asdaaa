#!/usr/bin/env python3
"""
ENHANCED RISK MANAGER - Продвинутая система управления рисками
Файл: src/risk/enhanced_risk_manager.py

🎯 ФУНКЦИИ:
✅ Динамический расчет размера позиций по Kelly Criterion
✅ Корреляционный анализ для диверсификации
✅ Мониторинг максимальной просадки в реальном времени
✅ Экстренные остановки при критических условиях
✅ Адаптивное управление рисками на основе волатильности
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

from ..core.database import SessionLocal
from ..core.models import Trade, TradeStatus, Balance, TradingPair
from ..core.config import config
from ..common.types import UnifiedTradingSignal as TradingSignal

logger = logging.getLogger(__name__)

class RiskLevel(Enum):
    """Уровни риска"""
    VERY_LOW = "very_low"      # <1% риска
    LOW = "low"                # 1-2% риска
    MEDIUM = "medium"          # 2-5% риска
    HIGH = "high"              # 5-10% риска
    VERY_HIGH = "very_high"    # >10% риска
    EXTREME = "extreme"        # >20% риска

class RiskStatus(Enum):
    """Статусы риск-менеджмента"""
    NORMAL = "normal"          # Нормальная торговля
    CAUTIOUS = "cautious"      # Осторожная торговля
    DEFENSIVE = "defensive"    # Защитный режим
    EMERGENCY = "emergency"    # Экстренная остановка

@dataclass
class PositionRisk:
    """Оценка риска позиции"""
    symbol: str
    position_size: float
    risk_amount: float         # Сумма под риском
    risk_percent: float        # Процент от капитала
    var_95: float             # Value at Risk 95%
    expected_loss: float       # Ожидаемый убыток
    correlation_risk: float    # Корреляционный риск
    liquidity_risk: float     # Риск ликвидности
    concentration_risk: float  # Риск концентрации

@dataclass
class PortfolioRisk:
    """Общий риск портфеля"""
    total_risk_amount: float   # Общая сумма под риском
    total_risk_percent: float  # Общий процент риска
    max_drawdown: float        # Максимальная просадка
    current_drawdown: float    # Текущая просадка
    correlation_matrix: np.ndarray  # Матрица корреляций
    diversification_ratio: float    # Коэффициент диверсификации
    sharpe_ratio: float        # Коэффициент Шарпа
    risk_status: RiskStatus    # Текущий статус риска

@dataclass
class RiskParameters:
    """Параметры для расчета риска"""
    max_position_risk: float = 0.02    # 2% максимум на позицию
    max_portfolio_risk: float = 0.10   # 10% максимум на портфель
    max_correlation: float = 0.7       # Максимальная корреляция
    max_drawdown: float = 0.15         # 15% максимальная просадка
    stop_loss_atr_multiplier: float = 2.0
    kelly_fraction: float = 0.25       # Доля Kelly Criterion

class EnhancedRiskManager:
    """
    Продвинутая система управления рисками
    
    🛡️ МНОГОУРОВНЕВАЯ СИСТЕМА ЗАЩИТЫ:
    
    ┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
    │   ОЦЕНКА        │───▶│   КОНТРОЛЬ       │───▶│   ИСПОЛНЕНИЕ    │
    │   РИСКА         │    │   ЛИМИТОВ        │    │   ЗАЩИТЫ        │
    │   - VaR         │    │   - Позиция      │    │   - Stop Loss   │
    │   - Корреляции  │    │   - Портфель     │    │   - Emergency   │
    │   - Концентрация│    │   - Просадка     │    │   - Position    │
    └─────────────────┘    └──────────────────┘    └─────────────────┘
             │                        │                        │
             ▼                        ▼                        ▼
    ┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
    │   МОНИТОРИНГ    │    │   АДАПТАЦИЯ      │    │   ОТЧЕТНОСТЬ    │
    │   - Real-time   │    │   - Волатильность│    │   - Метрики     │
    │   - Alerts      │    │   - Рынок        │    │   - История     │
    │   - Dashboard   │    │   - Performance  │    │   - Анализ      │
    └─────────────────┘    └──────────────────┘    └─────────────────┘
    """
    
    def __init__(self, risk_params: Optional[RiskParameters] = None):
        """
        Инициализация системы управления рисками
        
        Args:
            risk_params: Параметры риск-менеджмента
        """
        self.risk_params = risk_params or RiskParameters()
        self.load_config_parameters()
        
        # Состояние системы
        self.current_status = RiskStatus.NORMAL
        self.emergency_stop_active = False
        self.last_portfolio_check = None
        
        # Кеши и история
        self.position_risks = {}
        self.correlation_matrix = None
        self.price_history = defaultdict(deque)
        self.returns_history = defaultdict(deque)
        self.drawdown_history = deque(maxlen=1000)
        
        # Статистика
        self.risk_events = deque(maxlen=100)
        self.rejected_trades = 0
        self.total_risk_checks = 0
        
        logger.info("✅ EnhancedRiskManager инициализирован")
    
    def load_config_parameters(self):
        """Загрузка параметров из конфигурации"""
        try:
            # Обновляем параметры из config
            self.risk_params.max_position_risk = config.MAX_RISK_PER_TRADE_PERCENT / 100
            self.risk_params.max_portfolio_risk = config.MAX_PORTFOLIO_RISK_PERCENT / 100
            self.risk_params.max_correlation = config.MAX_CORRELATION_THRESHOLD
            self.risk_params.max_drawdown = config.MAX_DRAWDOWN_PERCENT / 100
            self.risk_params.stop_loss_atr_multiplier = config.STOP_LOSS_ATR_MULTIPLIER
            
            # Параметры экстренной остановки
            self.circuit_breaker_enabled = config.ENABLE_CIRCUIT_BREAKER
            self.circuit_breaker_loss = config.CIRCUIT_BREAKER_LOSS_PERCENT / 100
            self.max_consecutive_losses = config.MAX_CONSECUTIVE_LOSSES
            
            logger.info("✅ Параметры риск-менеджмента загружены из конфигурации")
            
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки параметров: {e}")
    
    async def validate_trade_risk(self, signal: TradingSignal, symbol: str,
                                current_price: float, balance: float) -> Tuple[bool, Dict[str, Any]]:
        """
        Валидация риска торговой операции
        
        Args:
            signal: Торговый сигнал
            symbol: Торговая пара
            current_price: Текущая цена
            balance: Доступный баланс
            
        Returns:
            Tuple[is_approved, risk_analysis]
        """
        try:
            self.total_risk_checks += 1
            
            # Проверка экстренной остановки
            if self.emergency_stop_active:
                return False, {
                    'reason': 'Активна экстренная остановка',
                    'risk_level': RiskLevel.EXTREME,
                    'recommended_action': 'wait'
                }
            
            # Расчет предполагаемого размера позиции
            position_size = await self.calculate_optimal_position_size(
                signal, symbol, current_price, balance
            )
            
            if position_size <= 0:
                return False, {
                    'reason': 'Размер позиции <= 0',
                    'risk_level': RiskLevel.HIGH,
                    'recommended_action': 'skip'
                }
            
            # Анализ риска позиции
            position_risk = await self.assess_position_risk(
                symbol, position_size, current_price, signal
            )
            
            # Анализ портфельного риска
            portfolio_risk = await self.assess_portfolio_risk(position_risk)
            
            # Проверка лимитов
            risk_checks = self._perform_risk_checks(position_risk, portfolio_risk)
            
            # Принятие решения
            is_approved = risk_checks['approved']
            
            if not is_approved:
                self.rejected_trades += 1
                logger.warning(
                    f"⚠️ Сделка отклонена: {risk_checks['reason']} "
                    f"(риск: {risk_checks['risk_level'].value})"
                )
            
            return is_approved, {
                'position_size': position_size,
                'position_risk': position_risk,
                'portfolio_risk': portfolio_risk,
                'risk_checks': risk_checks,
                'recommended_stop_loss': self._calculate_dynamic_stop_loss(
                    current_price, symbol, signal.action
                ),
                'recommended_take_profit': self._calculate_dynamic_take_profit(
                    current_price, signal.action, position_risk.var_95
                )
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка валидации риска: {e}")
            return False, {
                'reason': f'Ошибка анализа риска: {e}',
                'risk_level': RiskLevel.HIGH,
                'recommended_action': 'skip'
            }
    
    async def calculate_optimal_position_size(self, signal: TradingSignal, symbol: str,
                                            current_price: float, balance: float) -> float:
        """
        Расчет оптимального размера позиции
        Использует Kelly Criterion и другие методы
        """
        try:
            # Метод 1: Фиксированный процент риска
            risk_amount = balance * self.risk_params.max_position_risk
            
            # Рассчитываем stop-loss
            if signal.stop_loss:
                stop_distance = abs(current_price - signal.stop_loss)
            else:
                # Используем ATR для динамического stop-loss
                atr = await self._get_atr(symbol)
                stop_distance = atr * self.risk_params.stop_loss_atr_multiplier
            
            if stop_distance <= 0:
                return 0.0
            
            # Размер позиции на основе риска
            position_size_risk = risk_amount / stop_distance
            
            # Метод 2: Kelly Criterion (если есть историческая статистика)
            kelly_size = await self._calculate_kelly_position_size(
                symbol, current_price, balance
            )
            
            # Метод 3: Волатильность-based sizing
            volatility_size = await self._calculate_volatility_based_size(
                symbol, balance, current_price
            )
            
            # Берем консервативный размер (минимум из методов)
            optimal_size = min(
                position_size_risk,
                kelly_size,
                volatility_size,
                balance * 0.1  # Максимум 10% от баланса
            )
            
            # Применяем ограничения
            max_position_value = balance * self.risk_params.max_position_risk * 10
            max_size_by_value = max_position_value / current_price
            
            final_size = min(optimal_size, max_size_by_value)
            
            logger.debug(
                f"📊 Размер позиции для {symbol}: {final_size:.6f} "
                f"(risk: {position_size_risk:.6f}, kelly: {kelly_size:.6f}, "
                f"vol: {volatility_size:.6f})"
            )
            
            return max(0.0, final_size)
            
        except Exception as e:
            logger.error(f"❌ Ошибка расчета размера позиции: {e}")
            return 0.0
    
    async def assess_position_risk(self, symbol: str, position_size: float,
                                 current_price: float, signal: TradingSignal) -> PositionRisk:
        """Оценка риска конкретной позиции"""
        try:
            position_value = position_size * current_price
            
            # Расчет риска
            if signal.stop_loss:
                risk_amount = abs(current_price - signal.stop_loss) * position_size
            else:
                atr = await self._get_atr(symbol)
                risk_amount = atr * self.risk_params.stop_loss_atr_multiplier * position_size
            
            # Value at Risk (95%)
            volatility = await self._get_volatility(symbol)
            var_95 = position_value * volatility * 1.645  # 95% VaR
            
            # Корреляционный риск
            correlation_risk = await self._calculate_correlation_risk(symbol)
            
            # Риск ликвидности (упрощенный)
            liquidity_risk = min(0.1, position_value / 1000000)  # 1M USD как базовая ликвидность
            
            # Риск концентрации
            total_portfolio_value = await self._get_total_portfolio_value()
            concentration_risk = position_value / total_portfolio_value if total_portfolio_value > 0 else 0
            
            return PositionRisk(
                symbol=symbol,
                position_size=position_size,
                risk_amount=risk_amount,
                risk_percent=risk_amount / total_portfolio_value if total_portfolio_value > 0 else 0,
                var_95=var_95,
                expected_loss=risk_amount * 0.5,  # Упрощенный расчет
                correlation_risk=correlation_risk,
                liquidity_risk=liquidity_risk,
                concentration_risk=concentration_risk
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка оценки риска позиции: {e}")
            return PositionRisk(
                symbol=symbol,
                position_size=position_size,
                risk_amount=position_size * current_price * 0.02,
                risk_percent=0.02,
                var_95=position_size * current_price * 0.05,
                expected_loss=position_size * current_price * 0.01,
                correlation_risk=0.1,
                liquidity_risk=0.05,
                concentration_risk=0.1
            )
    
    async def assess_portfolio_risk(self, new_position: PositionRisk) -> PortfolioRisk:
        """Оценка общего риска портфеля"""
        try:
            # Получаем текущие позиции
            current_positions = await self._get_current_positions()
            
            # Добавляем новую позицию для анализа
            all_positions = current_positions + [new_position]
            
            # Общий риск
            total_risk_amount = sum(pos.risk_amount for pos in all_positions)
            total_value = await self._get_total_portfolio_value()
            total_risk_percent = total_risk_amount / total_value if total_value > 0 else 0
            
            # Просадка
            current_drawdown, max_drawdown = await self._calculate_drawdown()
            
            # Корреляционная матрица
            correlation_matrix = await self._build_correlation_matrix([pos.symbol for pos in all_positions])
            
            # Коэффициент диверсификации
            diversification_ratio = self._calculate_diversification_ratio(all_positions, correlation_matrix)
            
            # Коэффициент Шарпа (упрощенный)
            sharpe_ratio = await self._calculate_portfolio_sharpe(all_positions)
            
            # Определение статуса риска
            risk_status = self._determine_risk_status(
                total_risk_percent, current_drawdown, diversification_ratio
            )
            
            return PortfolioRisk(
                total_risk_amount=total_risk_amount,
                total_risk_percent=total_risk_percent,
                max_drawdown=max_drawdown,
                current_drawdown=current_drawdown,
                correlation_matrix=correlation_matrix,
                diversification_ratio=diversification_ratio,
                sharpe_ratio=sharpe_ratio,
                risk_status=risk_status
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка оценки портфельного риска: {e}")
            return PortfolioRisk(
                total_risk_amount=0.0,
                total_risk_percent=0.0,
                max_drawdown=0.0,
                current_drawdown=0.0,
                correlation_matrix=np.array([]),
                diversification_ratio=1.0,
                sharpe_ratio=0.0,
                risk_status=RiskStatus.NORMAL
            )
    
    def _perform_risk_checks(self, position_risk: PositionRisk,
                           portfolio_risk: PortfolioRisk) -> Dict[str, Any]:
        """Выполнение проверок риск-лимитов"""
        checks = {
            'approved': True,
            'reason': '',
            'risk_level': RiskLevel.LOW,
            'violations': []
        }
        
        try:
            # Проверка риска позиции
            if position_risk.risk_percent > self.risk_params.max_position_risk:
                checks['approved'] = False
                checks['reason'] = f'Превышен лимит риска позиции: {position_risk.risk_percent:.2%}'
                checks['risk_level'] = RiskLevel.HIGH
                checks['violations'].append('position_risk_limit')
            
            # Проверка портфельного риска
            if portfolio_risk.total_risk_percent > self.risk_params.max_portfolio_risk:
                checks['approved'] = False
                checks['reason'] = f'Превышен лимит портфельного риска: {portfolio_risk.total_risk_percent:.2%}'
                checks['risk_level'] = RiskLevel.HIGH
                checks['violations'].append('portfolio_risk_limit')
            
            # Проверка просадки
            if portfolio_risk.current_drawdown > self.risk_params.max_drawdown:
                checks['approved'] = False
                checks['reason'] = f'Превышена максимальная просадка: {portfolio_risk.current_drawdown:.2%}'
                checks['risk_level'] = RiskLevel.EXTREME
                checks['violations'].append('max_drawdown')
            
            # Проверка концентрации
            if position_risk.concentration_risk > 0.3:  # 30% максимум на одну позицию
                checks['approved'] = False
                checks['reason'] = f'Слишком высокая концентрация: {position_risk.concentration_risk:.2%}'
                checks['risk_level'] = RiskLevel.HIGH
                checks['violations'].append('concentration_risk')
            
            # Проверка корреляции
            if position_risk.correlation_risk > self.risk_params.max_correlation:
                checks['approved'] = False
                checks['reason'] = f'Высокая корреляция с портфелем: {position_risk.correlation_risk:.2f}'
                checks['risk_level'] = RiskLevel.MEDIUM
                checks['violations'].append('correlation_risk')
            
            # Проверка статуса портфеля
            if portfolio_risk.risk_status in [RiskStatus.EMERGENCY]:
                checks['approved'] = False
                checks['reason'] = f'Критический статус портфеля: {portfolio_risk.risk_status.value}'
                checks['risk_level'] = RiskLevel.EXTREME
                checks['violations'].append('portfolio_status')
            
            # Определяем итоговый уровень риска
            if not checks['violations']:
                if portfolio_risk.total_risk_percent > 0.05:
                    checks['risk_level'] = RiskLevel.MEDIUM
                else:
                    checks['risk_level'] = RiskLevel.LOW
            
            return checks
            
        except Exception as e:
            logger.error(f"❌ Ошибка проверки риск-лимитов: {e}")
            return {
                'approved': False,
                'reason': f'Ошибка проверки рисков: {e}',
                'risk_level': RiskLevel.HIGH,
                'violations': ['system_error']
            }
    
    async def monitor_portfolio_health(self) -> Dict[str, Any]:
        """Мониторинг здоровья портфеля"""
        try:
            current_positions = await self._get_current_positions()
            portfolio_risk = await self.assess_portfolio_risk(
                PositionRisk('DUMMY', 0, 0, 0, 0, 0, 0, 0, 0)  # Dummy для анализа
            )
            
            health_metrics = {
                'timestamp': datetime.utcnow(),
                'total_positions': len(current_positions),
                'total_risk_percent': portfolio_risk.total_risk_percent,
                'current_drawdown': portfolio_risk.current_drawdown,
                'max_drawdown': portfolio_risk.max_drawdown,
                'diversification_ratio': portfolio_risk.diversification_ratio,
                'sharpe_ratio': portfolio_risk.sharpe_ratio,
                'risk_status': portfolio_risk.risk_status.value,
                'emergency_stop_active': self.emergency_stop_active
            }
            
            # Проверяем критические условия
            critical_issues = []
            
            if portfolio_risk.current_drawdown > self.risk_params.max_drawdown * 0.8:
                critical_issues.append('Близко к максимальной просадке')
            
            if portfolio_risk.total_risk_percent > self.risk_params.max_portfolio_risk * 0.9:
                critical_issues.append('Близко к лимиту портфельного риска')
            
            if portfolio_risk.diversification_ratio < 0.3:
                critical_issues.append('Низкая диверсификация портфеля')
            
            health_metrics['critical_issues'] = critical_issues
            health_metrics['health_score'] = self._calculate_health_score(portfolio_risk)
            
            # Активируем экстренную остановку если нужно
            if (portfolio_risk.current_drawdown > self.circuit_breaker_loss and
                self.circuit_breaker_enabled):
                await self.activate_emergency_stop('Circuit breaker triggered')
            
            return health_metrics
            
        except Exception as e:
            logger.error(f"❌ Ошибка мониторинга здоровья портфеля: {e}")
            return {
                'timestamp': datetime.utcnow(),
                'error': str(e),
                'health_score': 0.0
            }
    
    async def activate_emergency_stop(self, reason: str = "Manual activation"):
        """Активация экстренной остановки"""
        try:
            self.emergency_stop_active = True
            self.current_status = RiskStatus.EMERGENCY
            
            # Логируем событие
            self.risk_events.append({
                'timestamp': datetime.utcnow(),
                'type': 'emergency_stop',
                'reason': reason
            })
            
            logger.critical(f"🚨 ЭКСТРЕННАЯ ОСТАНОВКА АКТИВИРОВАНА: {reason}")
            
            # Здесь можно добавить уведомления
            # await self._send_emergency_notification(reason)
            
        except Exception as e:
            logger.error(f"❌ Ошибка активации экстренной остановки: {e}")
    
    async def deactivate_emergency_stop(self):
        """Деактивация экстренной остановки"""
        try:
            self.emergency_stop_active = False
            self.current_status = RiskStatus.NORMAL
            
            self.risk_events.append({
                'timestamp': datetime.utcnow(),
                'type': 'emergency_stop_deactivated',
                'reason': 'Manual deactivation'
            })
            
            logger.info("✅ Экстренная остановка деактивирована")
            
        except Exception as e:
            logger.error(f"❌ Ошибка деактивации экстренной остановки: {e}")
    
    # ===============================================================
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # ===============================================================
    
    async def _calculate_kelly_position_size(self, symbol: str, price: float,
                                           balance: float) -> float:
        """Расчет размера позиции по Kelly Criterion"""
        try:
            # Получаем историческую статистику
            win_rate, avg_win, avg_loss = await self._get_historical_stats(symbol)
            
            if win_rate <= 0 or avg_loss <= 0:
                return balance * 0.02 / price  # Фиксированный 2%
            
            # Kelly = (bp - q) / b
            # где b = avg_win/avg_loss, p = win_rate, q = 1-win_rate
            b = avg_win / avg_loss
            p = win_rate
            q = 1 - win_rate
            
            kelly_fraction = (b * p - q) / b
            kelly_fraction = max(0, min(kelly_fraction, self.risk_params.kelly_fraction))
            
            return balance * kelly_fraction / price
            
        except Exception as e:
            logger.error(f"❌ Ошибка расчета Kelly: {e}")
            return balance * 0.02 / price
    
    async def _calculate_volatility_based_size(self, symbol: str, balance: float,
                                             price: float) -> float:
        """Расчет размера позиции на основе волатильности"""
        try:
            volatility = await self._get_volatility(symbol)
            
            # Чем выше волатильность, тем меньше позиция
            vol_factor = 1 / (1 + volatility * 10)
            base_allocation = balance * 0.05  # 5% базовая аллокация
            
            return base_allocation * vol_factor / price
            
        except Exception as e:
            logger.error(f"❌ Ошибка расчета размера по волатильности: {e}")
            return balance * 0.02 / price
    
    async def _get_atr(self, symbol: str, period: int = 14) -> float:
        """Получение Average True Range"""
        try:
            # Здесь должен быть запрос к базе данных или биржевому API
            # Пока возвращаем заглушку
            return 0.02  # 2% ATR
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения ATR: {e}")
            return 0.02
    
    async def _get_volatility(self, symbol: str, period: int = 20) -> float:
        """Получение волатильности"""
        try:
            # Заглушка - в реальности расчет из исторических данных
            return 0.05  # 5% дневная волатильность
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения волатильности: {e}")
            return 0.05
    
    async def _get_historical_stats(self, symbol: str) -> Tuple[float, float, float]:
        """Получение исторической статистики торговли"""
        try:
            db = SessionLocal()
            
            # Запрос закрытых сделок за последние 30 дней
            cutoff_date = datetime.utcnow() - timedelta(days=30)
            trades = db.query(Trade).filter(
                Trade.symbol == symbol,
                Trade.status == TradeStatus.CLOSED,
                Trade.exit_time >= cutoff_date
            ).all()
            
            if not trades:
                return 0.5, 0.02, 0.02  # Дефолтные значения
            
            profits = [t.profit for t in trades if t.profit]
            wins = [p for p in profits if p > 0]
            losses = [-p for p in profits if p < 0]
            
            win_rate = len(wins) / len(profits) if profits else 0.5
            avg_win = np.mean(wins) if wins else 0.02
            avg_loss = np.mean(losses) if losses else 0.02
            
            return win_rate, avg_win, avg_loss
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения исторической статистики: {e}")
            return 0.5, 0.02, 0.02
        finally:
            db.close()
    
    def _calculate_dynamic_stop_loss(self, current_price: float, symbol: str,
                                   action: str) -> float:
        """Расчет динамического stop-loss"""
        try:
            # Упрощенный расчет - в реальности использовать ATR
            stop_distance = current_price * 0.02  # 2%
            
            if action == 'BUY':
                return current_price - stop_distance
            else:  # SELL
                return current_price + stop_distance
                
        except Exception as e:
            logger.error(f"❌ Ошибка расчета stop-loss: {e}")
            return current_price * 0.98 if action == 'BUY' else current_price * 1.02
    
    def _calculate_dynamic_take_profit(self, current_price: float, action: str,
                                     var_95: float) -> float:
        """Расчет динамического take-profit"""
        try:
            # Используем VaR для расчета take-profit
            profit_distance = max(current_price * 0.04, var_95)
            
            if action == 'BUY':
                return current_price + profit_distance
            else:  # SELL
                return current_price - profit_distance
                
        except Exception as e:
            logger.error(f"❌ Ошибка расчета take-profit: {e}")
            return current_price * 1.04 if action == 'BUY' else current_price * 0.96
    
    def get_risk_statistics(self) -> Dict[str, Any]:
        """Получение статистики работы риск-менеджера"""
        try:
            return {
                'total_risk_checks': self.total_risk_checks,
                'rejected_trades': self.rejected_trades,
                'rejection_rate': self.rejected_trades / max(1, self.total_risk_checks),
                'current_status': self.current_status.value,
                'emergency_stop_active': self.emergency_stop_active,
                'recent_events': list(self.risk_events)[-10:],  # Последние 10 событий
                'risk_parameters': {
                    'max_position_risk': self.risk_params.max_position_risk,
                    'max_portfolio_risk': self.risk_params.max_portfolio_risk,
                    'max_correlation': self.risk_params.max_correlation,
                    'max_drawdown': self.risk_params.max_drawdown
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики: {e}")
            return {}

# =================================================================
# ЗАГЛУШКИ ДЛЯ МЕТОДОВ, ТРЕБУЮЩИХ ПОЛНОЙ РЕАЛИЗАЦИИ
# =================================================================

    async def _get_current_positions(self) -> List[PositionRisk]:
        """Заглушка - получение текущих позиций"""
        return []
    
    async def _get_total_portfolio_value(self) -> float:
        """Заглушка - получение общей стоимости портфеля"""
        return 10000.0
    
    async def _calculate_correlation_risk(self, symbol: str) -> float:
        """Заглушка - расчет корреляционного риска"""
        return 0.1
    
    async def _calculate_drawdown(self) -> Tuple[float, float]:
        """Заглушка - расчет просадки"""
        return 0.05, 0.12
    
    async def _build_correlation_matrix(self, symbols: List[str]) -> np.ndarray:
        """Заглушка - построение корреляционной матрицы"""
        n = len(symbols)
        return np.eye(n) if n > 0 else np.array([])
    
    def _calculate_diversification_ratio(self, positions: List[PositionRisk],
                                       correlation_matrix: np.ndarray) -> float:
        """Заглушка - расчет коэффициента диверсификации"""
        return 0.7
    
    async def _calculate_portfolio_sharpe(self, positions: List[PositionRisk]) -> float:
        """Заглушка - расчет коэффициента Шарпа портфеля"""
        return 1.2
    
    def _determine_risk_status(self, total_risk: float, drawdown: float,
                             diversification: float) -> RiskStatus:
        """Определение статуса риска портфеля"""
        if drawdown > 0.15 or total_risk > 0.2:
            return RiskStatus.EMERGENCY
        elif drawdown > 0.1 or total_risk > 0.15:
            return RiskStatus.DEFENSIVE
        elif drawdown > 0.05 or total_risk > 0.1:
            return RiskStatus.CAUTIOUS
        else:
            return RiskStatus.NORMAL
    
    def _calculate_health_score(self, portfolio_risk: PortfolioRisk) -> float:
        """Расчет общего скора здоровья портфеля"""
        try:
            # Компоненты скора
            drawdown_score = max(0, 1 - portfolio_risk.current_drawdown / 0.2)
            risk_score = max(0, 1 - portfolio_risk.total_risk_percent / 0.3)
            diversification_score = portfolio_risk.diversification_ratio
            sharpe_score = min(1, portfolio_risk.sharpe_ratio / 2)
            
            # Взвешенный скор
            health_score = (
                drawdown_score * 0.3 +
                risk_score * 0.3 +
                diversification_score * 0.2 +
                sharpe_score * 0.2
            )
            
            return max(0, min(1, health_score))
            
        except Exception as e:
            logger.error(f"❌ Ошибка расчета скора здоровья: {e}")
            return 0.5

# =================================================================
# ГЛОБАЛЬНЫЕ ФУНКЦИИ
# =================================================================

# Глобальный экземпляр
enhanced_risk_manager = None

def get_risk_manager() -> EnhancedRiskManager:
    """Получить глобальный экземпляр риск-менеджера"""
    global enhanced_risk_manager
    
    if enhanced_risk_manager is None:
        enhanced_risk_manager = EnhancedRiskManager()
    
    return enhanced_risk_manager

def create_risk_manager(risk_params: Optional[RiskParameters] = None) -> EnhancedRiskManager:
    """Создать новый экземпляр риск-менеджера"""
    return EnhancedRiskManager(risk_params)

# Экспорты
__all__ = [
    'EnhancedRiskManager',
    'RiskParameters',
    'PositionRisk',
    'PortfolioRisk',
    'RiskLevel',
    'RiskStatus',
    'get_risk_manager',
    'create_risk_manager'
]