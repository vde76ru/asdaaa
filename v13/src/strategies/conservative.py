"""
Консервативная стратегия для безопасной торговли
Путь: src/strategies/conservative.py
"""
import pandas as pd
import numpy as np
import ta
from typing import Dict
import logging

from .base import BaseStrategy, TradingSignal

logger = logging.getLogger(__name__)

class ConservativeStrategy(BaseStrategy):
    """
    Консервативная стратегия с жесткими критериями входа
    Минимизирует риски за счет снижения количества сделок
    """
    
    def __init__(self):
        super().__init__("conservative")
        self.min_confidence = 0.75  # Высокий порог уверенности
        self.min_risk_reward = 2.5  # Минимум 1:2.5
        self.max_risk_percent = 1.0  # Максимум 1% риска на сделку
    
    async def analyze(self, df: pd.DataFrame, symbol: str) -> TradingSignal:
        """Консервативный анализ с множественными подтверждениями"""
        
        if not self.validate_dataframe(df) or len(df) < 200:
            return TradingSignal('WAIT', 0, 0, reason='Недостаточно данных')
        
        try:
            # Рассчитываем индикаторы
            indicators = self._calculate_indicators(df)
            
            # Проверяем рыночные условия
            market_condition = self._check_market_conditions(indicators, df)
            
            if market_condition == 'UNSUITABLE':
                return TradingSignal('WAIT', 0, 0, reason='Неподходящие рыночные условия')
            
            # Ищем сигналы входа
            entry_signal = self._find_entry_signal(indicators, market_condition)
            
            return entry_signal
            
        except Exception as e:
            logger.error(f"Ошибка консервативного анализа {symbol}: {e}")
            return TradingSignal('WAIT', 0, 0, reason='Ошибка анализа')
    
    def _calculate_indicators(self, df: pd.DataFrame) -> Dict:
        """Расчет надежных индикаторов"""
        indicators = {}
        
        # Скользящие средние для определения тренда
        indicators['sma_50'] = df['close'].rolling(window=50).mean().iloc[-1]
        indicators['sma_200'] = df['close'].rolling(window=200).mean().iloc[-1]
        
        # RSI для определения перекупленности/перепроданности
        indicators['rsi'] = ta.momentum.rsi(df['close'], window=14).iloc[-1]
        
        # ATR для волатильности
        atr = ta.volatility.AverageTrueRange(df['high'], df['low'], df['close'])
        indicators['atr'] = atr.average_true_range().iloc[-1]
        indicators['atr_percent'] = (indicators['atr'] / df['close'].iloc[-1]) * 100
        
        # Объемный анализ
        indicators['volume_sma'] = df['volume'].rolling(window=50).mean().iloc[-1]
        indicators['volume_trend'] = df['volume'].rolling(window=10).mean().iloc[-1] / indicators['volume_sma']
        
        # Поддержка и сопротивление
        indicators['resistance'] = df['high'].rolling(window=20).max().iloc[-1]
        indicators['support'] = df['low'].rolling(window=20).min().iloc[-1]
        
        # Текущая цена
        indicators['current_price'] = df['close'].iloc[-1]
        
        return indicators
    
    def _check_market_conditions(self, indicators: Dict, df: pd.DataFrame) -> str:
        """Проверка рыночных условий"""
        
        # 1. Проверяем волатильность - не торгуем при экстремальной волатильности
        if indicators['atr_percent'] > 5:  # Волатильность > 5%
            return 'UNSUITABLE'
        
        # 2. Проверяем объем - должен быть стабильный
        if indicators['volume_trend'] < 0.5 or indicators['volume_trend'] > 3:
            return 'UNSUITABLE'
        
        # 3. Определяем тренд
        if indicators['current_price'] > indicators['sma_50'] > indicators['sma_200']:
            return 'UPTREND'
        elif indicators['current_price'] < indicators['sma_50'] < indicators['sma_200']:
            return 'DOWNTREND'
        else:
            return 'SIDEWAYS'
    
    def _find_entry_signal(self, indicators: Dict, market_condition: str) -> TradingSignal:
        """Поиск консервативных точек входа"""
        
        current_price = indicators['current_price']
        atr = indicators['atr']
        
        # Сигнал покупки только в восходящем тренде
        if market_condition == 'UPTREND':
            # Условия для покупки:
            # 1. RSI вышел из зоны перепроданности (30-40)
            # 2. Цена выше SMA50
            # 3. Откат к поддержке завершен
            
            if (30 < indicators['rsi'] < 40 and
                current_price > indicators['sma_50'] and
                current_price < indicators['sma_50'] * 1.02):  # Близко к SMA50
                
                # Консервативные уровни
                stop_loss = indicators['support']  # Стоп под уровнем поддержки
                take_profit = current_price + (current_price - stop_loss) * 3  # R:R = 1:3
                
                # Проверка риска
                risk_percent = ((current_price - stop_loss) / current_price) * 100
                if risk_percent > self.max_risk_percent:
                    stop_loss = current_price * (1 - self.max_risk_percent / 100)
                
                risk_reward = self.calculate_risk_reward(current_price, stop_loss, take_profit)
                
                if risk_reward >= self.min_risk_reward:
                    return TradingSignal(
                        action='BUY',
                        confidence=0.8,
                        price=current_price,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        reason='Консервативная покупка: откат в восходящем тренде',
                        risk_reward_ratio=risk_reward,
                        indicators=indicators
                    )
        
        # Сигнал продажи только в нисходящем тренде
        elif market_condition == 'DOWNTREND':
            if (60 < indicators['rsi'] < 70 and
                current_price < indicators['sma_50'] and
                current_price > indicators['sma_50'] * 0.98):  # Близко к SMA50
                
                stop_loss = indicators['resistance']
                take_profit = current_price - (stop_loss - current_price) * 3
                
                risk_percent = ((stop_loss - current_price) / current_price) * 100
                if risk_percent > self.max_risk_percent:
                    stop_loss = current_price * (1 + self.max_risk_percent / 100)
                
                risk_reward = self.calculate_risk_reward(current_price, stop_loss, take_profit)
                
                if risk_reward >= self.min_risk_reward:
                    return TradingSignal(
                        action='SELL',
                        confidence=0.8,
                        price=current_price,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        reason='Консервативная продажа: откат в нисходящем тренде',
                        risk_reward_ratio=risk_reward,
                        indicators=indicators
                    )
        
        return TradingSignal(
            action='WAIT',
            confidence=0,
            price=current_price,
            reason=f'Ждем подходящих условий в {market_condition}'
        )
