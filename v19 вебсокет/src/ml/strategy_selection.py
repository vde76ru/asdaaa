"""
Модуль автоматического выбора стратегий
Файл: src/ml/strategy_selection.py
"""
import logging
from typing import Dict, List, Optional
import numpy as np
from datetime import datetime

logger = logging.getLogger(__name__)

class AutoStrategySelector:
    """Автоматический выбор оптимальной стратегии"""
    
    def __init__(self):
        self.strategy_performance = {}
        self.market_conditions = {}
        logger.info("✅ AutoStrategySelector инициализирован")
    
    def analyze_market_conditions(self, symbol: str, data: Dict) -> str:
        """Анализ рыночных условий"""
        try:
            # Простая логика определения рыночных условий
            if 'volatility' in data:
                volatility = data['volatility']
                if volatility > 0.03:
                    return 'high_volatility'
                elif volatility < 0.01:
                    return 'low_volatility'
            return 'normal'
        except Exception as e:
            logger.error(f"Ошибка анализа рынка: {e}")
            return 'unknown'
    
    def select_best_strategy(self, symbol: str, available_strategies: List[str]) -> str:
        """Выбор лучшей стратегии"""
        try:
            # Простая логика выбора
            market_condition = self.market_conditions.get(symbol, 'normal')
            
            strategy_map = {
                'high_volatility': 'scalping',
                'low_volatility': 'mean_reversion',
                'normal': 'multi_indicator'
            }
            
            selected = strategy_map.get(market_condition, 'multi_indicator')
            
            if selected in available_strategies:
                return selected
            
            return available_strategies[0] if available_strategies else 'multi_indicator'
            
        except Exception as e:
            logger.error(f"Ошибка выбора стратегии: {e}")
            return 'multi_indicator'
    
    def update_performance(self, strategy: str, symbol: str, profit: float):
        """Обновление производительности стратегии"""
        key = f"{strategy}_{symbol}"
        if key not in self.strategy_performance:
            self.strategy_performance[key] = []
        self.strategy_performance[key].append(profit)
    
    def get_strategy_recommendations(self, symbol: str) -> List[str]:
        """Получение рекомендаций по стратегиям"""
        return ['multi_indicator', 'momentum', 'mean_reversion', 'scalping']

# Экспорт
__all__ = ['AutoStrategySelector']