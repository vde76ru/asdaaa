"""Модель состояния бота"""
from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime
from .base_models import Base, TimestampMixin

class BotState(Base, TimestampMixin):
    __tablename__ = 'bot_state'
    
    id = Column(Integer, primary_key=True)
    is_running = Column(Boolean, default=False)
    current_strategy = Column(String(50))
    last_signal = Column(String(10))
    last_trade_time = Column(DateTime)
    total_trades = Column(Integer, default=0)
    profitable_trades = Column(Integer, default=0)
    total_profit = Column(Float, default=0.0)
    current_balance = Column(Float, default=0.0)
    
    def to_dict(self):
        return {
            'id': self.id,
            'is_running': self.is_running,
            'current_strategy': self.current_strategy,
            'last_signal': self.last_signal,
            'last_trade_time': self.last_trade_time.isoformat() if self.last_trade_time else None,
            'total_trades': self.total_trades,
            'profitable_trades': self.profitable_trades,
            'total_profit': self.total_profit,
            'current_balance': self.current_balance
        }
