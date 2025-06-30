"""
WebSocket менеджер для обновлений в реальном времени
"""
import asyncio
import sys
import json
import logging
from typing import Dict, Any, List, Optional, Tuple, Set
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

class ConnectionManager:
    """Менеджер WebSocket соединений"""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.bot_data: Dict[str, Any] = {}
        self._broadcast_task: Optional[asyncio.Task] = None
        
    async def connect(self, websocket: WebSocket):
        """Подключение нового клиента"""
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"✅ WebSocket подключен. Активных: {len(self.active_connections)}")
        
        # Отправляем текущее состояние
        if self.bot_data:
            await websocket.send_json({
                "type": "initial",
                "data": self.bot_data
            })
    
    def disconnect(self, websocket: WebSocket):
        """Отключение клиента"""
        self.active_connections.discard(websocket)
        logger.info(f"❌ WebSocket отключен. Активных: {len(self.active_connections)}")
    
    async def broadcast(self, message: Dict[str, Any]):
        """Отправка сообщения всем подключенным клиентам"""
        if not self.active_connections:
            return
            
        # Сохраняем последние данные
        self.bot_data.update(message.get("data", {}))
        
        # Копируем список для безопасной итерации
        connections = list(self.active_connections)
        disconnected = []
        
        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Ошибка отправки WebSocket: {e}")
                disconnected.append(connection)
        
        # Удаляем отключенные соединения
        for conn in disconnected:
            self.disconnect(conn)
    
    async def send_bot_update(self, update_type: str, data: Dict[str, Any]):
        """Отправка обновления от бота"""
        message = {
            "type": update_type,
            "timestamp": datetime.now().isoformat(),
            "data": data
        }
        await self.broadcast(message)
    
    async def start_broadcast_loop(self):
        """Запуск цикла обновлений"""
        logger.info("🔄 Запущен цикл WebSocket broadcast")
        
        while True:
            try:
                # Получаем данные от бота
                from ..bot.manager import bot_manager
                
                status = bot_manager.get_status()
                
                # Формируем обновление
                update = {
                    "bot_status": status,
                    "timestamp": datetime.now().isoformat()
                }
                
                # Если бот запущен, добавляем дополнительные данные
                if status.get("is_running"):
                    # Получаем баланс
                    try:
                        balance = await bot_manager.exchange.fetch_balance()
                        update["balance"] = {
                            "USDT": balance.get("USDT", {}).get("free", 0),
                            "total": balance.get("USDT", {}).get("total", 0)
                        }
                    except:
                        update["balance"] = {"USDT": 0, "total": 0}
                    
                    # Получаем последние сделки из БД
                    from ..core.database import SessionLocal
                    from ..core.models import Trade, Signal
                    
                    db = SessionLocal()
                    try:
                        # Последние сделки
                        recent_trades = db.query(Trade).order_by(
                            Trade.created_at.desc()
                        ).limit(10).all()
                        
                        update["recent_trades"] = [
                            {
                                "id": t.id,
                                "symbol": t.symbol,
                                "side": t.side.value if hasattr(t.side, 'value') else str(t.side),
                                "entry_price": float(t.entry_price) if t.entry_price else 0,
                                "exit_price": float(t.exit_price) if t.exit_price else None,
                                "profit": float(t.profit) if t.profit else None,
                                "status": t.status.value if hasattr(t.status, 'value') else str(t.status),
                                "created_at": t.created_at.isoformat() if t.created_at else None
                            } for t in recent_trades
                        ]
                        
                        # Последние сигналы
                        recent_signals = db.query(Signal).order_by(
                            Signal.created_at.desc()
                        ).limit(10).all()
                        
                        update["recent_signals"] = [
                            {
                                "id": s.id,
                                "symbol": s.symbol,
                                "action": s.action,
                                "confidence": float(s.confidence) if s.confidence else 0,
                                "reason": s.reason,
                                "created_at": s.created_at.isoformat() if s.created_at else None
                            } for s in recent_signals
                        ]
                        
                    finally:
                        db.close()
                
                # Отправляем обновление
                await self.send_bot_update("update", update)
                
            except Exception as e:
                logger.error(f"Ошибка в broadcast loop: {e}")
            
            # Ждем перед следующим обновлением
            await asyncio.sleep(5)  # Обновление каждые 5 секунд

# Глобальный экземпляр
ws_manager = ConnectionManager()

async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint для подключения клиентов"""
    await ws_manager.connect(websocket)
    try:
        while True:
            # Ожидаем сообщения от клиента
            try:
                data = await websocket.receive_text()
                
                # Здесь можно обрабатывать команды от клиента
                try:
                    message = json.loads(data)
                    if message.get("type") == "ping":
                        await websocket.send_json({"type": "pong"})
                    elif message.get("type") == "auth":
                        # Простая проверка токена (можно улучшить)
                        token = message.get("token")
                        if token:
                            await websocket.send_json({"type": "auth_success"})
                        else:
                            await websocket.send_json({"type": "auth_required"})
                except json.JSONDecodeError:
                    pass
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Ошибка в WebSocket: {e}")
                break
                
    except WebSocketDisconnect:
        pass
    finally:
        ws_manager.disconnect(websocket)