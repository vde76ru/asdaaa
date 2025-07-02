"""
Централизованный менеджер состояний торгового бота
Файл: src/bot/state_manager.py

Назначение: Единый источник истины для состояния торгового бота
Решает проблему: Десинхронизация между BotController и BotManager
Архитектура: Thread-safe singleton с Observer pattern
"""

import threading
import logging
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)

class BotStatus(Enum):
    """Возможные состояния торгового бота"""
    STOPPED = "stopped"
    STARTING = "starting" 
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"

@dataclass
class BotState:
    """Структура состояния бота для thread-safe операций"""
    status: BotStatus
    is_running: bool
    active_pairs: List[str]
    open_positions: int
    start_time: Optional[datetime] = None
    last_update: Optional[datetime] = None
    error_message: Optional[str] = None
    strategy: str = "auto"
    
    def to_api_dict(self) -> Dict[str, Any]:
        """Преобразование в формат API ответа"""
        return {
            'status': self.status.value,
            'is_running': self.is_running,
            'active_pairs': self.active_pairs,
            'open_positions': self.open_positions,
            'positions_details': {},
            'statistics': {
                'start_time': self.start_time.isoformat() if self.start_time else None,
                'uptime': self._calculate_uptime(),
                'cycles_count': 0,
                'trades_today': 0
            },
            'process_info': {},
            'config': {
                'mode': 'TESTNET',
                'max_positions': 1,
                'human_mode': True,
                'max_daily_trades': 10
            },
            'timestamp': datetime.utcnow().isoformat(),
            'error_message': self.error_message
        }
    
    def _calculate_uptime(self) -> Optional[str]:
        """Расчет времени работы бота"""
        if not self.start_time or not self.is_running:
            return None
        
        uptime = datetime.utcnow() - self.start_time
        hours, remainder = divmod(int(uptime.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

class StateManager:
    """
    Централизованный менеджер состояний с thread-safe операциями
    
    Реализует паттерн Singleton для обеспечения единого источника истины
    Предоставляет Observer pattern для уведомления подписчиков
    """
    
    _instance = None
    _instance_lock = threading.Lock()
    
    def __new__(cls):
        """Thread-safe реализация Singleton"""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Инициализация StateManager (выполняется только один раз)"""
        if getattr(self, '_initialized', False):
            return
        
        self._state_lock = threading.RLock()
        self._state = BotState(
            status=BotStatus.STOPPED,
            is_running=False,
            active_pairs=[],
            open_positions=0,
            strategy="auto"
        )
        
        self._observers: List[Callable] = []
        self._operation_history: List[Dict] = []
        self._initialized = True
        
        logger.info("✅ StateManager инициализирован как Singleton")
    
    def get_state(self) -> BotState:
        """Получение текущего состояния (thread-safe)"""
        with self._state_lock:
            self._state.last_update = datetime.utcnow()
            return self._state
    
    def get_status_api(self) -> Dict[str, Any]:
        """Получение статуса в формате API"""
        state = self.get_state()
        return state.to_api_dict()
    
    def can_start(self) -> tuple[bool, str]:
        """Проверка возможности запуска бота"""
        with self._state_lock:
            if self._state.status in [BotStatus.RUNNING, BotStatus.STARTING]:
                return False, f"Бот уже в состоянии: {self._state.status.value}"
            
            if self._state.status == BotStatus.STOPPING:
                return False, "Бот находится в процессе остановки"
            
            return True, "Запуск разрешен"
    
    def can_stop(self) -> tuple[bool, str]:
        """Проверка возможности остановки бота"""
        with self._state_lock:
            if self._state.status in [BotStatus.STOPPED, BotStatus.STOPPING]:
                return False, f"Бот уже в состоянии: {self._state.status.value}"
            
            if self._state.status == BotStatus.ERROR:
                return True, "Принудительная остановка из состояния ошибки"
            
            return True, "Остановка разрешена"
    
    def transition_to_starting(self, pairs: List[str], strategy: str = "auto") -> bool:
        """Переход в состояние запуска"""
        can_start, reason = self.can_start()
        if not can_start:
            logger.warning(f"Переход к запуску отклонен: {reason}")
            return False
        
        with self._state_lock:
            self._state.status = BotStatus.STARTING
            self._state.is_running = False
            self._state.active_pairs = pairs.copy()
            self._state.strategy = strategy
            self._state.error_message = None
            self._state.last_update = datetime.utcnow()
            
            self._record_operation("transition_to_starting", {
                'pairs': pairs,
                'strategy': strategy
            })
            
            self._notify_observers()
            
        logger.info(f"🚀 Переход к запуску: пары={pairs}, стратегия={strategy}")
        return True
    
    def transition_to_running(self) -> bool:
        """Переход в состояние работы"""
        with self._state_lock:
            if self._state.status != BotStatus.STARTING:
                logger.error(f"Некорректный переход к running из {self._state.status}")
                return False
            
            self._state.status = BotStatus.RUNNING
            self._state.is_running = True
            self._state.start_time = datetime.utcnow()
            self._state.last_update = datetime.utcnow()
            
            self._record_operation("transition_to_running", {})
            self._notify_observers()
            
        logger.info("✅ Бот перешел в состояние работы")
        return True
    
    def transition_to_stopping(self) -> bool:
        """Переход в состояние остановки"""
        can_stop, reason = self.can_stop()
        if not can_stop:
            logger.warning(f"Переход к остановке отклонен: {reason}")
            return False
        
        with self._state_lock:
            self._state.status = BotStatus.STOPPING
            self._state.is_running = False
            self._state.last_update = datetime.utcnow()
            
            self._record_operation("transition_to_stopping", {})
            self._notify_observers()
            
        logger.info("🛑 Переход к остановке")
        return True
    
    def transition_to_stopped(self) -> bool:
        """Переход в состояние остановки"""
        with self._state_lock:
            self._state.status = BotStatus.STOPPED
            self._state.is_running = False
            self._state.active_pairs = []
            self._state.open_positions = 0
            self._state.start_time = None
            self._state.error_message = None
            self._state.last_update = datetime.utcnow()
            
            self._record_operation("transition_to_stopped", {})
            self._notify_observers()
            
        logger.info("✅ Бот остановлен")
        return True
    
    def transition_to_error(self, error_message: str) -> bool:
        """Переход в состояние ошибки"""
        with self._state_lock:
            self._state.status = BotStatus.ERROR
            self._state.is_running = False
            self._state.error_message = error_message
            self._state.last_update = datetime.utcnow()
            
            self._record_operation("transition_to_error", {
                'error_message': error_message
            })
            self._notify_observers()
            
        logger.error(f"❌ Бот перешел в состояние ошибки: {error_message}")
        return True
    
    def force_reset(self) -> None:
        """Принудительный сброс состояния (аварийная процедура)"""
        with self._state_lock:
            self._state = BotState(
                status=BotStatus.STOPPED,
                is_running=False,
                active_pairs=[],
                open_positions=0,
                strategy="auto"
            )
            
            self._record_operation("force_reset", {})
            self._notify_observers()
            
        logger.warning("🔥 Выполнен принудительный сброс состояния")
    
    def add_observer(self, callback: Callable) -> None:
        """Добавление подписчика на изменения состояния"""
        with self._state_lock:
            self._observers.append(callback)
        logger.debug(f"Добавлен observer, всего: {len(self._observers)}")
    
    def remove_observer(self, callback: Callable) -> None:
        """Удаление подписчика"""
        with self._state_lock:
            if callback in self._observers:
                self._observers.remove(callback)
        logger.debug(f"Удален observer, осталось: {len(self._observers)}")
    
    def get_operation_history(self, limit: int = 10) -> List[Dict]:
        """Получение истории операций для диагностики"""
        with self._state_lock:
            return self._operation_history[-limit:]
    
    def _notify_observers(self) -> None:
        """Уведомление всех подписчиков об изменении состояния"""
        for callback in self._observers.copy():  # Копия для thread-safety
            try:
                callback(self._state)
            except Exception as e:
                logger.error(f"Ошибка уведомления observer: {e}")
                # Удаляем неработающий observer
                with self._state_lock:
                    if callback in self._observers:
                        self._observers.remove(callback)
    
    def _record_operation(self, operation: str, details: Dict) -> None:
        """Запись операции в историю для диагностики"""
        record = {
            'timestamp': datetime.utcnow().isoformat(),
            'operation': operation,
            'details': details,
            'state_before': self._state.status.value if hasattr(self._state, 'status') else 'unknown'
        }
        
        # Ограничиваем размер истории
        if len(self._operation_history) >= 100:
            self._operation_history = self._operation_history[-50:]
        
        self._operation_history.append(record)

# Глобальный экземпляр Singleton
state_manager = StateManager()