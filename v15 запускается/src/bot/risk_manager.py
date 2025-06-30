"""
Модуль управления рисками
Путь: /var/www/www-root/data/www/systemetech.ru/src/bot/risk_manager.py
"""
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta

from ..core.unified_config import unified_config as config
from ..core.models import Signal, Trade

logger = logging.getLogger(__name__)

class RiskManager:
    """Управление рисками"""
    
    def __init__(self):
        self.max_positions = config.MAX_POSITIONS
        self.max_daily_loss_percent = 5.0  # Максимальный дневной убыток 5%
        self.max_position_size_percent = config.MAX_POSITION_SIZE_PERCENT
        self.min_risk_reward_ratio = config.MIN_RISK_REWARD_RATIO
        
        # Статистика
        self.daily_stats = {
            'trades': 0,
            'wins': 0,
            'losses': 0,
            'total_profit': 0,
            'last_reset': datetime.now().date()
        }
        
    def check_signal(self, signal: Signal, open_positions: Dict[str, Trade], current_balance: float) -> bool:
        """Проверка сигнала на соответствие правилам риск-менеджмента"""
        
        # Сбрасываем дневную статистику если новый день
        self._reset_daily_stats_if_needed()
        
        # 1. Проверка количества открытых позиций
        if len(open_positions) >= self.max_positions:
            logger.info(f"🚫 Достигнут лимит открытых позиций: {len(open_positions)}/{self.max_positions}")
            return False
        
        # 2. Проверка дневного лимита сделок
        if self.daily_stats['trades'] >= config.MAX_DAILY_TRADES:
            logger.info(f"🚫 Достигнут дневной лимит сделок: {self.daily_stats['trades']}/{config.MAX_DAILY_TRADES}")
            return False
        
        # 3. Проверка дневного убытка
        daily_loss_percent = (self.daily_stats['total_profit'] / current_balance) * 100
        if daily_loss_percent < -self.max_daily_loss_percent:
            logger.info(f"🚫 Достигнут дневной лимит убытков: {daily_loss_percent:.2f}%")
            return False
        
        # 4. Проверка риск/прибыль
        if signal.stop_loss and signal.take_profit:
            risk = abs(signal.price - signal.stop_loss)
            reward = abs(signal.take_profit - signal.price)
            
            if risk > 0:
                risk_reward_ratio = reward / risk
                if risk_reward_ratio < self.min_risk_reward_ratio:
                    logger.info(f"🚫 Низкое соотношение риск/прибыль: {risk_reward_ratio:.2f}")
                    return False
        
        # 5. Проверка на дублирование позиции
        if signal.symbol in open_positions:
            logger.info(f"🚫 Позиция по {signal.symbol} уже открыта")
            return False
        
        # 6. Проверка минимальной уверенности
        if signal.confidence < 0.6:
            logger.info(f"🚫 Низкая уверенность в сигнале: {signal.confidence:.2f}")
            return False
        
        logger.info(f"✅ Сигнал прошел проверку риск-менеджмента")
        return True
    
    def update_statistics(self, result: str, profit: float):
        """Обновление статистики"""
        self.daily_stats['trades'] += 1
        
        if result == 'win':
            self.daily_stats['wins'] += 1
        else:
            self.daily_stats['losses'] += 1
        
        self.daily_stats['total_profit'] += profit
        
        win_rate = (self.daily_stats['wins'] / self.daily_stats['trades']) * 100 if self.daily_stats['trades'] > 0 else 0
        
        logger.info(f"📊 Статистика дня: Сделок: {self.daily_stats['trades']}, "
                   f"Win rate: {win_rate:.1f}%, P&L: ${self.daily_stats['total_profit']:.2f}")
    
    def _reset_daily_stats_if_needed(self):
        """Сброс дневной статистики если новый день"""
        today = datetime.now().date()
        if today != self.daily_stats['last_reset']:
            logger.info("📅 Новый торговый день - сброс статистики")
            self.daily_stats = {
                'trades': 0,
                'wins': 0,
                'losses': 0,
                'total_profit': 0,
                'last_reset': today
            }
    
    def calculate_position_size(self, signal: Signal, balance: float) -> float:
        """Расчет размера позиции с учетом риска"""
        # Базовый размер позиции
        position_size = balance * (self.max_position_size_percent / 100)
        
        # Корректировка на основе уверенности
        position_size *= signal.confidence
        
        # Корректировка на основе текущей статистики
        if self.daily_stats['trades'] > 5:
            win_rate = self.daily_stats['wins'] / self.daily_stats['trades']
            if win_rate < 0.3:  # Если win rate < 30%, уменьшаем размер
                position_size *= 0.5
        
        # Не больше максимального размера
        max_size = balance * (self.max_position_size_percent / 100)
        position_size = min(position_size, max_size)
        
        return position_size