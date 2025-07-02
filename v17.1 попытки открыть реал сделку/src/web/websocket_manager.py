"""
WebSocket Manager - Упрощенная версия для Flask-SocketIO
Путь: src/web/websocket_manager.py
"""
import logging
import json
from datetime import datetime
from typing import Dict, Set, Any, Optional
from flask_socketio import SocketIO, emit, disconnect
from flask import request
import threading
from ..bot.state_manager import state_manager

logger = logging.getLogger(__name__)

class WebSocketManager:
    """
    Упрощенный менеджер WebSocket соединений
    Работает с Flask-SocketIO без asyncio конфликтов
    """
    
    def __init__(self, socketio: SocketIO):
        self.socketio = socketio
        self.active_connections: Set[str] = set()
        self.subscriptions: Dict[str, Set[str]] = {}  # channel -> set of sids
        self._lock = threading.Lock()
        
        # Статистика
        self.stats = {
            'total_connections': 0,
            'active_connections': 0,
            'messages_sent': 0,
            'start_time': datetime.utcnow()
        }
        
        self._setup_handlers()
        
        # ✅ ИСПРАВЛЕННАЯ ИНТЕГРАЦИЯ: Подписка на изменения состояния бота в __init__
        try:
            state_manager.add_observer(self._on_bot_state_changed)
            logger.info("✅ WebSocketManager интегрирован с StateManager")
        except Exception as e:
            logger.error(f"❌ Ошибка интеграции с StateManager: {e}")
        
        logger.info("✅ WebSocketManager инициализирован")
    
    def _setup_handlers(self):
        """Настройка обработчиков SocketIO"""
        
        @self.socketio.on('connect')
        def handle_connect():
            """Обработка подключения"""
            sid = request.sid
            with self._lock:
                self.active_connections.add(sid)
                self.stats['total_connections'] += 1
                self.stats['active_connections'] = len(self.active_connections)
            
            logger.info(f"🔌 WebSocket подключен: {sid}")
            
            # Отправляем начальное сообщение
            emit('connected', {
                'status': 'connected',
                'timestamp': datetime.utcnow().isoformat()
            })
            
            # ✅ НОВОЕ: Отправляем актуальное состояние при подключении
            try:
                current_status = state_manager.get_status_api()
                emit('bot_status', current_status)
            except Exception as e:
                logger.error(f"❌ Ошибка отправки начального статуса: {e}")
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            """Обработка отключения"""
            sid = request.sid
            with self._lock:
                self.active_connections.discard(sid)
                # Удаляем из всех подписок
                for channel_sids in self.subscriptions.values():
                    channel_sids.discard(sid)
                self.stats['active_connections'] = len(self.active_connections)
            
            logger.info(f"🔌 WebSocket отключен: {sid}")
        
        @self.socketio.on('subscribe')
        def handle_subscribe(data):
            """Подписка на канал"""
            sid = request.sid
            channel = data.get('channel')
            
            if channel:
                with self._lock:
                    if channel not in self.subscriptions:
                        self.subscriptions[channel] = set()
                    self.subscriptions[channel].add(sid)
                
                emit('subscribed', {'channel': channel})
                logger.info(f"📡 {sid} подписался на {channel}")
        
        @self.socketio.on('unsubscribe')
        def handle_unsubscribe(data):
            """Отписка от канала"""
            sid = request.sid
            channel = data.get('channel')
            
            if channel:
                with self._lock:
                    if channel in self.subscriptions:
                        self.subscriptions[channel].discard(sid)
                
                emit('unsubscribed', {'channel': channel})
                logger.info(f"📡 {sid} отписался от {channel}")
    
    def broadcast_to_all(self, event: str, data: dict):
        """Отправка сообщения всем подключенным клиентам"""
        try:
            self.socketio.emit(event, data)
            self.stats['messages_sent'] += 1
            logger.debug(f"📢 Отправлено всем: {event}")
        except Exception as e:
            logger.error(f"Ошибка broadcast: {e}")
    
    def broadcast_to_channel(self, channel: str, event: str, data: dict):
        """Отправка сообщения подписчикам канала"""
        try:
            with self._lock:
                channel_sids = self.subscriptions.get(channel, set())
            
            for sid in channel_sids:
                self.socketio.emit(event, data, room=sid)
            
            self.stats['messages_sent'] += len(channel_sids)
            logger.debug(f"📢 Отправлено в канал {channel}: {event}")
        except Exception as e:
            logger.error(f"Ошибка broadcast to channel: {e}")
    
    def get_stats(self) -> dict:
        """Получение статистики"""
        with self._lock:
            return {
                **self.stats,
                'active_connections': len(self.active_connections),
                'channels': len(self.subscriptions),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    def start(self):
        """Запуск менеджера (для совместимости)"""
        logger.info("✅ WebSocketManager запущен")
    
    def stop(self):
        """Остановка менеджера"""
        with self._lock:
            self.active_connections.clear()
            self.subscriptions.clear()
        logger.info("🛑 WebSocketManager остановлен")
        
    def _on_bot_state_changed(self, bot_state):
        """Автоматическое уведомление WebSocket клиентов при изменении состояния бота"""
        try:
            self.broadcast_to_all('bot_status', bot_state.to_api_dict())
            logger.debug("📡 Состояние бота транслировано через WebSocket")
        except Exception as e:
            logger.error(f"❌ Ошибка WebSocket трансляции: {e}")

def create_websocket_manager(socketio: SocketIO, bot_manager=None) -> WebSocketManager:
    """Фабричная функция для создания WebSocket менеджера"""
    return WebSocketManager(socketio)