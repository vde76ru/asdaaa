"""
Единые типы данных для всей системы
Файл: src/common/types.py
"""
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum

class SignalAction(Enum):
    """Действия сигнала"""
    BUY = "BUY"
    SELL = "SELL"
    WAIT = "WAIT"
    
class OrderSide(Enum):
    """Стороны ордера для Bybit"""
    BUY = "Buy"
    SELL = "Sell"

@dataclass
class UnifiedTradingSignal:
    """
    Единый формат торгового сигнала для всей системы
    Объединяет требования strategies и bybit_integration
    """
    # Основные поля
    symbol: str
    action: SignalAction  # Для стратегий
    confidence: float
    price: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Поля для стратегий
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    reason: str = ""
    risk_reward_ratio: Optional[float] = None
    indicators: Optional[Dict[str, Any]] = None
    ml_prediction: Optional[Dict[str, Any]] = None
    source: str = "technical"
    strategy: str = "unknown"
    
    # Поля для Bybit
    side: Optional[OrderSide] = None  # Автоматически вычисляется
    signal_type: str = "entry"  # "entry", "exit", "tp", "sl"
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Автоматическая конвертация и валидация после создания"""
        # Конвертируем action в side для Bybit
        if self.side is None and self.action:
            if isinstance(self.action, str):
                self.action = SignalAction(self.action.upper())
            
            if self.action == SignalAction.BUY:
                self.side = OrderSide.BUY
            elif self.action == SignalAction.SELL:
                self.side = OrderSide.SELL
        
        # Валидация
        if self.confidence < 0 or self.confidence > 1:
            raise ValueError(f"Confidence должна быть от 0 до 1, получено: {self.confidence}")
        
        if self.price <= 0:
            raise ValueError(f"Price должна быть положительной, получено: {self.price}")
    
    @property
    def side_str(self) -> str:
        """Получить side как строку для Bybit API"""
        return self.side.value if self.side else ""
    
    @property
    def action_str(self) -> str:
        """Получить action как строку"""
        return self.action.value if self.action else "WAIT"
    
    def to_strategy_format(self) -> Dict[str, Any]:
        """Конвертация в формат для стратегий"""
        return {
            'symbol': self.symbol,
            'action': self.action_str,
            'confidence': self.confidence,
            'price': self.price,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'reason': self.reason,
            'risk_reward_ratio': self.risk_reward_ratio,
            'indicators': self.indicators,
            'source': self.source
        }
    
    def to_bybit_format(self) -> Dict[str, Any]:
        """Конвертация в формат для Bybit"""
        return {
            'symbol': self.symbol,
            'side': self.side_str,
            'signal_type': self.signal_type,
            'price': self.price,
            'confidence': self.confidence,
            'timestamp': self.timestamp,
            'metadata': self.metadata or {
                'stop_loss': self.stop_loss,
                'take_profit': self.take_profit,
                'strategy': self.strategy,
                'reason': self.reason
            }
        }

# Для обратной совместимости
TradingSignal = UnifiedTradingSignal