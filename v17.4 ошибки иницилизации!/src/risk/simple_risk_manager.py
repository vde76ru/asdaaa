"""
Простой риск-менеджер без TA-Lib
"""
import logging
from typing import Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class SimpleRiskManager:
    """Упрощенный риск-менеджер без зависимости от TA-Lib"""
    
    def __init__(self):
        self.max_position_size = 0.05  # 5% от капитала
        self.max_daily_loss = 0.02     # 2% максимальный убыток в день
        self.stop_loss_percent = 0.02  # 2% стоп-лосс
        
    def calculate_position_size(self, balance: float, risk_amount: float) -> float:
        """Расчет размера позиции"""
        max_position = balance * self.max_position_size
        return min(max_position, risk_amount)
    
    def check_daily_loss_limit(self, daily_loss: float, balance: float) -> bool:
        """Проверка дневного лимита убытков"""
        max_loss = balance * self.max_daily_loss
        return abs(daily_loss) < max_loss