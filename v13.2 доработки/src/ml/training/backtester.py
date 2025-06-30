"""
Backtester для тестирования ML стратегий на исторических данных
Файл: src/ml/training/backtester.py
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Any, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import json
from collections import defaultdict

import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats

from ...logging.smart_logger import SmartLogger
from ...core.database import SessionLocal
from ..models.classifier import DirectionClassifier
from ..models.regressor import PriceLevelRegressor
from ..strategy_selector import MLStrategySelector


@dataclass
class BacktestConfig:
    """Конфигурация для бэктестинга"""
    initial_balance: float = 10000.0
    commission: float = 0.001  # 0.1%
    slippage: float = 0.0005  # 0.05%
    max_position_size: float = 0.95  # 95% от баланса
    use_leverage: bool = False
    leverage: float = 1.0
    risk_per_trade: float = 0.02  # 2% риска на сделку
    max_open_positions: int = 3
    enable_shorting: bool = True
    use_stop_loss: bool = True
    use_take_profit: bool = True
    trailing_stop: bool = False
    trailing_stop_distance: float = 0.02  # 2%


@dataclass
class Trade:
    """Класс для хранения информации о сделке"""
    entry_time: datetime
    entry_price: float
    position_size: float
    side: str  # 'long' or 'short'
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    profit: float = 0.0
    profit_percent: float = 0.0
    commission_paid: float = 0.0
    exit_reason: Optional[str] = None
    ml_confidence: float = 0.0
    strategy: str = ""
    max_profit: float = 0.0
    max_loss: float = 0.0
    duration: Optional[timedelta] = None


@dataclass
class BacktestResult:
    """Результаты бэктестинга"""
    # Основные метрики
    total_return: float = 0.0
    total_return_percent: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    
    # Финансовые метрики
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    profit_factor: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    
    # Риск метрики
    max_drawdown: float = 0.0
    max_drawdown_percent: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    
    # Временные метрики
    avg_trade_duration: timedelta = timedelta()
    longest_trade: timedelta = timedelta()
    shortest_trade: timedelta = timedelta()
    
    # Детали
    trades: List[Trade] = field(default_factory=list)
    equity_curve: pd.Series = field(default_factory=pd.Series)
    drawdown_curve: pd.Series = field(default_factory=pd.Series)
    monthly_returns: pd.Series = field(default_factory=pd.Series)
    
    # ML метрики
    avg_ml_confidence: float = 0.0
    confidence_vs_profit_correlation: float = 0.0
    strategy_performance: Dict[str, Dict] = field(default_factory=dict)


class Backtester:
    """
    Класс для бэктестинга ML стратегий
    """
    
    def __init__(self, config: BacktestConfig = BacktestConfig()):
        self.config = config
        self.logger = SmartLogger(__name__)
        
    def run_backtest(self, 
                    market_data: pd.DataFrame,
                    features: pd.DataFrame,
                    predictions: pd.DataFrame,
                    start_date: Optional[datetime] = None,
                    end_date: Optional[datetime] = None) -> BacktestResult:
        """
        Запускает бэктест на исторических данных
        
        Args:
            market_data: OHLCV данные
            features: Признаки для ML моделей
            predictions: Предсказания ML моделей
            start_date: Начальная дата
            end_date: Конечная дата
            
        Returns:
            Результаты бэктестинга
        """
        self.logger.info(
            "Запуск бэктестинга",
            category='backtest',
            start_date=start_date,
            end_date=end_date,
            total_bars=len(market_data)
        )
        
        # Фильтруем по датам
        if start_date:
            mask = market_data.index >= start_date
            market_data = market_data[mask]
            features = features[mask]
            predictions = predictions[mask]
        
        if end_date:
            mask = market_data.index <= end_date
            market_data = market_data[mask]
            features = features[mask]
            predictions = predictions[mask]
        
        # Инициализация
        balance = self.config.initial_balance
        equity = [balance]
        trades = []
        open_positions = []
        
        # Основной цикл бэктеста
        for i in range(1, len(market_data)):
            current_time = market_data.index[i]
            current_price = market_data.iloc[i]['close']
            current_high = market_data.iloc[i]['high']
            current_low = market_data.iloc[i]['low']
            
            # Проверяем открытые позиции
            positions_to_close = []
            
            for pos_idx, position in enumerate(open_positions):
                # Проверка Stop Loss
                if self.config.use_stop_loss and position.stop_loss:
                    if (position.side == 'long' and current_low <= position.stop_loss) or \
                       (position.side == 'short' and current_high >= position.stop_loss):
                        exit_price = position.stop_loss
                        self._close_position(position, exit_price, current_time, 'stop_loss')
                        positions_to_close.append(pos_idx)
                        continue
                
                # Проверка Take Profit
                if self.config.use_take_profit and position.take_profit:
                    if (position.side == 'long' and current_high >= position.take_profit) or \
                       (position.side == 'short' and current_low <= position.take_profit):
                        exit_price = position.take_profit
                        self._close_position(position, exit_price, current_time, 'take_profit')
                        positions_to_close.append(pos_idx)
                        continue
                
                # Обновляем максимальную прибыль/убыток
                if position.side == 'long':
                    current_profit = (current_price - position.entry_price) / position.entry_price
                else:
                    current_profit = (position.entry_price - current_price) / position.entry_price
                
                position.max_profit = max(position.max_profit, current_profit)
                position.max_loss = min(position.max_loss, current_profit)
                
                # Trailing Stop
                if self.config.trailing_stop and current_profit > self.config.trailing_stop_distance:
                    if position.side == 'long':
                        new_stop = current_price * (1 - self.config.trailing_stop_distance)
                        if position.stop_loss:
                            position.stop_loss = max(position.stop_loss, new_stop)
                        else:
                            position.stop_loss = new_stop
                    else:
                        new_stop = current_price * (1 + self.config.trailing_stop_distance)
                        if position.stop_loss:
                            position.stop_loss = min(position.stop_loss, new_stop)
                        else:
                            position.stop_loss = new_stop
            
            # Удаляем закрытые позиции
            for idx in sorted(positions_to_close, reverse=True):
                closed_trade = open_positions.pop(idx)
                trades.append(closed_trade)
                balance += closed_trade.profit
            
            # Проверяем сигналы для новых позиций
            if len(open_positions) < self.config.max_open_positions and i < len(predictions):
                prediction = predictions.iloc[i]
                
                # Получаем сигнал
                signal = prediction.get('signal', 'hold')
                confidence = prediction.get('confidence', 0.0)
                tp_percent = prediction.get('take_profit_percent', 2.0)
                sl_percent = prediction.get('stop_loss_percent', 1.0)
                strategy = prediction.get('strategy', 'unknown')
                
                # Определяем размер позиции
                position_size = self._calculate_position_size(
                    balance, current_price, sl_percent, confidence
                )
                
                # Открываем позицию
                if signal == 'buy' and position_size > 0:
                    if self.config.enable_shorting:
                        # Закрываем короткие позиции
                        for pos_idx, pos in enumerate(open_positions):
                            if pos.side == 'short':
                                self._close_position(pos, current_price, current_time, 'signal_reversal')
                                positions_to_close.append(pos_idx)
                    
                    # Открываем длинную позицию
                    new_trade = self._open_position(
                        'long', current_time, current_price, position_size,
                        sl_percent, tp_percent, confidence, strategy
                    )
                    open_positions.append(new_trade)
                    balance -= new_trade.position_size + new_trade.commission_paid
                    
                elif signal == 'sell' and self.config.enable_shorting and position_size > 0:
                    # Закрываем длинные позиции
                    for pos_idx, pos in enumerate(open_positions):
                        if pos.side == 'long':
                            self._close_position(pos, current_price, current_time, 'signal_reversal')
                            positions_to_close.append(pos_idx)
                    
                    # Открываем короткую позицию
                    new_trade = self._open_position(
                        'short', current_time, current_price, position_size,
                        sl_percent, tp_percent, confidence, strategy
                    )
                    open_positions.append(new_trade)
                    balance -= new_trade.position_size + new_trade.commission_paid
            
            # Обновляем баланс с учетом открытых позиций
            current_equity = balance
            for position in open_positions:
                if position.side == 'long':
                    current_value = position.position_size * (current_price / position.entry_price)
                else:
                    current_value = position.position_size * (2 - current_price / position.entry_price)
                current_equity += current_value
            
            equity.append(current_equity)
        
        # Закрываем все открытые позиции
        final_price = market_data.iloc[-1]['close']
        final_time = market_data.index[-1]
        
        for position in open_positions:
            self._close_position(position, final_price, final_time, 'end_of_backtest')
            trades.append(position)
            balance += position.profit
        
        # Рассчитываем результаты
        result = self._calculate_results(trades, equity, market_data)
        
        self.logger.info(
            f"Бэктест завершен: Return={result.total_return_percent:.2f}%, "
            f"Trades={result.total_trades}, WinRate={result.win_rate:.2f}%",
            category='backtest'
        )
        
        return result
    
    def _open_position(self, side: str, entry_time: datetime, entry_price: float,
                      position_size: float, sl_percent: float, tp_percent: float,
                      confidence: float, strategy: str) -> Trade:
        """Открывает новую позицию"""
        commission = position_size * self.config.commission
        
        # Учитываем slippage
        if side == 'long':
            entry_price *= (1 + self.config.slippage)
            stop_loss = entry_price * (1 - sl_percent / 100) if self.config.use_stop_loss else None
            take_profit = entry_price * (1 + tp_percent / 100) if self.config.use_take_profit else None
        else:
            entry_price *= (1 - self.config.slippage)
            stop_loss = entry_price * (1 + sl_percent / 100) if self.config.use_stop_loss else None
            take_profit = entry_price * (1 - tp_percent / 100) if self.config.use_take_profit else None
        
        trade = Trade(
            entry_time=entry_time,
            entry_price=entry_price,
            position_size=position_size,
            side=side,
            stop_loss=stop_loss,
            take_profit=take_profit,
            commission_paid=commission,
            ml_confidence=confidence,
            strategy=strategy
        )
        
        return trade
    
    def _close_position(self, trade: Trade, exit_price: float, 
                       exit_time: datetime, exit_reason: str):
        """Закрывает позицию"""
        # Учитываем slippage
        if trade.side == 'long':
            exit_price *= (1 - self.config.slippage)
        else:
            exit_price *= (1 + self.config.slippage)
        
        trade.exit_time = exit_time
        trade.exit_price = exit_price
        trade.exit_reason = exit_reason
        trade.duration = exit_time - trade.entry_time
        
        # Рассчитываем прибыль
        if trade.side == 'long':
            trade.profit = trade.position_size * (exit_price / trade.entry_price - 1)
        else:
            trade.profit = trade.position_size * (1 - exit_price / trade.entry_price)
        
        # Учитываем комиссию за закрытие
        exit_commission = trade.position_size * self.config.commission
        trade.commission_paid += exit_commission
        trade.profit -= trade.commission_paid
        
        # Процент прибыли
        trade.profit_percent = (trade.profit / trade.position_size) * 100
    
    def _calculate_position_size(self, balance: float, price: float,
                               sl_percent: float, confidence: float) -> float:
        """Рассчитывает размер позиции с учетом риск-менеджмента"""
        # Базовый размер на основе риска
        risk_amount = balance * self.config.risk_per_trade
        position_size = risk_amount / (sl_percent / 100)
        
        # Корректировка на основе уверенности ML
        confidence_factor = 0.5 + confidence * 0.5  # от 50% до 100%
        position_size *= confidence_factor
        
        # Ограничения
        max_position = balance * self.config.max_position_size
        position_size = min(position_size, max_position)
        
        # Учитываем leverage
        if self.config.use_leverage:
            position_size *= self.config.leverage
        
        return position_size
    
    def _calculate_results(self, trades: List[Trade], equity: List[float],
                         market_data: pd.DataFrame) -> BacktestResult:
        """Рассчитывает результаты бэктестинга"""
        result = BacktestResult()
        
        if not trades:
            return result
        
        # Основные метрики
        result.total_trades = len(trades)
        result.trades = trades
        
        profits = [t.profit for t in trades]
        winning_trades = [t for t in trades if t.profit > 0]
        losing_trades = [t for t in trades if t.profit < 0]
        
        result.winning_trades = len(winning_trades)
        result.losing_trades = len(losing_trades)
        result.win_rate = (result.winning_trades / result.total_trades * 100) if result.total_trades > 0 else 0
        
        # Финансовые метрики
        result.gross_profit = sum(t.profit for t in winning_trades)
        result.gross_loss = sum(t.profit for t in losing_trades)
        result.total_return = sum(profits)
        result.total_return_percent = (result.total_return / self.config.initial_balance) * 100
        
        if losing_trades:
            result.profit_factor = abs(result.gross_profit / result.gross_loss)
            result.avg_loss = result.gross_loss / len(losing_trades)
            result.largest_loss = min(t.profit for t in losing_trades)
        
        if winning_trades:
            result.avg_win = result.gross_profit / len(winning_trades)
            result.largest_win = max(t.profit for t in winning_trades)
        
        # Equity curve
        equity_series = pd.Series(equity, index=market_data.index[:len(equity)])
        result.equity_curve = equity_series
        
        # Drawdown
        rolling_max = equity_series.expanding().max()
        drawdown = (equity_series - rolling_max) / rolling_max
        result.drawdown_curve = drawdown
        result.max_drawdown = drawdown.min()
        result.max_drawdown_percent = result.max_drawdown * 100
        
        # Risk metrics
        returns = equity_series.pct_change().dropna()
        
        if len(returns) > 1:
            # Sharpe Ratio (предполагаем 0% risk-free rate)
            result.sharpe_ratio = np.sqrt(252) * returns.mean() / returns.std() if returns.std() > 0 else 0
            
            # Sortino Ratio
            downside_returns = returns[returns < 0]
            downside_std = downside_returns.std() if len(downside_returns) > 0 else 0
            result.sortino_ratio = np.sqrt(252) * returns.mean() / downside_std if downside_std > 0 else 0
            
            # Calmar Ratio
            result.calmar_ratio = (result.total_return_percent / 100) / abs(result.max_drawdown) if result.max_drawdown != 0 else 0
        
        # Временные метрики
        durations = [t.duration for t in trades if t.duration]
        if durations:
            result.avg_trade_duration = sum(durations, timedelta()) / len(durations)
            result.longest_trade = max(durations)
            result.shortest_trade = min(durations)
        
        # ML метрики
        ml_confidences = [t.ml_confidence for t in trades]
        result.avg_ml_confidence = np.mean(ml_confidences) if ml_confidences else 0
        
        # Корреляция между уверенностью и прибылью
        if len(trades) > 3:
            correlation = stats.pearsonr(ml_confidences, [t.profit_percent for t in trades])
            result.confidence_vs_profit_correlation = correlation[0]
        
        # Производительность по стратегиям
        strategy_groups = defaultdict(list)
        for trade in trades:
            strategy_groups[trade.strategy].append(trade)
        
        for strategy, strategy_trades in strategy_groups.items():
            strategy_profits = [t.profit for t in strategy_trades]
            strategy_wins = [t for t in strategy_trades if t.profit > 0]
            
            result.strategy_performance[strategy] = {
                'total_trades': len(strategy_trades),
                'win_rate': len(strategy_wins) / len(strategy_trades) * 100,
                'total_profit': sum(strategy_profits),
                'avg_profit': np.mean(strategy_profits),
                'avg_confidence': np.mean([t.ml_confidence for t in strategy_trades])
            }
        
        # Месячные доходности
        monthly_returns = equity_series.resample('M').last().pct_change().dropna()
        result.monthly_returns = monthly_returns
        
        return result
    
    def run_walk_forward_analysis(self,
                                market_data: pd.DataFrame,
                                features: pd.DataFrame,
                                ml_models: Dict[str, Any],
                                window_size: int = 252,  # 1 год
                                step_size: int = 21,     # 1 месяц
                                retrain_frequency: int = 63) -> Dict[str, Any]:
        """
        Walk-forward анализ для проверки устойчивости стратегии
        
        Args:
            market_data: Рыночные данные
            features: Признаки
            ml_models: ML модели для тестирования
            window_size: Размер окна обучения
            step_size: Шаг сдвига окна
            retrain_frequency: Частота переобучения модели
            
        Returns:
            Результаты walk-forward анализа
        """
        self.logger.info(
            "Запуск walk-forward анализа",
            category='backtest',
            window_size=window_size,
            step_size=step_size
        )
        
        results = []
        periods = []
        
        for start_idx in range(0, len(market_data) - window_size - step_size, step_size):
            # Определяем периоды
            train_start = start_idx
            train_end = start_idx + window_size
            test_start = train_end
            test_end = min(test_start + step_size, len(market_data))
            
            # Данные для обучения
            train_market = market_data.iloc[train_start:train_end]
            train_features = features.iloc[train_start:train_end]
            
            # Данные для тестирования
            test_market = market_data.iloc[test_start:test_end]
            test_features = features.iloc[test_start:test_end]
            
            # Переобучаем модели если необходимо
            if start_idx % retrain_frequency == 0:
                for model_name, model in ml_models.items():
                    if hasattr(model, 'train'):
                        self.logger.info(
                            f"Переобучение модели {model_name}",
                            category='backtest'
                        )
                        # Здесь должен быть код обучения модели
                        # model.train(train_features, train_labels)
            
            # Получаем предсказания для тестового периода
            predictions = pd.DataFrame(index=test_features.index)
            
            # Заглушка для предсказаний
            # В реальности здесь должны быть предсказания от ML моделей
            predictions['signal'] = np.random.choice(['buy', 'sell', 'hold'], size=len(test_features))
            predictions['confidence'] = np.random.uniform(0.5, 1.0, size=len(test_features))
            predictions['take_profit_percent'] = np.random.uniform(1.0, 3.0, size=len(test_features))
            predictions['stop_loss_percent'] = np.random.uniform(0.5, 1.5, size=len(test_features))
            predictions['strategy'] = 'ml_ensemble'
            
            # Запускаем бэктест на тестовом периоде
            period_result = self.run_backtest(test_market, test_features, predictions)
            
            results.append(period_result)
            periods.append({
                'train_start': train_market.index[0],
                'train_end': train_market.index[-1],
                'test_start': test_market.index[0],
                'test_end': test_market.index[-1]
            })
        
        # Анализируем результаты
        analysis = self._analyze_walk_forward_results(results, periods)
        
        return analysis
    
    def _analyze_walk_forward_results(self, results: List[BacktestResult],
                                    periods: List[Dict]) -> Dict[str, Any]:
        """Анализирует результаты walk-forward тестирования"""
        analysis = {
            'total_periods': len(results),
            'periods': periods,
            'aggregate_metrics': {},
            'consistency_metrics': {},
            'period_results': []
        }
        
        # Собираем метрики по периодам
        metrics = {
            'returns': [r.total_return_percent for r in results],
            'win_rates': [r.win_rate for r in results],
            'sharpe_ratios': [r.sharpe_ratio for r in results],
            'max_drawdowns': [r.max_drawdown_percent for r in results],
            'profit_factors': [r.profit_factor for r in results],
            'total_trades': [r.total_trades for r in results]
        }
        
        # Агрегированные метрики
        for metric_name, values in metrics.items():
            analysis['aggregate_metrics'][metric_name] = {
                'mean': np.mean(values),
                'std': np.std(values),
                'min': np.min(values),
                'max': np.max(values),
                'median': np.median(values)
            }
        
        # Метрики консистентности
        positive_periods = sum(1 for r in metrics['returns'] if r > 0)
        analysis['consistency_metrics']['win_period_rate'] = positive_periods / len(results) * 100
        
        # Стабильность результатов
        analysis['consistency_metrics']['return_stability'] = 1 / (1 + np.std(metrics['returns']))
        analysis['consistency_metrics']['sharpe_stability'] = 1 / (1 + np.std(metrics['sharpe_ratios']))
        
        # Тренд производительности
        if len(results) > 3:
            x = np.arange(len(results))
            slope, intercept = np.polyfit(x, metrics['returns'], 1)
            analysis['consistency_metrics']['performance_trend'] = slope
        
        # Детали по периодам
        for i, (result, period) in enumerate(zip(results, periods)):
            analysis['period_results'].append({
                'period': i + 1,
                'dates': period,
                'return': result.total_return_percent,
                'trades': result.total_trades,
                'win_rate': result.win_rate,
                'sharpe': result.sharpe_ratio,
                'max_dd': result.max_drawdown_percent
            })
        
        return analysis
    
    def plot_backtest_results(self, result: BacktestResult, save_path: Optional[str] = None):
        """
        Визуализирует результаты бэктестинга
        
        Args:
            result: Результаты бэктестинга
            save_path: Путь для сохранения графиков
        """
        fig, axes = plt.subplots(3, 2, figsize=(15, 12))
        fig.suptitle('Backtest Results', fontsize=16)
        
        # 1. Equity Curve
        ax = axes[0, 0]
        result.equity_curve.plot(ax=ax, linewidth=2, color='blue')
        ax.set_title('Equity Curve')
        ax.set_ylabel('Balance')
        ax.grid(True, alpha=0.3)
        
        # 2. Drawdown
        ax = axes[0, 1]
        result.drawdown_curve.plot(ax=ax, linewidth=2, color='red', alpha=0.7)
        ax.fill_between(result.drawdown_curve.index, 0, result.drawdown_curve.values, 
                       color='red', alpha=0.3)
        ax.set_title('Drawdown')
        ax.set_ylabel('Drawdown %')
        ax.grid(True, alpha=0.3)
        
        # 3. Monthly Returns
        ax = axes[1, 0]
        if not result.monthly_returns.empty:
            result.monthly_returns.plot(kind='bar', ax=ax, color='green', alpha=0.7)
            ax.set_title('Monthly Returns')
            ax.set_ylabel('Return %')
            ax.tick_params(axis='x', rotation=45)
        
        # 4. Trade Distribution
        ax = axes[1, 1]
        profits = [t.profit_percent for t in result.trades]
        if profits:
            ax.hist(profits, bins=30, color='skyblue', alpha=0.7, edgecolor='black')
            ax.axvline(x=0, color='red', linestyle='--', alpha=0.7)
            ax.set_title('Trade Profit Distribution')
            ax.set_xlabel('Profit %')
            ax.set_ylabel('Frequency')
        
        # 5. Win Rate by Strategy
        ax = axes[2, 0]
        if result.strategy_performance:
            strategies = list(result.strategy_performance.keys())
            win_rates = [result.strategy_performance[s]['win_rate'] for s in strategies]
            ax.bar(strategies, win_rates, color='purple', alpha=0.7)
            ax.set_title('Win Rate by Strategy')
            ax.set_ylabel('Win Rate %')
            ax.tick_params(axis='x', rotation=45)
        
        # 6. Cumulative Returns
        ax = axes[2, 1]
        cumulative_returns = (1 + result.equity_curve.pct_change()).cumprod()
        cumulative_returns.plot(ax=ax, linewidth=2, color='orange')
        ax.set_title('Cumulative Returns')
        ax.set_ylabel('Cumulative Return')
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            self.logger.info(f"График сохранен: {save_path}", category='backtest')
        
        plt.show()
    
    def generate_report(self, result: BacktestResult) -> str:
        """
        Генерирует текстовый отчет о результатах бэктестинга
        
        Args:
            result: Результаты бэктестинга
            
        Returns:
            Форматированный отчет
        """
        report = []
        report.append("=" * 60)
        report.append("BACKTEST REPORT")
        report.append("=" * 60)
        report.append("")
        
        # Основные метрики
        report.append("PERFORMANCE SUMMARY")
        report.append("-" * 30)
        report.append(f"Total Return: ${result.total_return:.2f} ({result.total_return_percent:.2f}%)")
        report.append(f"Total Trades: {result.total_trades}")
        report.append(f"Win Rate: {result.win_rate:.2f}%")
        report.append(f"Profit Factor: {result.profit_factor:.2f}")
        report.append("")
        
        # Финансовые метрики
        report.append("FINANCIAL METRICS")
        report.append("-" * 30)
        report.append(f"Gross Profit: ${result.gross_profit:.2f}")
        report.append(f"Gross Loss: ${result.gross_loss:.2f}")
        report.append(f"Average Win: ${result.avg_win:.2f}")
        report.append(f"Average Loss: ${result.avg_loss:.2f}")
        report.append(f"Largest Win: ${result.largest_win:.2f}")
        report.append(f"Largest Loss: ${result.largest_loss:.2f}")
        report.append("")
        
        # Риск метрики
        report.append("RISK METRICS")
        report.append("-" * 30)
        report.append(f"Max Drawdown: {result.max_drawdown_percent:.2f}%")
        report.append(f"Sharpe Ratio: {result.sharpe_ratio:.2f}")
        report.append(f"Sortino Ratio: {result.sortino_ratio:.2f}")
        report.append(f"Calmar Ratio: {result.calmar_ratio:.2f}")
        report.append("")
        
        # ML метрики
        report.append("ML METRICS")
        report.append("-" * 30)
        report.append(f"Average ML Confidence: {result.avg_ml_confidence:.2f}")
        report.append(f"Confidence-Profit Correlation: {result.confidence_vs_profit_correlation:.2f}")
        report.append("")
        
        # Стратегии
        if result.strategy_performance:
            report.append("STRATEGY PERFORMANCE")
            report.append("-" * 30)
            for strategy, metrics in result.strategy_performance.items():
                report.append(f"\n{strategy}:")
                report.append(f"  Trades: {metrics['total_trades']}")
                report.append(f"  Win Rate: {metrics['win_rate']:.2f}%")
                report.append(f"  Total Profit: ${metrics['total_profit']:.2f}")
                report.append(f"  Avg Confidence: {metrics['avg_confidence']:.2f}")
        
        report.append("")
        report.append("=" * 60)
        
        return "\n".join(report)