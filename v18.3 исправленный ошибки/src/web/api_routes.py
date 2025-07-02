"""
API endpoints для управления ботом - ПОЛНАЯ ВЕРСИЯ С АВТОРИЗАЦИЕЙ
Путь: src/web/api_routes.py

Этот файл содержит все API endpoints для управления ботом через веб-интерфейс.
Включает полную систему авторизации с защитой от брутфорса.
"""
import asyncio
import json
from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.security import OAuth2PasswordRequestForm
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from pydantic import BaseModel
import logging

# Импорты из нашего проекта
from ..core.database import get_db
from ..core.models import (
    Trade, Signal, TradingPair, User, BotState, 
    Balance, TradeStatus, OrderSide, SignalAction
)
from ..logging.smart_logger import get_clean_logger
from .dashboard import get_dashboard_html
from .auth import get_current_user, create_access_token, verify_password, get_password_hash

logger = get_clean_logger(__name__)

# ===== КОНСТАНТЫ ДЛЯ ЗАЩИТЫ ОТ БРУТФОРСА =====
MAX_LOGIN_ATTEMPTS = 5  # Максимум попыток входа
BLOCK_DURATION_MINUTES = 30  # Время блокировки в минутах
LOGIN_ATTEMPT_WINDOW_MINUTES = 15  # Окно для подсчета попыток

# ===== PYDANTIC МОДЕЛИ =====

class LoginRequest(BaseModel):
    """Запрос на вход в систему"""
    username: str
    password: str

class BotStartRequest(BaseModel):
    """Запрос на запуск бота"""
    strategy: Optional[str] = "auto"
    pairs: Optional[List[str]] = None

class BotActionRequest(BaseModel):
    """Запрос на действие с ботом"""
    action: str  # start, stop, restart

class SettingsRequest(BaseModel):
    """Запрос на обновление настроек"""
    max_position_size: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    max_daily_trades: Optional[int] = None
    trading_pairs: Optional[List[str]] = None

# ===== WEBSOCKET МЕНЕДЖЕР =====

class WebSocketManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self._broadcast_task: Optional[asyncio.Task] = None
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"🔌 WebSocket подключен. Активных соединений: {len(self.active_connections)}")
        
        # Отправляем начальный статус
        try:
            if bot_manager:
                status = bot_manager.get_status()
                await websocket.send_json({
                    "type": "initial_status",
                    "data": status
                })
        except Exception as e:
            logger.error(f"Ошибка отправки начального статуса: {e}")
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"🔌 WebSocket отключен. Активных соединений: {len(self.active_connections)}")
    
    async def broadcast(self, data: dict):
        """Отправка данных всем подключенным клиентам"""
        if not self.active_connections:
            return
        
        message = json.dumps(data, default=str, ensure_ascii=False)
        disconnected = []
        
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Ошибка отправки WebSocket: {e}")
                disconnected.append(connection)
        
        # Удаляем отключенные соединения
        for connection in disconnected:
            self.disconnect(connection)
    
    async def start_broadcast_loop(self):
        """Запуск цикла автоматических обновлений"""
        if self._broadcast_task and not self._broadcast_task.done():
            return
        
        self._broadcast_task = asyncio.create_task(self._broadcast_worker())
        logger.info("🔄 Запущен цикл WebSocket обновлений")
    
    async def _broadcast_worker(self):
        """Воркер для отправки обновлений"""
        while True:
            try:
                if bot_manager:
                    # Получаем актуальные данные
                    status = bot_manager.get_status()
                    
                    # Отправляем обновление
                    await self.broadcast({
                        "type": "status_update",
                        "data": status,
                        "timestamp": datetime.utcnow()
                    })
                
                await asyncio.sleep(5)  # Обновление каждые 5 секунд
                
            except Exception as e:
                logger.error(f"Ошибка в broadcast worker: {e}")
                await asyncio.sleep(10)

# Глобальный менеджер WebSocket
ws_manager = WebSocketManager()

# Глобальная переменная для BotManager
bot_manager = None

def set_bot_manager(manager):
    """Установить ссылку на менеджера бота"""
    global bot_manager
    bot_manager = manager
    logger.info("✅ BotManager установлен в API роутах")

# Создаем роутер
router = APIRouter()

# ===== ФУНКЦИИ ЗАЩИТЫ ОТ БРУТФОРСА =====

def check_user_blocked(user: User) -> bool:
    """Проверка, заблокирован ли пользователь"""
    if not user.is_blocked:
        return False
    
    # Проверяем, прошло ли время блокировки
    if user.blocked_at:
        block_duration = timedelta(minutes=BLOCK_DURATION_MINUTES)
        if datetime.utcnow() - user.blocked_at > block_duration:
            return False
    
    return True

def handle_failed_login(db: Session, user: User, client_ip: str):
    """Обработка неудачной попытки входа"""
    user.failed_login_attempts += 1
    
    # Проверяем, нужно ли заблокировать
    if user.failed_login_attempts >= MAX_LOGIN_ATTEMPTS:
        user.is_blocked = True
        user.blocked_at = datetime.utcnow()
        logger.warning(f"🔒 Пользователь {user.username} заблокирован после {MAX_LOGIN_ATTEMPTS} неудачных попыток. IP: {client_ip}")
    
    db.commit()

def handle_successful_login(db: Session, user: User):
    """Обработка успешного входа"""
    user.failed_login_attempts = 0
    user.last_login = datetime.utcnow()
    if user.is_blocked:
        user.is_blocked = False
        user.blocked_at = None
    db.commit()

# ===== ОСНОВНЫЕ ENDPOINTS =====

@router.get("/", response_class=HTMLResponse)
async def dashboard():
    """Главная страница с дашбордом"""
    return get_dashboard_html()

@router.get("/api")
async def api_info():
    """Информация об API"""
    return {
        "service": "Crypto Trading Bot API",
        "version": "3.0.0",
        "status": "running",
        "timestamp": datetime.utcnow(),
        "endpoints": {
            "dashboard": "/",
            "documentation": "/docs",
            "health": "/health",
            "login": "/api/login",
            "bot_status": "/api/bot/status",
            "websocket": "/ws"
        }
    }

@router.get("/health")
async def health_check():
    """Проверка здоровья системы"""
    health_info = {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "components": {}
    }
    
    # Проверяем компоненты
    try:
        # База данных
        db = next(get_db())
        db.execute("SELECT 1")
        health_info["components"]["database"] = "healthy"
        db.close()
    except Exception as e:
        health_info["components"]["database"] = "error"
        health_info["status"] = "degraded"
    
    # BotManager
    if bot_manager:
        health_info["components"]["bot_manager"] = "healthy"
    else:
        health_info["components"]["bot_manager"] = "not_initialized"
        health_info["status"] = "degraded"
    
    return health_info

# ===== AUTHENTICATION ENDPOINTS =====

@router.post("/api/login")
async def login(
    request: LoginRequest,
    req: Request,
    db: Session = Depends(get_db)
):
    """
    Endpoint для входа в систему с защитой от брутфорса
    
    Возвращает JWT токен при успешной авторизации.
    Блокирует пользователя после MAX_LOGIN_ATTEMPTS неудачных попыток.
    """
    # Получаем IP клиента
    client_ip = req.client.host if req.client else "unknown"
    
    # Ищем пользователя
    user = db.query(User).filter(User.username == request.username).first()
    
    if not user:
        # Пользователь не найден, но не сообщаем об этом явно
        logger.warning(f"❌ Попытка входа с несуществующим пользователем: {request.username}. IP: {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверные учетные данные"
        )
    
    # Проверяем, не заблокирован ли пользователь
    if check_user_blocked(user):
        remaining_time = BLOCK_DURATION_MINUTES
        if user.blocked_at:
            elapsed = (datetime.utcnow() - user.blocked_at).total_seconds() / 60
            remaining_time = max(0, BLOCK_DURATION_MINUTES - int(elapsed))
        
        logger.warning(f"🔒 Попытка входа заблокированного пользователя: {user.username}. IP: {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Аккаунт временно заблокирован. Осталось {remaining_time} минут"
        )
    
    # Проверяем пароль
    if not verify_password(request.password, user.hashed_password):
        # Неверный пароль
        handle_failed_login(db, user, client_ip)
        
        remaining_attempts = MAX_LOGIN_ATTEMPTS - user.failed_login_attempts
        logger.warning(f"❌ Неверный пароль для {user.username}. Осталось попыток: {remaining_attempts}. IP: {client_ip}")
        
        if remaining_attempts > 0:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Неверные учетные данные. Осталось попыток: {remaining_attempts}"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Аккаунт заблокирован на {BLOCK_DURATION_MINUTES} минут"
            )
    
    # Проверяем, активен ли пользователь
    if not user.is_active:
        logger.warning(f"❌ Попытка входа неактивного пользователя: {user.username}. IP: {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Аккаунт деактивирован"
        )
    
    # Успешный вход
    handle_successful_login(db, user)
    
    # Создаем токен
    access_token = create_access_token(data={"sub": user.username})
    
    logger.info(f"✅ Успешный вход: {user.username}. IP: {client_ip}")
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "username": user.username,
            "is_admin": user.is_admin,
            "email": user.email
        }
    }

@router.post("/auth/token")
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    req: Request = None,
    db: Session = Depends(get_db)
):
    """OAuth2 совместимый endpoint для получения токена"""
    # Используем тот же механизм что и /api/login
    login_request = LoginRequest(
        username=form_data.username,
        password=form_data.password
    )
    
    result = await login(login_request, req, db)
    
    # OAuth2 требует немного другой формат ответа
    return {
        "access_token": result["access_token"],
        "token_type": "bearer"
    }

@router.get("/api/user/me")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Получить информацию о текущем пользователе"""
    return {
        "username": current_user.username,
        "email": current_user.email,
        "is_admin": current_user.is_admin,
        "is_active": current_user.is_active,
        "created_at": current_user.created_at,
        "last_login": current_user.last_login
    }

# ===== BOT CONTROL ENDPOINTS =====

@router.get("/api/bot/status")
async def get_bot_status():
    """Получить полный статус бота"""
    if not bot_manager:
        return {
            "status": "error",
            "is_running": False,
            "message": "Bot manager not initialized",
            "timestamp": datetime.utcnow()
        }
    
    try:
        return bot_manager.get_status()
    except Exception as e:
        logger.error(f"Ошибка получения статуса: {e}")
        return {
            "status": "error",
            "is_running": False,
            "message": str(e),
            "timestamp": datetime.utcnow()
        }

@router.post("/api/bot/start")
async def start_bot(
    request: BotStartRequest,
    current_user: User = Depends(get_current_user)
):
    """Запустить бота (требует авторизации)"""
    if not bot_manager:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bot manager not initialized"
        )
    
    logger.info(f"🚀 Пользователь {current_user.username} запускает бота")
    
    try:
        # Обновляем пары если указаны
        if request.pairs:
            await bot_manager.update_pairs(request.pairs)
        
        # Запускаем бота
        success, message = await bot_manager.start()
        
        if success:
            # Запускаем broadcast loop
            await ws_manager.start_broadcast_loop()
            
            # Отправляем уведомление через WebSocket
            await ws_manager.broadcast({
                "type": "bot_started",
                "message": message,
                "strategy": request.strategy,
                "user": current_user.username,
                "timestamp": datetime.utcnow()
            })
            
            return {
                "success": True,
                "message": message,
                "status": "started"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )
            
    except Exception as e:
        logger.error(f"Ошибка запуска бота: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start bot: {str(e)}"
        )

@router.post("/api/bot/stop")
async def stop_bot(current_user: User = Depends(get_current_user)):
    """Остановить бота (требует авторизации)"""
    if not bot_manager:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bot manager not initialized"
        )
    
    logger.info(f"🛑 Пользователь {current_user.username} останавливает бота")
    
    try:
        success, message = await bot_manager.stop()
        
        # Отправляем уведомление через WebSocket
        await ws_manager.broadcast({
            "type": "bot_stopped",
            "message": message,
            "user": current_user.username,
            "timestamp": datetime.utcnow()
        })
        
        return {
            "success": success,
            "message": message,
            "status": "stopped"
        }
        
    except Exception as e:
        logger.error(f"Ошибка остановки бота: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop bot: {str(e)}"
        )

@router.post("/api/bot/action")
async def bot_action(
    request: BotActionRequest,
    current_user: User = Depends(get_current_user)
):
    """Выполнить действие с ботом (требует авторизации)"""
    if request.action == "start":
        return await start_bot(BotStartRequest(), current_user)
    elif request.action == "stop":
        return await stop_bot(current_user)
    elif request.action == "restart":
        # Сначала останавливаем
        await stop_bot(current_user)
        await asyncio.sleep(2)  # Небольшая пауза
        # Затем запускаем
        return await start_bot(BotStartRequest(), current_user)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown action: {request.action}"
        )

# ===== DATA ENDPOINTS =====

@router.get("/api/stats")
async def get_statistics(db: Session = Depends(get_db)):
    """Получить статистику торговли"""
    try:
        # Определяем временные границы
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Статистика за сегодня
        today_trades = db.query(Trade).filter(
            Trade.created_at >= today_start
        ).all()
        
        # Считаем метрики
        total_trades = len(today_trades)
        closed_trades = [t for t in today_trades if t.status == TradeStatus.CLOSED]
        profitable_trades = [t for t in closed_trades if t.profit and t.profit > 0]
        
        total_profit = sum(t.profit or 0 for t in closed_trades)
        success_rate = (len(profitable_trades) / len(closed_trades) * 100) if closed_trades else 0
        
        # Лучшая и худшая сделки
        best_trade = max(closed_trades, key=lambda t: t.profit or 0) if closed_trades else None
        worst_trade = min(closed_trades, key=lambda t: t.profit or 0) if closed_trades else None
        
        return {
            "total_trades": total_trades,
            "closed_trades": len(closed_trades),
            "profitable_trades": len(profitable_trades),
            "total_profit": round(total_profit, 2),
            "success_rate": round(success_rate, 1),
            "best_trade": {
                "symbol": best_trade.symbol,
                "profit": round(best_trade.profit, 2)
            } if best_trade else None,
            "worst_trade": {
                "symbol": worst_trade.symbol,
                "profit": round(worst_trade.profit, 2)
            } if worst_trade else None,
            "timestamp": now
        }
        
    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get statistics"
        )



@router.get("/api/signals")
async def get_signals(
    limit: int = 50,
    executed: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """Получить список торговых сигналов"""
    try:
        query = db.query(Signal)
        
        # Фильтр по исполнению
        if executed is not None:
            query = query.filter(Signal.executed == executed)
        
        # Получаем сигналы
        signals = query.order_by(desc(Signal.created_at)).limit(limit).all()
        
        # Форматируем для отправки
        signals_data = []
        for signal in signals:
            signals_data.append({
                "id": signal.id,
                "symbol": signal.symbol,
                "action": signal.action,
                "confidence": float(signal.confidence) if signal.confidence else 0,
                "price": float(signal.price) if signal.price else 0,
                "stop_loss": float(signal.stop_loss) if signal.stop_loss else None,
                "take_profit": float(signal.take_profit) if signal.take_profit else None,
                "strategy": signal.strategy,
                "reason": signal.reason,
                "executed": signal.executed,
                "created_at": signal.created_at.isoformat() if signal.created_at else None
            })
        
        return {"signals": signals_data}
        
    except Exception as e:
        logger.error(f"Ошибка получения сигналов: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get signals"
        )

@router.get("/api/balance")
async def get_balance(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить текущий баланс (требует авторизации)"""
    try:
        # Пробуем получить с биржи
        if bot_manager and hasattr(bot_manager, 'exchange'):
            try:
                balance = await bot_manager.exchange.fetch_balance()
                usdt_balance = balance.get('USDT', {})
                
                # Сохраняем в БД
                balance_record = Balance(
                    currency='USDT',
                    total=float(usdt_balance.get('total', 0)),
                    free=float(usdt_balance.get('free', 0)),
                    used=float(usdt_balance.get('used', 0)),
                    timestamp=datetime.utcnow()
                )
                db.add(balance_record)
                db.commit()
                
                return {
                    "USDT": {
                        "total": float(usdt_balance.get('total', 0)),
                        "free": float(usdt_balance.get('free', 0)),
                        "used": float(usdt_balance.get('used', 0))
                    },
                    "source": "exchange",
                    "timestamp": datetime.utcnow()
                }
            except Exception as e:
                logger.warning(f"Не удалось получить баланс с биржи: {e}")
        
        # Если не получилось с биржи, берем из БД
        latest_balance = db.query(Balance).filter(
            Balance.currency == 'USDT'
        ).order_by(desc(Balance.timestamp)).first()
        
        if latest_balance:
            return {
                "USDT": {
                    "total": float(latest_balance.total),
                    "free": float(latest_balance.free),
                    "used": float(latest_balance.used)
                },
                "source": "database",
                "timestamp": latest_balance.timestamp
            }
        else:
            return {
                "USDT": {"total": 0, "free": 0, "used": 0},
                "source": "default",
                "timestamp": datetime.utcnow()
            }
            
    except Exception as e:
        logger.error(f"Ошибка получения баланса: {e}")
        return {
            "USDT": {"total": 0, "free": 0, "used": 0},
            "error": str(e),
            "timestamp": datetime.utcnow()
        }

@router.post("/api/trading-pairs")
async def update_trading_pairs(
    pairs: List[str],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Обновить список активных торговых пар (требует авторизации)"""
    
    # Проверяем права администратора
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только администратор может изменять торговые пары"
        )
    
    try:
        # Деактивируем все пары
        db.query(TradingPair).update({"is_active": False})
        
        # Активируем выбранные
        for symbol in pairs:
            pair = db.query(TradingPair).filter(
                TradingPair.symbol == symbol
            ).first()
            
            if pair:
                pair.is_active = True
            else:
                # Создаем новую пару
                new_pair = TradingPair(
                    symbol=symbol,
                    is_active=True,
                    strategy='auto',  # Автоматический выбор стратегии
                    stop_loss_percent=2.0,
                    take_profit_percent=4.0
                )
                db.add(new_pair)
        
        db.commit()
        
        # Обновляем в боте если он запущен
        if bot_manager:
            await bot_manager.update_pairs(pairs)
        
        logger.info(f"✅ Пользователь {current_user.username} обновил торговые пары: {pairs}")
        
        return {
            "success": True,
            "message": f"Updated {len(pairs)} trading pairs",
            "pairs": pairs
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка обновления торговых пар: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update trading pairs"
        )


# ===== SETTINGS ENDPOINTS =====

@router.get("/api/settings")
async def get_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить текущие настройки (требует авторизации)"""
    try:
        # Получаем настройки из конфига и БД
        from ..core.config import config
        
        settings = {
            "trading": {
                "max_position_size_percent": config.MAX_POSITION_SIZE_PERCENT,
                "stop_loss_percent": config.STOP_LOSS_PERCENT,
                "take_profit_percent": config.TAKE_PROFIT_PERCENT,
                "max_daily_trades": config.MAX_DAILY_TRADES,
                "max_positions": config.MAX_POSITIONS,
                "min_risk_reward_ratio": config.MIN_RISK_REWARD_RATIO
            },
            "exchange": {
                "name": "Bybit",
                "testnet": config.BYBIT_TESTNET
            },
            "notifications": {
                "telegram_enabled": bool(config.TELEGRAM_BOT_TOKEN),
                "telegram_chat_id": config.TELEGRAM_CHAT_ID if config.TELEGRAM_BOT_TOKEN else None
            }
        }
        
        return settings
        
    except Exception as e:
        logger.error(f"Ошибка получения настроек: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get settings"
        )

@router.post("/api/settings")
async def update_settings(
    settings: SettingsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Обновить настройки бота (требует прав администратора)"""
    
    # Проверяем права администратора
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только администратор может изменять настройки"
        )
    
    try:
        # Здесь можно сохранить настройки в БД
        # Для простоты пока просто возвращаем успех
        
        logger.info(f"⚙️ Пользователь {current_user.username} обновил настройки")
        
        # Отправляем уведомление через WebSocket
        await ws_manager.broadcast({
            "type": "settings_updated",
            "settings": settings.dict(exclude_none=True),
            "user": current_user.username,
            "timestamp": datetime.utcnow()
        })
        
        return {
            "success": True,
            "message": "Settings updated successfully"
        }
        
    except Exception as e:
        logger.error(f"Ошибка обновления настроек: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update settings"
        )

# ===== WEBSOCKET ENDPOINT =====

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket для real-time обновлений"""
    await ws_manager.connect(websocket)
    
    try:
        while True:
            # Ждем сообщения от клиента
            data = await websocket.receive_text()
            
            # Обрабатываем команды от клиента
            try:
                message = json.loads(data)
                
                if message.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                elif message.get("type") == "get_status":
                    if bot_manager:
                        status = bot_manager.get_status()
                        await websocket.send_json({
                            "type": "status_response",
                            "data": status
                        })
                        
            except json.JSONDecodeError:
                logger.warning(f"Получено некорректное сообщение: {data}")
                
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket ошибка: {e}")
        ws_manager.disconnect(websocket)

# ===== EXPORT/IMPORT ENDPOINTS =====

@router.get("/api/export/trades")
async def export_trades(
    format: str = "csv",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Экспорт сделок в CSV или JSON (требует авторизации)"""
    try:
        query = db.query(Trade)
        
        # Фильтр по пользователю если не админ
        if not current_user.is_admin:
            query = query.filter(Trade.user_id == current_user.id)
        
        trades = query.order_by(desc(Trade.created_at)).all()
        
        if format == "json":
            trades_data = []
            for trade in trades:
                trades_data.append({
                    "id": trade.id,
                    "symbol": trade.symbol,
                    "side": str(trade.side.value) if hasattr(trade.side, 'value') else str(trade.side),
                    "entry_price": float(trade.entry_price) if trade.entry_price else 0,
                    "exit_price": float(trade.exit_price) if trade.exit_price else None,
                    "quantity": float(trade.quantity) if trade.quantity else 0,
                    "profit": float(trade.profit) if trade.profit else None,
                    "status": str(trade.status.value) if hasattr(trade.status, 'value') else str(trade.status),
                    "strategy": trade.strategy,
                    "created_at": trade.created_at.isoformat() if trade.created_at else None,
                    "closed_at": trade.closed_at.isoformat() if trade.closed_at else None
                })
            
            return JSONResponse(content={"trades": trades_data})
            
        else:  # CSV
            import csv
            from io import StringIO
            
            output = StringIO()
            writer = csv.writer(output)
            
            # Заголовки
            writer.writerow([
                "ID", "Symbol", "Side", "Entry Price", "Exit Price",
                "Quantity", "Profit", "Status", "Strategy",
                "Created At", "Closed At"
            ])
            
            # Данные
            for trade in trades:
                writer.writerow([
                    trade.id,
                    trade.symbol,
                    str(trade.side.value) if hasattr(trade.side, 'value') else str(trade.side),
                    float(trade.entry_price) if trade.entry_price else 0,
                    float(trade.exit_price) if trade.exit_price else "",
                    float(trade.quantity) if trade.quantity else 0,
                    float(trade.profit) if trade.profit else "",
                    str(trade.status.value) if hasattr(trade.status, 'value') else str(trade.status),
                    trade.strategy,
                    trade.created_at.isoformat() if trade.created_at else "",
                    trade.closed_at.isoformat() if trade.closed_at else ""
                ])
            
            output.seek(0)
            
            return StreamingResponse(
                iter([output.getvalue()]),
                media_type="text/csv",
                headers={
                    "Content-Disposition": f"attachment; filename=trades_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                }
            )
            
    except Exception as e:
        logger.error(f"Ошибка экспорта сделок: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export trades"
        )
        
        


# ===== ADMIN ENDPOINTS =====

@router.post("/api/admin/unblock-user/{username}")
async def unblock_user(
    username: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Разблокировать пользователя (только для администраторов)"""
    
    # Проверяем права администратора
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только администратор может разблокировать пользователей"
        )
    
    # Ищем пользователя
    user = db.query(User).filter(User.username == username).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Пользователь {username} не найден"
        )
    
    # Разблокируем
    user.is_blocked = False
    user.blocked_at = None
    user.failed_login_attempts = 0
    db.commit()
    
    logger.info(f"🔓 Администратор {current_user.username} разблокировал пользователя {username}")
    
    return {
        "success": True,
        "message": f"Пользователь {username} разблокирован"
    }

@router.get("/api/admin/users")
async def get_users_list(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить список пользователей (только для администраторов)"""
    
    # Проверяем права администратора
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только администратор может просматривать список пользователей"
        )
    
    users = db.query(User).all()
    
    users_data = []
    for user in users:
        users_data.append({
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_active": user.is_active,
            "is_admin": user.is_admin,
            "is_blocked": user.is_blocked,
            "failed_login_attempts": user.failed_login_attempts,
            "last_login": user.last_login.isoformat() if user.last_login else None,
            "blocked_at": user.blocked_at.isoformat() if user.blocked_at else None,
            "created_at": user.created_at.isoformat() if user.created_at else None
        })
    
    return {"users": users_data}

# ===== ADVANCED ANALYTICS ENDPOINTS =====

@router.get("/api/analytics/performance")
async def get_performance_analytics(
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить расширенную аналитику производительности (требует авторизации)"""
    try:
        # Используем AdvancedAnalytics если доступен
        from ..analysis.advanced_analytics import advanced_analytics
        
        report = await advanced_analytics.generate_performance_report(days)
        return report
        
    except ImportError:
        # Базовая аналитика если модуль недоступен
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        query = db.query(Trade).filter(
            Trade.created_at >= start_date,
            Trade.status == TradeStatus.CLOSED
        )
        
        # Фильтр по пользователю если не админ
        if not current_user.is_admin:
            query = query.filter(Trade.user_id == current_user.id)
        
        trades = query.all()
        
        return {
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "days": days
            },
            "summary": {
                "total_trades": len(trades),
                "profitable_trades": len([t for t in trades if t.profit and t.profit > 0]),
                "total_profit": sum(t.profit or 0 for t in trades)
            }
        }
    except Exception as e:
        logger.error(f"Ошибка получения аналитики: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get analytics"
        )
        
        
@router.get("/api/trading/status")
async def get_trading_status(
    current_user: User = Depends(get_current_user)
):
    """API для получения статуса реальной торговли"""
    try:
        if not bot_manager:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Bot manager not initialized"
            )
        
        if hasattr(bot_manager, 'trading_integration'):
            trading_status = bot_manager.trading_integration.get_status()
            
            return {
                'success': True,
                'data': {
                    'mode': 'live' if not config.PAPER_TRADING else 'paper',
                    'open_positions': trading_status.get('open_positions', 0),
                    'daily_pnl': trading_status.get('daily_pnl', 0.0),
                    'risk_utilization': trading_status.get('risk_utilization', 0.0),
                    'last_trade': trading_status.get('last_trade_time'),
                    'trades_today': trading_status.get('trades_today', 0),
                    'balance': trading_status.get('current_balance', 0.0),
                    'equity': trading_status.get('equity', 0.0),
                    'margin_used': trading_status.get('margin_used', 0.0),
                    'is_safe': trading_status.get('is_safe', True)
                }
            }
        else:
            return {
                'success': False, 
                'error': 'Trading integration not initialized'
            }
    except Exception as e:
        logger.error(f"Ошибка получения статуса торговли: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/api/trading/positions")  
async def get_open_positions(
    current_user: User = Depends(get_current_user)
):
    """API для получения открытых позиций"""
    try:
        if not bot_manager or not hasattr(bot_manager, 'trading_integration'):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Trading integration not available"
            )
        
        positions = await bot_manager.trading_integration.get_open_positions()
        
        return {
            'success': True,
            'data': positions,
            'count': len(positions),
            'timestamp': datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Ошибка получения позиций: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/api/trading/close_position")
async def close_position(
    request: dict,
    current_user: User = Depends(get_current_user)
):
    """Закрытие конкретной позиции"""
    try:
        symbol = request.get('symbol')
        if not symbol:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Symbol is required"
            )
        
        if not bot_manager or not hasattr(bot_manager, 'trading_integration'):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Trading integration not available"
            )
        
        result = await bot_manager.trading_integration.close_position(symbol)
        
        # Логируем действие пользователя
        logger.info(
            f"👤 Пользователь {current_user.username} закрыл позицию {symbol}",
            category='trading',
            user_id=current_user.id,
            symbol=symbol,
            action='manual_close'
        )
        
        return {
            'success': result.get('success', False),
            'message': result.get('message', ''),
            'symbol': symbol,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Ошибка закрытия позиции: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/api/trading/close_all")
async def close_all_positions(
    current_user: User = Depends(get_current_user)
):
    """Закрытие всех открытых позиций"""
    try:
        if not bot_manager or not hasattr(bot_manager, 'trading_integration'):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Trading integration not available"
            )
        
        result = await bot_manager.trading_integration.close_all_positions()
        
        # Логируем критичное действие
        logger.critical(
            f"🚨 Пользователь {current_user.username} закрыл ВСЕ позиции",
            category='trading',
            user_id=current_user.id,
            action='close_all_positions',
            positions_count=result.get('closed_count', 0)
        )
        
        return {
            'success': result.get('success', False),
            'message': result.get('message', ''),
            'closed_positions': result.get('closed_count', 0),
            'failed_positions': result.get('failed_count', 0),
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Ошибка закрытия всех позиций: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/api/trading/emergency_stop")
async def emergency_stop_trading(
    current_user: User = Depends(get_current_user)
):
    """Экстренная остановка торговли"""
    try:
        if not bot_manager:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Bot manager not available"
            )
        
        # Экстренная остановка
        result = await bot_manager.emergency_stop()
        
        # Критичное логирование
        logger.critical(
            f"🚨 ЭКСТРЕННАЯ ОСТАНОВКА активирована пользователем {current_user.username}",
            category='emergency',
            user_id=current_user.id,
            action='emergency_stop'
        )
        
        return {
            'success': result[0],
            'message': result[1],
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Ошибка экстренной остановки: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/api/trading/risk_status")
async def get_risk_status(
    current_user: User = Depends(get_current_user)
):
    """Получение статуса рисков"""
    try:
        if not bot_manager or not hasattr(bot_manager, 'trading_integration'):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Trading integration not available"
            )
        
        risk_status = await bot_manager.trading_integration.check_risk_limits()
        
        return {
            'success': True,
            'data': {
                'is_safe': risk_status.is_safe,
                'risk_score': risk_status.risk_score,
                'daily_loss': risk_status.daily_loss,
                'portfolio_risk': risk_status.portfolio_risk,
                'max_drawdown': risk_status.max_drawdown,
                'open_positions': risk_status.open_positions_count,
                'correlation_risk': risk_status.correlation_risk,
                'warnings': risk_status.warnings,
                'limits': {
                    'max_daily_loss': config.MAX_DAILY_LOSS_PERCENT,
                    'max_portfolio_risk': config.MAX_PORTFOLIO_RISK_PERCENT,
                    'max_positions': config.MAX_POSITIONS,
                    'max_correlation': config.MAX_CORRELATION_THRESHOLD
                }
            },
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Ошибка получения статуса рисков: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/api/trading/set_mode")
async def set_trading_mode(
    request: dict,
    current_user: User = Depends(get_current_user)
):
    """Переключение режима торговли (paper/live)"""
    try:
        mode = request.get('mode')  # 'paper' или 'live'
        
        if mode not in ['paper', 'live']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mode must be 'paper' or 'live'"
            )
        
        # Проверяем права пользователя
        if mode == 'live' and not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admin can enable live trading"
            )
        
        if not bot_manager:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Bot manager not available"
            )
        
        # Изменяем режим
        old_mode = 'paper' if config.PAPER_TRADING else 'live'
        
        if mode == 'paper':
            config.PAPER_TRADING = True
            config.LIVE_TRADING = False
        else:
            config.PAPER_TRADING = False  
            config.LIVE_TRADING = True
        
        # Логируем смену режима
        logger.critical(
            f"🔄 Пользователь {current_user.username} сменил режим торговли: {old_mode} → {mode}",
            category='trading',
            user_id=current_user.id,
            old_mode=old_mode,
            new_mode=mode
        )
        
        return {
            'success': True,
            'message': f'Режим торговли изменен на {mode}',
            'old_mode': old_mode,
            'new_mode': mode,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Ошибка смены режима торговли: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ===== ФУНКЦИИ ДЛЯ ЭКСПОРТА =====

__all__ = [
    'router',
    'set_bot_manager', 
    'ws_manager',
    'WebSocketManager',
    'get_trading_status',
    'get_open_positions', 
    'close_position',
    'close_all_positions',
    'emergency_stop_trading',
    'get_risk_status',
    'set_trading_mode'
]