"""
Продвинутая система аналитики для торгового бота
Путь: src/analysis/advanced_analytics.py
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
from sqlalchemy import func, and_, or_
from collections import defaultdict

from ..core.database import SessionLocal
from ..core.models import Trade, Signal, Balance, TradeStatus

logger = logging.getLogger(__name__)

class AdvancedAnalytics:
    """
    Продвинутая аналитика для глубокого анализа торговли
    
    Возможности:
    - Анализ поведения графика до/во время/после сделки
    - Паттерны успешных и неудачных сделок
    - Корреляция между индикаторами и результатами
    - Временной анализ (лучшее время для торговли)
    - Анализ просадок и восстановления
    """
    
    def __init__(self):
        self.analysis_window_minutes = 30  # Окно анализа до/после сделки
        
    async def analyze_trade_context(
        self, 
        trade_id: int, 
        market_data: pd.DataFrame
    ) -> Dict:
        """
        Анализирует контекст конкретной сделки
        
        Args:
            trade_id: ID сделки для анализа
            market_data: Исторические данные рынка
            
        Returns:
            Dict с детальным анализом контекста сделки
        """
        db = SessionLocal()
        try:
            trade = db.query(Trade).filter(Trade.id == trade_id).first()
            if not trade:
                return {'error': 'Trade not found'}
            
            # Временные метки для анализа
            entry_time = trade.created_at
            exit_time = trade.closed_at or datetime.utcnow()
            
            # Окна анализа
            before_start = entry_time - timedelta(minutes=self.analysis_window_minutes)
            after_end = exit_time + timedelta(minutes=self.analysis_window_minutes)
            
            # Фильтруем данные по временным окнам
            context_data = market_data[
                (market_data.index >= before_start) & 
                (market_data.index <= after_end)
            ].copy()
            
            if context_data.empty:
                return {'error': 'No market data for analysis period'}
            
            # Анализ периодов
            before_trade = context_data[context_data.index < entry_time]
            during_trade = context_data[
                (context_data.index >= entry_time) & 
                (context_data.index <= exit_time)
            ]
            after_trade = context_data[context_data.index > exit_time]
            
            analysis = {
                'trade_id': trade_id,
                'symbol': trade.symbol,
                'side': trade.side.value if hasattr(trade.side, 'value') else str(trade.side),
                'profit': float(trade.profit) if trade.profit else 0,
                
                # Анализ до входа
                'before_entry': self._analyze_period(before_trade, 'before'),
                
                # Анализ во время сделки
                'during_trade': self._analyze_period(during_trade, 'during'),
                
                # Анализ после выхода
                'after_exit': self._analyze_period(after_trade, 'after'),
                
                # Общие метрики
                'entry_quality': self._assess_entry_quality(trade, before_trade),
                'exit_quality': self._assess_exit_quality(trade, during_trade, after_trade),
                
                # Упущенная прибыль/избежанный убыток
                'missed_opportunities': self._analyze_missed_opportunities(
                    trade, during_trade, after_trade
                )
            }
            
            return analysis
            
        finally:
            db.close()
    
    def _analyze_period(self, data: pd.DataFrame, period_type: str) -> Dict:
        """Анализирует конкретный период"""
        if data.empty:
            return {'error': 'No data for period'}
        
        analysis = {
            'period_type': period_type,
            'duration_minutes': len(data),
            
            # Движение цены
            'price_change': {
                'absolute': float(data['close'].iloc[-1] - data['close'].iloc[0]),
                'percent': float((data['close'].iloc[-1] - data['close'].iloc[0]) / 
                                data['close'].iloc[0] * 100),
                'high_low_range': float(data['high'].max() - data['low'].min()),
                'volatility': float(data['close'].std())
            },
            
            # Объем
            'volume': {
                'total': float(data['volume'].sum()),
                'average': float(data['volume'].mean()),
                'trend': 'increasing' if data['volume'].iloc[-5:].mean() > 
                         data['volume'].iloc[:5].mean() else 'decreasing'
            },
            
            # Свечной анализ
            'candle_patterns': self._identify_candle_patterns(data),
            
            # Тренд
            'trend': self._identify_trend(data),
            
            # Экстремумы
            'extremes': {
                'highest': float(data['high'].max()),
                'lowest': float(data['low'].min()),
                'highest_time': data['high'].idxmax().isoformat() if not data.empty else None,
                'lowest_time': data['low'].idxmin().isoformat() if not data.empty else None
            }
        }
        
        return analysis
    
    def _identify_candle_patterns(self, data: pd.DataFrame) -> List[Dict]:
        """Идентифицирует свечные паттерны"""
        patterns = []
        
        if len(data) < 3:
            return patterns
        
        # Проверяем последние 3 свечи на паттерны
        for i in range(2, len(data)):
            candle = data.iloc[i]
            prev_candle = data.iloc[i-1]
            prev_prev_candle = data.iloc[i-2]
            
            # Бычье поглощение
            if (candle['close'] > candle['open'] and 
                prev_candle['close'] < prev_candle['open'] and
                candle['close'] > prev_candle['open'] and
                candle['open'] < prev_candle['close']):
                patterns.append({
                    'type': 'bullish_engulfing',
                    'time': candle.name.isoformat(),
                    'strength': 'strong'
                })
            
            # Медвежье поглощение
            elif (candle['close'] < candle['open'] and
                  prev_candle['close'] > prev_candle['open'] and
                  candle['close'] < prev_candle['open'] and
                  candle['open'] > prev_candle['close']):
                patterns.append({
                    'type': 'bearish_engulfing',
                    'time': candle.name.isoformat(),
                    'strength': 'strong'
                })
            
            # Молот
            body = abs(candle['close'] - candle['open'])
            lower_wick = candle['open'] - candle['low'] if candle['close'] > candle['open'] else candle['close'] - candle['low']
            upper_wick = candle['high'] - candle['close'] if candle['close'] > candle['open'] else candle['high'] - candle['open']
            
            if lower_wick > body * 2 and upper_wick < body * 0.5:
                patterns.append({
                    'type': 'hammer',
                    'time': candle.name.isoformat(),
                    'strength': 'medium'
                })
        
        return patterns
    
    def _identify_trend(self, data: pd.DataFrame) -> Dict:
        """Определяет тренд"""
        if len(data) < 5:
            return {'direction': 'undefined', 'strength': 0}
        
        # Простая линейная регрессия
        x = np.arange(len(data))
        y = data['close'].values
        
        # Вычисляем наклон
        slope = np.polyfit(x, y, 1)[0]
        
        # Определяем направление и силу
        avg_price = data['close'].mean()
        slope_percent = (slope / avg_price) * 100
        
        if slope_percent > 0.5:
            direction = 'up'
            strength = min(slope_percent / 2, 10)  # Нормализуем до 0-10
        elif slope_percent < -0.5:
            direction = 'down'
            strength = min(abs(slope_percent) / 2, 10)
        else:
            direction = 'sideways'
            strength = 0
        
        return {
            'direction': direction,
            'strength': float(strength),
            'slope_percent': float(slope_percent)
        }
    
    def _assess_entry_quality(self, trade: Trade, before_data: pd.DataFrame) -> Dict:
        """Оценивает качество входа в сделку"""
        if before_data.empty:
            return {'score': 0, 'factors': []}
        
        factors = []
        score = 50  # Базовый счет
        
        # Фактор 1: Вход на отскоке от поддержки/сопротивления
        support = before_data['low'].rolling(window=20).min().iloc[-1]
        resistance = before_data['high'].rolling(window=20).max().iloc[-1]
        entry_price = float(trade.entry_price)
        
        if trade.side.value == 'BUY' and abs(entry_price - support) / entry_price < 0.01:
            score += 20
            factors.append('Вход от поддержки (+20)')
        elif trade.side.value == 'SELL' and abs(entry_price - resistance) / entry_price < 0.01:
            score += 20
            factors.append('Вход от сопротивления (+20)')
        
        # Фактор 2: Вход по тренду
        trend = self._identify_trend(before_data)
        if (trend['direction'] == 'up' and trade.side.value == 'BUY') or \
           (trend['direction'] == 'down' and trade.side.value == 'SELL'):
            score += 15
            factors.append(f'Вход по тренду (+15)')
        
        # Фактор 3: Объем подтверждает
        avg_volume = before_data['volume'].mean()
        entry_volume = before_data['volume'].iloc[-1]
        if entry_volume > avg_volume * 1.5:
            score += 15
            factors.append('Высокий объем на входе (+15)')
        
        return {
            'score': min(score, 100),
            'factors': factors
        }
    
    def _assess_exit_quality(self, trade: Trade, during_data: pd.DataFrame, 
                           after_data: pd.DataFrame) -> Dict:
        """Оценивает качество выхода из сделки"""
        factors = []
        score = 50
        
        if during_data.empty:
            return {'score': 0, 'factors': []}
        
        exit_price = float(trade.exit_price) if trade.exit_price else during_data['close'].iloc[-1]
        
        # Фактор 1: Вышли вовремя (не слишком рано)
        if not after_data.empty and trade.profit and trade.profit > 0:
            # Проверяем, продолжилось ли движение
            if trade.side.value == 'BUY':
                missed_profit = after_data['high'].max() - exit_price
            else:
                missed_profit = exit_price - after_data['low'].min()
            
            missed_percent = abs(missed_profit / exit_price * 100)
            if missed_percent < 1:  # Упустили менее 1%
                score += 20
                factors.append('Оптимальный выход (+20)')
            elif missed_percent > 3:  # Упустили более 3%
                score -= 20
                factors.append(f'Ранний выход, упущено {missed_percent:.1f}% (-20)')
        
        # Фактор 2: Защитили прибыль
        if trade.profit and trade.profit > 0:
            max_profit = during_data['high'].max() - float(trade.entry_price) if trade.side.value == 'BUY' \
                        else float(trade.entry_price) - during_data['low'].min()
            
            profit_protected = trade.profit / max_profit if max_profit > 0 else 0
            if profit_protected > 0.7:  # Защитили более 70% максимальной прибыли
                score += 15
                factors.append(f'Защищено {profit_protected:.0%} прибыли (+15)')
        
        return {
            'score': min(max(score, 0), 100),
            'factors': factors
        }
    
    def _analyze_missed_opportunities(self, trade: Trade, during_data: pd.DataFrame, 
                                    after_data: pd.DataFrame) -> Dict:
        """Анализирует упущенные возможности"""
        analysis = {
            'missed_profit': 0,
            'avoided_loss': 0,
            'optimal_exit_price': 0,
            'optimal_exit_time': None
        }
        
        if during_data.empty:
            return analysis
        
        entry_price = float(trade.entry_price)
        exit_price = float(trade.exit_price) if trade.exit_price else during_data['close'].iloc[-1]
        
        # Для лонгов
        if trade.side.value == 'BUY':
            # Оптимальная точка выхода
            optimal_exit_idx = during_data['high'].idxmax()
            optimal_exit_price = during_data['high'].max()
            
            # Упущенная прибыль
            analysis['missed_profit'] = max(0, optimal_exit_price - exit_price)
            
            # Избежанный убыток (если вышли до падения)
            if not after_data.empty:
                worst_after = after_data['low'].min()
                analysis['avoided_loss'] = max(0, exit_price - worst_after)
        
        # Для шортов
        else:
            optimal_exit_idx = during_data['low'].idxmin()
            optimal_exit_price = during_data['low'].min()
            
            analysis['missed_profit'] = max(0, exit_price - optimal_exit_price)
            
            if not after_data.empty:
                worst_after = after_data['high'].max()
                analysis['avoided_loss'] = max(0, worst_after - exit_price)
        
        analysis['optimal_exit_price'] = float(optimal_exit_price)
        analysis['optimal_exit_time'] = optimal_exit_idx.isoformat() if optimal_exit_idx else None
        
        # Процентные значения
        analysis['missed_profit_percent'] = (analysis['missed_profit'] / exit_price * 100)
        analysis['avoided_loss_percent'] = (analysis['avoided_loss'] / exit_price * 100)
        
        return analysis
    
    async def generate_performance_report(self, days: int = 30) -> Dict:
        """
        Генерирует подробный отчет о производительности
        
        Args:
            days: Количество дней для анализа
            
        Returns:
            Dict с полным отчетом о производительности
        """
        db = SessionLocal()
        try:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            # Получаем все сделки за период
            trades = db.query(Trade).filter(
                Trade.created_at >= start_date,
                Trade.status == TradeStatus.CLOSED
            ).all()
            
            if not trades:
                return {'error': 'No closed trades for analysis'}
            
            # Базовая статистика
            total_trades = len(trades)
            profitable_trades = [t for t in trades if t.profit and t.profit > 0]
            losing_trades = [t for t in trades if t.profit and t.profit < 0]
            
            # Прибыль/убыток
            total_profit = sum(t.profit for t in trades if t.profit)
            total_profit_winning = sum(t.profit for t in profitable_trades)
            total_loss = sum(t.profit for t in losing_trades)
            
            # Win rate
            win_rate = len(profitable_trades) / total_trades * 100 if total_trades > 0 else 0
            
            # Средние значения
            avg_profit = total_profit_winning / len(profitable_trades) if profitable_trades else 0
            avg_loss = total_loss / len(losing_trades) if losing_trades else 0
            
            # Profit factor
            profit_factor = abs(total_profit_winning / total_loss) if total_loss != 0 else float('inf')
            
            # Максимальная просадка
            drawdown_info = self._calculate_drawdown(trades)
            
            # Анализ по времени
            time_analysis = self._analyze_by_time(trades)
            
            # Анализ по парам
            pairs_analysis = self._analyze_by_pairs(trades)
            
            # Анализ по стратегиям
            strategy_analysis = self._analyze_by_strategies(trades)
            
            # Корреляционный анализ
            correlation_analysis = await self._analyze_correlations(trades)
            
            report = {
                'period': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat(),
                    'days': days
                },
                
                'summary': {
                    'total_trades': total_trades,
                    'profitable_trades': len(profitable_trades),
                    'losing_trades': len(losing_trades),
                    'win_rate': round(win_rate, 2),
                    'total_profit': round(total_profit, 2),
                    'profit_factor': round(profit_factor, 2) if profit_factor != float('inf') else 'inf',
                    'average_win': round(avg_profit, 2),
                    'average_loss': round(avg_loss, 2),
                    'expectancy': round((win_rate/100 * avg_profit) + ((1-win_rate/100) * avg_loss), 2)
                },
                
                'drawdown': drawdown_info,
                'time_analysis': time_analysis,
                'pairs_performance': pairs_analysis,
                'strategy_performance': strategy_analysis,
                'correlations': correlation_analysis,
                
                'best_trades': self._get_best_trades(trades, 5),
                'worst_trades': self._get_worst_trades(trades, 5),
                
                'recommendations': self._generate_recommendations(
                    trades, time_analysis, pairs_analysis, strategy_analysis
                )
            }
            
            return report
            
        finally:
            db.close()
    
    def _calculate_drawdown(self, trades: List[Trade]) -> Dict:
        """Рассчитывает максимальную просадку"""
        if not trades:
            return {'max_drawdown': 0, 'max_drawdown_percent': 0}
        
        # Сортируем по времени
        sorted_trades = sorted(trades, key=lambda x: x.created_at)
        
        # Рассчитываем кумулятивную прибыль
        cumulative_profit = []
        running_total = 0
        
        for trade in sorted_trades:
            running_total += trade.profit if trade.profit else 0
            cumulative_profit.append({
                'time': trade.created_at,
                'profit': running_total
            })
        
        # Находим максимальную просадку
        max_drawdown = 0
        max_drawdown_percent = 0
        peak = cumulative_profit[0]['profit']
        
        for point in cumulative_profit:
            if point['profit'] > peak:
                peak = point['profit']
            
            drawdown = peak - point['profit']
            drawdown_percent = (drawdown / peak * 100) if peak > 0 else 0
            
            if drawdown > max_drawdown:
                max_drawdown = drawdown
                max_drawdown_percent = drawdown_percent
        
        return {
            'max_drawdown': round(max_drawdown, 2),
            'max_drawdown_percent': round(max_drawdown_percent, 2),
            'current_drawdown': round(peak - cumulative_profit[-1]['profit'], 2) if cumulative_profit else 0
        }
    
    def _analyze_by_time(self, trades: List[Trade]) -> Dict:
        """Анализирует результаты по времени"""
        time_stats = defaultdict(lambda: {'trades': 0, 'profit': 0, 'wins': 0})
        
        for trade in trades:
            # По часам
            hour = trade.created_at.hour
            time_stats[f'hour_{hour}']['trades'] += 1
            time_stats[f'hour_{hour}']['profit'] += trade.profit if trade.profit else 0
            if trade.profit and trade.profit > 0:
                time_stats[f'hour_{hour}']['wins'] += 1
            
            # По дням недели
            weekday = trade.created_at.weekday()
            day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            time_stats[f'weekday_{day_names[weekday]}']['trades'] += 1
            time_stats[f'weekday_{day_names[weekday]}']['profit'] += trade.profit if trade.profit else 0
            if trade.profit and trade.profit > 0:
                time_stats[f'weekday_{day_names[weekday]}']['wins'] += 1
        
        # Находим лучшее и худшее время
        best_hour = None
        worst_hour = None
        best_hour_profit = float('-inf')
        worst_hour_profit = float('inf')
        
        for key, stats in time_stats.items():
            if key.startswith('hour_'):
                avg_profit = stats['profit'] / stats['trades'] if stats['trades'] > 0 else 0
                if avg_profit > best_hour_profit:
                    best_hour_profit = avg_profit
                    best_hour = key.replace('hour_', '')
                if avg_profit < worst_hour_profit:
                    worst_hour_profit = avg_profit
                    worst_hour = key.replace('hour_', '')
        
        return {
            'by_hour': {k: v for k, v in time_stats.items() if k.startswith('hour_')},
            'by_weekday': {k: v for k, v in time_stats.items() if k.startswith('weekday_')},
            'best_hour': best_hour,
            'worst_hour': worst_hour,
            'best_hour_avg_profit': round(best_hour_profit, 2),
            'worst_hour_avg_profit': round(worst_hour_profit, 2)
        }
    
    def _analyze_by_pairs(self, trades: List[Trade]) -> Dict:
        """Анализирует результаты по торговым парам"""
        pairs_stats = defaultdict(lambda: {
            'trades': 0, 'profit': 0, 'wins': 0, 'losses': 0,
            'best_trade': 0, 'worst_trade': 0
        })
        
        for trade in trades:
            symbol = trade.symbol
            pairs_stats[symbol]['trades'] += 1
            pairs_stats[symbol]['profit'] += trade.profit if trade.profit else 0
            
            if trade.profit:
                if trade.profit > 0:
                    pairs_stats[symbol]['wins'] += 1
                    if trade.profit > pairs_stats[symbol]['best_trade']:
                        pairs_stats[symbol]['best_trade'] = trade.profit
                else:
                    pairs_stats[symbol]['losses'] += 1
                    if trade.profit < pairs_stats[symbol]['worst_trade']:
                        pairs_stats[symbol]['worst_trade'] = trade.profit
        
        # Рассчитываем дополнительные метрики
        for symbol, stats in pairs_stats.items():
            stats['win_rate'] = (stats['wins'] / stats['trades'] * 100) if stats['trades'] > 0 else 0
            stats['avg_profit'] = stats['profit'] / stats['trades'] if stats['trades'] > 0 else 0
            stats['profit_factor'] = abs(stats['best_trade'] / stats['worst_trade']) if stats['worst_trade'] != 0 else float('inf')
        
        # Сортируем по прибыльности
        sorted_pairs = sorted(pairs_stats.items(), key=lambda x: x[1]['profit'], reverse=True)
        
        return {
            'pairs': dict(sorted_pairs),
            'best_pair': sorted_pairs[0][0] if sorted_pairs else None,
            'worst_pair': sorted_pairs[-1][0] if sorted_pairs else None
        }
    
    def _analyze_by_strategies(self, trades: List[Trade]) -> Dict:
        """Анализирует результаты по стратегиям"""
        strategy_stats = defaultdict(lambda: {
            'trades': 0, 'profit': 0, 'wins': 0, 'losses': 0
        })
        
        for trade in trades:
            strategy = trade.strategy
            strategy_stats[strategy]['trades'] += 1
            strategy_stats[strategy]['profit'] += trade.profit if trade.profit else 0
            
            if trade.profit:
                if trade.profit > 0:
                    strategy_stats[strategy]['wins'] += 1
                else:
                    strategy_stats[strategy]['losses'] += 1
        
        # Рассчитываем метрики
        for strategy, stats in strategy_stats.items():
            stats['win_rate'] = (stats['wins'] / stats['trades'] * 100) if stats['trades'] > 0 else 0
            stats['avg_profit'] = stats['profit'] / stats['trades'] if stats['trades'] > 0 else 0
        
        return dict(strategy_stats)
    
    async def _analyze_correlations(self, trades: List[Trade]) -> Dict:
        """Анализирует корреляции между различными факторами"""
        # Здесь можно добавить анализ корреляций между:
        # - Временем дня и прибыльностью
        # - Волатильностью и результатами
        # - Объемом и успешностью сделок
        # и т.д.
        
        correlations = {
            'volume_profit': 0,  # Корреляция между объемом и прибылью
            'volatility_profit': 0,  # Корреляция между волатильностью и прибылью
            'time_profit': 0  # Корреляция между временем дня и прибылью
        }
        
        # Упрощенный пример - в реальности нужен более сложный анализ
        return correlations
    
    def _get_best_trades(self, trades: List[Trade], limit: int = 5) -> List[Dict]:
        """Возвращает лучшие сделки"""
        sorted_trades = sorted(
            [t for t in trades if t.profit and t.profit > 0],
            key=lambda x: x.profit,
            reverse=True
        )[:limit]
        
        return [{
            'id': t.id,
            'symbol': t.symbol,
            'profit': round(t.profit, 2),
            'profit_percent': round((t.profit / (t.entry_price * t.quantity)) * 100, 2),
            'duration': str(t.closed_at - t.created_at) if t.closed_at else 'N/A',
            'strategy': t.strategy,
            'date': t.created_at.isoformat()
        } for t in sorted_trades]
    
    def _get_worst_trades(self, trades: List[Trade], limit: int = 5) -> List[Dict]:
        """Возвращает худшие сделки"""
        sorted_trades = sorted(
            [t for t in trades if t.profit and t.profit < 0],
            key=lambda x: x.profit
        )[:limit]
        
        return [{
            'id': t.id,
            'symbol': t.symbol,
            'profit': round(t.profit, 2),
            'profit_percent': round((t.profit / (t.entry_price * t.quantity)) * 100, 2),
            'duration': str(t.closed_at - t.created_at) if t.closed_at else 'N/A',
            'strategy': t.strategy,
            'date': t.created_at.isoformat()
        } for t in sorted_trades]
    
    def _generate_recommendations(self, trades: List[Trade], time_analysis: Dict,
                                pairs_analysis: Dict, strategy_analysis: Dict) -> List[str]:
        """Генерирует рекомендации на основе анализа"""
        recommendations = []
        
        # Рекомендации по времени
        if time_analysis['best_hour'] and time_analysis['worst_hour']:
            recommendations.append(
                f"Лучшее время для торговли: {time_analysis['best_hour']}:00 "
                f"(средняя прибыль: ${time_analysis['best_hour_avg_profit']:.2f})"
            )
            recommendations.append(
                f"Избегайте торговли в {time_analysis['worst_hour']}:00 "
                f"(средний убыток: ${time_analysis['worst_hour_avg_profit']:.2f})"
            )
        
        # Рекомендации по парам
        if pairs_analysis['best_pair'] and pairs_analysis['worst_pair']:
            best_stats = pairs_analysis['pairs'][pairs_analysis['best_pair']]
            worst_stats = pairs_analysis['pairs'][pairs_analysis['worst_pair']]
            
            recommendations.append(
                f"Самая прибыльная пара: {pairs_analysis['best_pair']} "
                f"(Win rate: {best_stats['win_rate']:.1f}%, прибыль: ${best_stats['profit']:.2f})"
            )
            
            if worst_stats['profit'] < 0:
                recommendations.append(
                    f"Рассмотрите исключение {pairs_analysis['worst_pair']} из торговли "
                    f"(убыток: ${worst_stats['profit']:.2f})"
                )
        
        # Рекомендации по стратегиям
        best_strategy = max(strategy_analysis.items(), 
                           key=lambda x: x[1]['profit']) if strategy_analysis else None
        
        if best_strategy:
            recommendations.append(
                f"Наиболее эффективная стратегия: {best_strategy[0]} "
                f"(прибыль: ${best_strategy[1]['profit']:.2f}, "
                f"Win rate: {best_strategy[1]['win_rate']:.1f}%)"
            )
        
        # Общие рекомендации
        total_trades = len(trades)
        if total_trades > 50:
            avg_trades_per_day = total_trades / 30  # assuming 30 days
            if avg_trades_per_day > 10:
                recommendations.append(
                    "Рассмотрите снижение количества сделок для повышения качества входов"
                )
        
        return recommendations

# Создаем глобальный экземпляр
advanced_analytics = AdvancedAnalytics()