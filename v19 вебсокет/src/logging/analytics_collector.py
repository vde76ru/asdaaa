"""
Сборщик аналитики из логов для улучшения стратегий
Файл: src/logging/analytics_collector.py
"""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
import numpy as np
from sqlalchemy import and_, func, desc
from sqlalchemy.orm import Session

from ..core.database import SessionLocal
from .smart_logger import TradingLog
from ..core.models import Trade, Signal, StrategyPerformance


class AnalyticsCollector:
    """Собирает и анализирует данные из логов для оптимизации торговли"""
    
    def __init__(self):
        self.cache = {}
        self.cache_ttl = 300  # 5 минут
        
    async def collect_trading_analytics(self, 
                                      symbol: Optional[str] = None,
                                      strategy: Optional[str] = None,
                                      period_days: int = 30) -> Dict[str, Any]:
        """Собирает аналитику по торговле"""
        db = SessionLocal()
        try:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=period_days)
            
            # Базовый фильтр
            filters = [
                TradingLog.created_at.between(start_date, end_date),
                TradingLog.category.in_(['trade', 'profit_loss', 'signal'])
            ]
            
            if symbol:
                filters.append(TradingLog.symbol == symbol)
            if strategy:
                filters.append(TradingLog.strategy == strategy)
            
            # Получаем логи
            logs = db.query(TradingLog).filter(and_(*filters)).all()
            
            # Анализируем
            analytics = {
                'period': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat(),
                    'days': period_days
                },
                'trades': self._analyze_trades(logs),
                'signals': self._analyze_signals(logs),
                'errors': self._analyze_errors(db, start_date, end_date, symbol, strategy),
                'patterns': self._analyze_patterns(logs),
                'recommendations': []
            }
            
            # Генерируем рекомендации
            analytics['recommendations'] = self._generate_recommendations(analytics)
            
            return analytics
            
        finally:
            db.close()
    
    def _analyze_trades(self, logs: List[TradingLog]) -> Dict[str, Any]:
        """Анализирует сделки из логов"""
        trade_logs = [log for log in logs if log.category == 'trade']
        profit_logs = [log for log in logs if log.category == 'profit_loss']
        
        if not trade_logs:
            return {'total': 0}
        
        # Подсчет сделок
        opened_trades = len([log for log in trade_logs if 'открыта' in log.message.lower()])
        closed_trades = len([log for log in trade_logs if 'закрыта' in log.message.lower()])
        
        # Анализ прибыльности
        profits = []
        losses = []
        
        for log in profit_logs:
            if log.context and 'profit' in log.context:
                profit = log.context['profit']
                if profit >= 0:
                    profits.append(profit)
                else:
                    losses.append(abs(profit))
        
        total_profit = sum(profits) - sum(losses)
        win_rate = len(profits) / (len(profits) + len(losses)) if profits or losses else 0
        
        # Средние показатели
        avg_profit = np.mean(profits) if profits else 0
        avg_loss = np.mean(losses) if losses else 0
        profit_factor = sum(profits) / sum(losses) if losses else float('inf') if profits else 0
        
        # Время удержания позиций
        hold_times = self._calculate_hold_times(trade_logs)
        
        return {
            'total': opened_trades,
            'opened': opened_trades,
            'closed': closed_trades,
            'active': opened_trades - closed_trades,
            'profitable': len(profits),
            'losing': len(losses),
            'win_rate': win_rate,
            'total_profit': total_profit,
            'avg_profit': avg_profit,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'best_trade': max(profits) if profits else 0,
            'worst_trade': -max(losses) if losses else 0,
            'avg_hold_time_hours': np.mean(hold_times) if hold_times else 0,
            'by_symbol': self._group_by_field(profit_logs, 'symbol'),
            'by_strategy': self._group_by_field(profit_logs, 'strategy')
        }
    
    def _analyze_signals(self, logs: List[TradingLog]) -> Dict[str, Any]:
        """Анализирует сигналы"""
        signal_logs = [log for log in logs if log.category == 'signal']
        
        if not signal_logs:
            return {'total': 0}
        
        # Подсчет по типам
        buy_signals = 0
        sell_signals = 0
        signal_accuracy = defaultdict(lambda: {'total': 0, 'successful': 0})
        
        for log in signal_logs:
            if log.context:
                action = log.context.get('action', '').lower()
                confidence = log.context.get('confidence', 0)
                strategy = log.strategy or 'unknown'
                
                if 'buy' in action:
                    buy_signals += 1
                elif 'sell' in action:
                    sell_signals += 1
                
                signal_accuracy[strategy]['total'] += 1
                # Считаем успешным сигнал с confidence > 0.6
                if confidence > 0.6:
                    signal_accuracy[strategy]['successful'] += 1
        
        # Рассчитываем точность по стратегиям
        strategy_accuracy = {}
        for strategy, data in signal_accuracy.items():
            if data['total'] > 0:
                strategy_accuracy[strategy] = {
                    'accuracy': data['successful'] / data['total'],
                    'total_signals': data['total']
                }
        
        return {
            'total': len(signal_logs),
            'buy_signals': buy_signals,
            'sell_signals': sell_signals,
            'ratio': buy_signals / sell_signals if sell_signals > 0 else 0,
            'avg_confidence': np.mean([
                log.context.get('confidence', 0) 
                for log in signal_logs 
                if log.context and 'confidence' in log.context
            ]) if signal_logs else 0,
            'by_strategy': strategy_accuracy,
            'hourly_distribution': self._get_hourly_distribution(signal_logs)
        }
    
    def _analyze_errors(self, db: Session, start_date: datetime, end_date: datetime,
                       symbol: Optional[str], strategy: Optional[str]) -> Dict[str, Any]:
        """Анализирует ошибки"""
        filters = [
            TradingLog.created_at.between(start_date, end_date),
            TradingLog.log_level.in_(['ERROR', 'CRITICAL'])
        ]
        
        if symbol:
            filters.append(TradingLog.symbol == symbol)
        if strategy:
            filters.append(TradingLog.strategy == strategy)
        
        error_logs = db.query(TradingLog).filter(and_(*filters)).all()
        
        if not error_logs:
            return {'total': 0}
        
        # Группировка ошибок
        error_types = defaultdict(int)
        error_by_time = defaultdict(int)
        
        for log in error_logs:
            # Простая категоризация по ключевым словам
            message_lower = log.message.lower()
            if 'connection' in message_lower or 'timeout' in message_lower:
                error_types['connection'] += 1
            elif 'balance' in message_lower or 'insufficient' in message_lower:
                error_types['insufficient_funds'] += 1
            elif 'api' in message_lower:
                error_types['api_error'] += 1
            elif 'strategy' in message_lower:
                error_types['strategy_error'] += 1
            else:
                error_types['other'] += 1
            
            # По времени
            hour = log.created_at.hour
            error_by_time[hour] += 1
        
        return {
            'total': len(error_logs),
            'critical': len([log for log in error_logs if log.log_level == 'CRITICAL']),
            'by_type': dict(error_types),
            'by_hour': dict(error_by_time),
            'most_common': max(error_types.items(), key=lambda x: x[1])[0] if error_types else None,
            'error_rate': len(error_logs) / max(1, sum(1 for log in error_logs))
        }
    
    def _analyze_patterns(self, logs: List[TradingLog]) -> Dict[str, Any]:
        """Анализирует паттерны в логах"""
        patterns = {
            'time_patterns': self._analyze_time_patterns(logs),
            'sequence_patterns': self._analyze_sequence_patterns(logs),
            'correlation_patterns': self._analyze_correlations(logs)
        }
        
        return patterns
    
    def _analyze_time_patterns(self, logs: List[TradingLog]) -> Dict[str, Any]:
        """Анализирует временные паттерны"""
        if not logs:
            return {}
        
        # Активность по часам
        hourly_activity = defaultdict(int)
        hourly_profit = defaultdict(list)
        
        for log in logs:
            hour = log.created_at.hour
            hourly_activity[hour] += 1
            
            if log.category == 'profit_loss' and log.context and 'profit' in log.context:
                hourly_profit[hour].append(log.context['profit'])
        
        # Лучшие и худшие часы
        best_hours = []
        worst_hours = []
        
        for hour, profits in hourly_profit.items():
            if profits:
                avg_profit = np.mean(profits)
                if avg_profit > 0:
                    best_hours.append((hour, avg_profit))
                else:
                    worst_hours.append((hour, avg_profit))
        
        best_hours.sort(key=lambda x: x[1], reverse=True)
        worst_hours.sort(key=lambda x: x[1])
        
        return {
            'most_active_hours': sorted(hourly_activity.items(), 
                                       key=lambda x: x[1], 
                                       reverse=True)[:3],
            'best_profit_hours': best_hours[:3],
            'worst_profit_hours': worst_hours[:3],
            'weekend_activity': self._calculate_weekend_activity(logs)
        }
    
    def _analyze_sequence_patterns(self, logs: List[TradingLog]) -> Dict[str, Any]:
        """Анализирует последовательности событий"""
        sequences = []
        current_sequence = []
        
        for i, log in enumerate(logs):
            if log.category in ['signal', 'trade']:
                current_sequence.append({
                    'category': log.category,
                    'symbol': log.symbol,
                    'time': log.created_at
                })
                
                # Если следующий лог - profit_loss, завершаем последовательность
                if i + 1 < len(logs) and logs[i + 1].category == 'profit_loss':
                    current_sequence.append({
                        'category': 'profit_loss',
                        'profit': logs[i + 1].context.get('profit', 0) if logs[i + 1].context else 0
                    })
                    sequences.append(current_sequence)
                    current_sequence = []
        
        # Анализируем успешные и неуспешные последовательности
        successful_patterns = []
        failed_patterns = []
        
        for seq in sequences:
            if seq and seq[-1]['category'] == 'profit_loss':
                if seq[-1]['profit'] > 0:
                    successful_patterns.append(len(seq) - 1)  # Количество шагов до профита
                else:
                    failed_patterns.append(len(seq) - 1)
        
        return {
            'avg_steps_to_profit': np.mean(successful_patterns) if successful_patterns else 0,
            'avg_steps_to_loss': np.mean(failed_patterns) if failed_patterns else 0,
            'success_sequences': len(successful_patterns),
            'failed_sequences': len(failed_patterns)
        }
    
    def _analyze_correlations(self, logs: List[TradingLog]) -> Dict[str, Any]:
        """Анализирует корреляции между событиями"""
        correlations = {}
        
        # Корреляция между объемом сигналов и прибыльностью
        signals_by_day = defaultdict(int)
        profits_by_day = defaultdict(float)
        
        for log in logs:
            day = log.created_at.date()
            
            if log.category == 'signal':
                signals_by_day[day] += 1
            elif log.category == 'profit_loss' and log.context and 'profit' in log.context:
                profits_by_day[day] += log.context['profit']
        
        # Рассчитываем корреляцию
        if signals_by_day and profits_by_day:
            common_days = set(signals_by_day.keys()) & set(profits_by_day.keys())
            if len(common_days) >= 3:
                signals_array = np.array([signals_by_day[day] for day in sorted(common_days)])
                profits_array = np.array([profits_by_day[day] for day in sorted(common_days)])
                
                if np.std(signals_array) > 0 and np.std(profits_array) > 0:
                    correlation = np.corrcoef(signals_array, profits_array)[0, 1]
                    correlations['signals_to_profit'] = correlation
        
        return correlations
    
    def _calculate_hold_times(self, trade_logs: List[TradingLog]) -> List[float]:
        """Рассчитывает время удержания позиций"""
        hold_times = []
        open_trades = {}
        
        for log in sorted(trade_logs, key=lambda x: x.created_at):
            if log.trade_id:
                if 'открыта' in log.message.lower():
                    open_trades[log.trade_id] = log.created_at
                elif 'закрыта' in log.message.lower() and log.trade_id in open_trades:
                    hold_time = (log.created_at - open_trades[log.trade_id]).total_seconds() / 3600
                    hold_times.append(hold_time)
                    del open_trades[log.trade_id]
        
        return hold_times
    
    def _group_by_field(self, logs: List[TradingLog], field: str) -> Dict[str, Dict]:
        """Группирует логи по полю"""
        grouped = defaultdict(lambda: {'count': 0, 'total_profit': 0})
        
        for log in logs:
            value = getattr(log, field)
            if value and log.context and 'profit' in log.context:
                grouped[value]['count'] += 1
                grouped[value]['total_profit'] += log.context['profit']
        
        return {k: v for k, v in grouped.items() if k is not None}
    
    def _get_hourly_distribution(self, logs: List[TradingLog]) -> Dict[int, int]:
        """Получает распределение по часам"""
        distribution = defaultdict(int)
        
        for log in logs:
            distribution[log.created_at.hour] += 1
        
        return dict(distribution)
    
    def _calculate_weekend_activity(self, logs: List[TradingLog]) -> Dict[str, float]:
        """Рассчитывает активность в выходные"""
        weekend_logs = [log for log in logs if log.created_at.weekday() >= 5]
        weekday_logs = [log for log in logs if log.created_at.weekday() < 5]
        
        return {
            'weekend_percentage': len(weekend_logs) / len(logs) * 100 if logs else 0,
            'weekend_avg_per_day': len(weekend_logs) / 2,  # Суббота и воскресенье
            'weekday_avg_per_day': len(weekday_logs) / 5   # Понедельник-пятница
        }
    
    def _generate_recommendations(self, analytics: Dict[str, Any]) -> List[Dict[str, str]]:
        """Генерирует рекомендации на основе аналитики"""
        recommendations = []
        
        # Анализ win rate
        if analytics['trades'].get('win_rate', 0) < 0.4:
            recommendations.append({
                'type': 'critical',
                'area': 'trading',
                'message': 'Низкий win rate (<40%). Рекомендуется пересмотреть критерии входа в сделки.',
                'action': 'Увеличить минимальную уверенность для входа в сделку'
            })
        
        # Анализ profit factor
        profit_factor = analytics['trades'].get('profit_factor', 0)
        if 0 < profit_factor < 1.2:
            recommendations.append({
                'type': 'warning',
                'area': 'risk_management',
                'message': f'Низкий profit factor ({profit_factor:.2f}). Средний убыток превышает среднюю прибыль.',
                'action': 'Пересмотреть уровни Take Profit и Stop Loss'
            })
        
        # Анализ времени удержания
        avg_hold_time = analytics['trades'].get('avg_hold_time_hours', 0)
        if avg_hold_time > 24:
            recommendations.append({
                'type': 'info',
                'area': 'strategy',
                'message': f'Долгое время удержания позиций ({avg_hold_time:.1f} часов).',
                'action': 'Рассмотреть возможность более активного управления позициями'
            })
        
        # Анализ ошибок
        error_rate = analytics['errors'].get('total', 0)
        if error_rate > 10:
            most_common_error = analytics['errors'].get('most_common', 'unknown')
            recommendations.append({
                'type': 'warning',
                'area': 'system',
                'message': f'Высокое количество ошибок ({error_rate}). Наиболее частая: {most_common_error}.',
                'action': 'Проверить стабильность подключения и корректность API настроек'
            })
        
        # Анализ временных паттернов
        if analytics['patterns']['time_patterns'].get('best_profit_hours'):
            best_hours = analytics['patterns']['time_patterns']['best_profit_hours'][:3]
            hours_str = ', '.join([f"{h[0]}:00" for h in best_hours])
            recommendations.append({
                'type': 'info',
                'area': 'timing',
                'message': f'Наиболее прибыльные часы: {hours_str}.',
                'action': 'Сконцентрировать торговую активность в эти периоды'
            })
        
        # Анализ корреляций
        signal_correlation = analytics['patterns']['correlation_patterns'].get('signals_to_profit', 0)
        if signal_correlation < -0.3:
            recommendations.append({
                'type': 'critical',
                'area': 'signals',
                'message': 'Отрицательная корреляция между количеством сигналов и прибылью.',
                'action': 'Повысить качество фильтрации сигналов, возможно, система генерирует слишком много ложных сигналов'
            })
        
        return recommendations
    
    async def generate_performance_report(self, period_days: int = 7) -> Dict[str, Any]:
        """Генерирует отчет о производительности"""
        # Собираем аналитику по всем символам и стратегиям
        overall_analytics = await self.collect_trading_analytics(period_days=period_days)
        
        # Собираем данные по отдельным символам
        db = SessionLocal()
        try:
            # Получаем активные символы
            active_symbols = db.query(TradingLog.symbol).filter(
                TradingLog.symbol.isnot(None)
            ).distinct().all()
            
            symbol_analytics = {}
            for (symbol,) in active_symbols:
                symbol_analytics[symbol] = await self.collect_trading_analytics(
                    symbol=symbol, 
                    period_days=period_days
                )
            
            # Формируем отчет
            report = {
                'generated_at': datetime.utcnow().isoformat(),
                'period_days': period_days,
                'overall': overall_analytics,
                'by_symbol': symbol_analytics,
                'top_performers': self._get_top_performers(symbol_analytics),
                'areas_of_improvement': self._identify_improvement_areas(overall_analytics),
                'market_insights': await self._get_market_insights(db)
            }
            
            return report
            
        finally:
            db.close()
    
    def _get_top_performers(self, symbol_analytics: Dict[str, Dict]) -> Dict[str, List]:
        """Определяет топ исполнителей"""
        # Сортируем по прибыли
        by_profit = sorted(
            [(symbol, data['trades'].get('total_profit', 0)) 
             for symbol, data in symbol_analytics.items()],
            key=lambda x: x[1],
            reverse=True
        )
        
        # Сортируем по win rate
        by_winrate = sorted(
            [(symbol, data['trades'].get('win_rate', 0)) 
             for symbol, data in symbol_analytics.items()
             if data['trades'].get('total', 0) >= 5],  # Минимум 5 сделок
            key=lambda x: x[1],
            reverse=True
        )
        
        return {
            'by_profit': by_profit[:5],
            'by_winrate': by_winrate[:5]
        }
    
    def _identify_improvement_areas(self, analytics: Dict[str, Any]) -> List[Dict]:
        """Определяет области для улучшения"""
        areas = []
        
        # Проверяем различные метрики
        trades = analytics.get('trades', {})
        
        if trades.get('avg_loss', 0) > trades.get('avg_profit', 0):
            areas.append({
                'area': 'Risk Management',
                'issue': 'Средний убыток превышает среднюю прибыль',
                'impact': 'high',
                'suggestion': 'Пересмотреть соотношение Risk/Reward'
            })
        
        if trades.get('active', 0) > 10:
            areas.append({
                'area': 'Position Management',
                'issue': f"Слишком много открытых позиций ({trades['active']})",
                'impact': 'medium',
                'suggestion': 'Установить лимит на количество одновременных позиций'
            })
        
        errors = analytics.get('errors', {})
        if errors.get('total', 0) > 0:
            areas.append({
                'area': 'System Stability',
                'issue': f"Обнаружено {errors['total']} ошибок",
                'impact': 'high',
                'suggestion': 'Проанализировать и устранить источники ошибок'
            })
        
        return areas
    
    async def _get_market_insights(self, db: Session) -> Dict[str, Any]:
        """Получает инсайты о рынке"""
        # Здесь можно добавить анализ рыночных условий
        # Пока возвращаем базовую информацию
        return {
            'current_market_condition': 'normal',
            'volatility_level': 'medium',
            'recommended_strategies': ['momentum', 'mean_reversion'],
            'risk_level': 'moderate'
        }


# Создаем глобальный экземпляр
analytics_collector = AnalyticsCollector()