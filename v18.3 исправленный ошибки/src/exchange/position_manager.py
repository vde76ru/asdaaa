"""
POSITION MANAGER - Управление торговыми позициями
Файл: src/exchange/position_manager.py

🎯 ФУНКЦИИ:
✅ Автоматический мониторинг всех открытых позиций 24/7
✅ Stop-loss/take-profit исполнение без участия человека
✅ Трейлинг стопы для максимизации прибыли
✅ Экстренное закрытие при критических условиях
✅ Обновление PnL в реальном времени
"""
import asyncio
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
import logging

from ..core.database import SessionLocal
from ..core.models import Trade, TradeStatus, OrderSide
from ..logging.smart_logger import get_logger
try:
    from .unified_exchange import get_real_exchange_client
except ImportError:
    from .real_client import get_real_exchange_client

logger = get_logger(__name__)

@dataclass
class PositionInfo:
    """Информация о позиции"""
    symbol: str
    side: str  # long/short
    size: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_percent: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    trailing_stop: bool = False
    trailing_distance: Optional[float] = None
    max_price: Optional[float] = None  # Для трейлинг стопа
    min_price: Optional[float] = None  # Для трейлинг стопа

@dataclass
class TradeUpdate:
    """Обновление сделки"""
    trade_id: int
    status: TradeStatus
    exit_price: Optional[float] = None
    profit: Optional[float] = None
    exit_reason: Optional[str] = None

class PositionManager:
    """
    Менеджер торговых позиций
    
    🔥 АВТОМАТИЧЕСКОЕ УПРАВЛЕНИЕ ПОЗИЦИЯМИ:
    1. Мониторинг открытых позиций каждые 30 секунд
    2. Автоматический stop-loss/take-profit без участия человека
    3. Трейлинг стопы для увеличения прибыли
    4. Partial close логика для фиксации прибыли
    5. Экстренное закрытие при критической просадке
    """
    
    def __init__(self, check_interval: int = 30):
        """
        Инициализация менеджера позиций
        
        Args:
            check_interval: Интервал проверки позиций в секундах
        """
        self.exchange = get_real_exchange_client()
        self.check_interval = check_interval
        self.is_running = False
        self.positions: Dict[str, PositionInfo] = {}
        self.active_trades: Dict[int, Trade] = {}
        
        # Настройки риск-менеджмента
        self.max_slippage_percent = 0.5  # Максимальное проскальзывание
        self.emergency_stop_drawdown = 0.15  # 15% просадка для экстренной остановки
        self.partial_close_profit_threshold = 0.05  # 5% прибыли для частичного закрытия
        
        logger.info(
            "Position Manager инициализирован",
            category='position',
            check_interval=check_interval
        )
    
    async def start_monitoring(self):
        """Запуск мониторинга позиций"""
        if self.is_running:
            logger.warning("Position Manager уже запущен")
            return
        
        self.is_running = True
        
        logger.info(
            "🔄 Запуск мониторинга позиций",
            category='position'
        )
        
        while self.is_running:
            try:
                await self._monitoring_cycle()
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(
                    f"❌ Ошибка в цикле мониторинга позиций: {e}",
                    category='position'
                )
                await asyncio.sleep(5)  # Короткая пауза при ошибке
    
    def stop_monitoring(self):
        """Остановка мониторинга"""
        self.is_running = False
        logger.info("⏹️ Мониторинг позиций остановлен", category='position')
    
    async def _monitoring_cycle(self):
        """Один цикл мониторинга"""
        try:
            # 1. Обновляем информацию о позициях
            await self._update_positions()
            
            # 2. Загружаем активные сделки из БД
            await self._load_active_trades()
            
            # 3. Проверяем stop-loss/take-profit
            await self._check_stop_loss_take_profit()
            
            # 4. Обновляем трейлинг стопы
            await self._update_trailing_stops()
            
            # 5. Проверяем условия для частичного закрытия
            await self._check_partial_close()
            
            # 6. Проверяем экстренные условия
            await self._check_emergency_conditions()
            
            # 7. Обновляем PnL в базе данных
            await self._update_trades_pnl()
            
        except Exception as e:
            logger.error(f"❌ Ошибка в цикле мониторинга: {e}")
    
    async def _update_positions(self):
        """Обновление информации о позициях с биржи"""
        try:
            # Получаем позиции с биржи
            exchange_positions = await self.exchange.fetch_positions()
            
            # Обновляем наш кэш
            self.positions.clear()
            
            for pos in exchange_positions:
                if pos.size > 0:  # Только открытые позиции
                    symbol = pos.symbol
                    
                    # Получаем текущую цену
                    ticker = await self.exchange.fetch_ticker(symbol)
                    current_price = ticker['last']
                    
                    position_info = PositionInfo(
                        symbol=symbol,
                        side=pos.side,
                        size=pos.size,
                        entry_price=pos.entry_price,
                        current_price=current_price,
                        unrealized_pnl=pos.unrealized_pnl,
                        unrealized_pnl_percent=pos.percentage
                    )
                    
                    self.positions[symbol] = position_info
            
            if self.positions:
                logger.debug(
                    f"📊 Обновлено позиций: {len(self.positions)}",
                    category='position',
                    symbols=list(self.positions.keys())
                )
                
        except Exception as e:
            logger.error(f"❌ Ошибка обновления позиций: {e}")
    
    async def _load_active_trades(self):
        """Загрузка активных сделок из БД"""
        db = SessionLocal()
        try:
            active_trades = db.query(Trade).filter(
                Trade.status == TradeStatus.OPEN
            ).all()
            
            self.active_trades.clear()
            for trade in active_trades:
                self.active_trades[trade.id] = trade
                
                # Добавляем информацию о stop-loss/take-profit к позициям
                if trade.symbol in self.positions:
                    position = self.positions[trade.symbol]
                    position.stop_loss = trade.stop_loss
                    position.take_profit = trade.take_profit
                    position.trailing_stop = trade.trailing_stop or False
                    position.trailing_distance = trade.trailing_distance
            
        finally:
            db.close()
    
    async def _check_stop_loss_take_profit(self):
        """Проверка условий stop-loss и take-profit"""
        updates = []
        
        for symbol, position in self.positions.items():
            try:
                # Проверяем stop-loss
                if position.stop_loss:
                    sl_triggered = False
                    
                    if position.side == 'long' and position.current_price <= position.stop_loss:
                        sl_triggered = True
                    elif position.side == 'short' and position.current_price >= position.stop_loss:
                        sl_triggered = True
                    
                    if sl_triggered:
                        logger.warning(
                            f"🛑 Stop-Loss triggered для {symbol}",
                            category='position',
                            symbol=symbol,
                            current_price=position.current_price,
                            stop_loss=position.stop_loss,
                            loss_percent=position.unrealized_pnl_percent
                        )
                        
                        # Закрываем позицию
                        if await self._close_position_with_reason(symbol, "Stop-Loss"):
                            updates.append(TradeUpdate(
                                trade_id=self._get_trade_id_by_symbol(symbol),
                                status=TradeStatus.CLOSED,
                                exit_price=position.current_price,
                                profit=position.unrealized_pnl,
                                exit_reason="Stop-Loss"
                            ))
                
                # Проверяем take-profit
                if position.take_profit:
                    tp_triggered = False
                    
                    if position.side == 'long' and position.current_price >= position.take_profit:
                        tp_triggered = True
                    elif position.side == 'short' and position.current_price <= position.take_profit:
                        tp_triggered = True
                    
                    if tp_triggered:
                        logger.info(
                            f"🎯 Take-Profit triggered для {symbol}",
                            category='position',
                            symbol=symbol,
                            current_price=position.current_price,
                            take_profit=position.take_profit,
                            profit_percent=position.unrealized_pnl_percent
                        )
                        
                        # Закрываем позицию
                        if await self._close_position_with_reason(symbol, "Take-Profit"):
                            updates.append(TradeUpdate(
                                trade_id=self._get_trade_id_by_symbol(symbol),
                                status=TradeStatus.CLOSED,
                                exit_price=position.current_price,
                                profit=position.unrealized_pnl,
                                exit_reason="Take-Profit"
                            ))
                
            except Exception as e:
                logger.error(f"❌ Ошибка проверки SL/TP для {symbol}: {e}")
        
        # Обновляем сделки в БД
        if updates:
            await self._update_trades_in_db(updates)
    
    async def _update_trailing_stops(self):
        """Обновление трейлинг стопов"""
        for symbol, position in self.positions.items():
            if not position.trailing_stop or not position.trailing_distance:
                continue
            
            try:
                trade = self._get_trade_by_symbol(symbol)
                if not trade:
                    continue
                
                # Обновляем максимальную/минимальную цену
                if position.side == 'long':
                    if not position.max_price or position.current_price > position.max_price:
                        position.max_price = position.current_price
                        
                        # Обновляем трейлинг стоп
                        new_stop = position.max_price * (1 - position.trailing_distance / 100)
                        
                        if not position.stop_loss or new_stop > position.stop_loss:
                            position.stop_loss = new_stop
                            
                            # Обновляем в БД
                            await self._update_trade_stop_loss(trade.id, new_stop)
                            
                            logger.info(
                                f"📈 Трейлинг стоп обновлен для {symbol}",
                                category='position',
                                symbol=symbol,
                                new_stop=new_stop,
                                max_price=position.max_price
                            )
                
                else:  # short position
                    if not position.min_price or position.current_price < position.min_price:
                        position.min_price = position.current_price
                        
                        # Обновляем трейлинг стоп
                        new_stop = position.min_price * (1 + position.trailing_distance / 100)
                        
                        if not position.stop_loss or new_stop < position.stop_loss:
                            position.stop_loss = new_stop
                            
                            # Обновляем в БД
                            await self._update_trade_stop_loss(trade.id, new_stop)
                            
                            logger.info(
                                f"📉 Трейлинг стоп обновлен для {symbol}",
                                category='position',
                                symbol=symbol,
                                new_stop=new_stop,
                                min_price=position.min_price
                            )
                            
            except Exception as e:
                logger.error(f"❌ Ошибка обновления трейлинг стопа для {symbol}: {e}")
    
    async def _check_partial_close(self):
        """Проверка условий для частичного закрытия позиций"""
        for symbol, position in self.positions.items():
            try:
                # Если прибыль достигла порога, закрываем 50% позиции
                if position.unrealized_pnl_percent >= self.partial_close_profit_threshold * 100:
                    trade = self._get_trade_by_symbol(symbol)
                    if trade and not hasattr(trade, 'partial_closed'):
                        
                        partial_size = position.size * 0.5
                        
                        # Частично закрываем позицию
                        close_side = 'sell' if position.side == 'long' else 'buy'
                        
                        result = await self.exchange.create_order(
                            symbol=symbol,
                            order_type='market',
                            side=close_side,
                            amount=partial_size
                        )
                        
                        if result.success:
                            logger.info(
                                f"💰 Частичное закрытие позиции {symbol}: 50%",
                                category='position',
                                symbol=symbol,
                                profit_percent=position.unrealized_pnl_percent
                            )
                            
                            # Помечаем в БД что частично закрыто
                            await self._mark_partial_closed(trade.id)
                
            except Exception as e:
                logger.error(f"❌ Ошибка частичного закрытия {symbol}: {e}")
    
    async def _check_emergency_conditions(self):
        """Проверка экстренных условий"""
        try:
            # Вычисляем общий PnL
            total_pnl = sum(pos.unrealized_pnl for pos in self.positions.values())
            
            # Получаем общий баланс
            balance = await self.exchange.fetch_balance()
            total_balance = balance.get('total', {}).get('USDT', 0)
            
            if total_balance > 0:
                total_drawdown = abs(total_pnl) / total_balance
                
                if total_drawdown >= self.emergency_stop_drawdown:
                    logger.critical(
                        f"🚨 ЭКСТРЕННАЯ ОСТАНОВКА! Просадка: {total_drawdown:.1%}",
                        category='position',
                        total_pnl=total_pnl,
                        total_balance=total_balance,
                        drawdown=total_drawdown
                    )
                    
                    # Закрываем все позиции
                    await self.emergency_close_all()
                    
        except Exception as e:
            logger.error(f"❌ Ошибка проверки экстренных условий: {e}")
    
    async def _update_trades_pnl(self):
        """Обновление PnL сделок в БД"""
        if not self.positions:
            return
        
        db = SessionLocal()
        try:
            for symbol, position in self.positions.items():
                trade = self._get_trade_by_symbol(symbol)
                if trade:
                    trade.current_price = position.current_price
                    trade.unrealized_pnl = position.unrealized_pnl
                    trade.updated_at = datetime.utcnow()
                    
                    db.merge(trade)
            
            db.commit()
            
        except Exception as e:
            logger.error(f"❌ Ошибка обновления PnL в БД: {e}")
        finally:
            db.close()
    
    # =================================================================
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # =================================================================
    
    async def _close_position_with_reason(self, symbol: str, reason: str) -> bool:
        """Закрытие позиции с указанием причины"""
        try:
            success = await self.exchange.close_position(symbol)
            
            if success:
                logger.info(
                    f"✅ Позиция {symbol} закрыта: {reason}",
                    category='position',
                    symbol=symbol,
                    reason=reason
                )
            else:
                logger.error(
                    f"❌ Не удалось закрыть позицию {symbol}: {reason}",
                    category='position',
                    symbol=symbol,
                    reason=reason
                )
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Ошибка закрытия позиции {symbol}: {e}")
            return False
    
    def _get_trade_by_symbol(self, symbol: str) -> Optional[Trade]:
        """Получение сделки по символу"""
        for trade in self.active_trades.values():
            if trade.symbol == symbol:
                return trade
        return None
    
    def _get_trade_id_by_symbol(self, symbol: str) -> Optional[int]:
        """Получение ID сделки по символу"""
        trade = self._get_trade_by_symbol(symbol)
        return trade.id if trade else None
    
    async def _update_trade_stop_loss(self, trade_id: int, new_stop_loss: float):
        """Обновление stop-loss сделки в БД"""
        db = SessionLocal()
        try:
            trade = db.query(Trade).filter(Trade.id == trade_id).first()
            if trade:
                trade.stop_loss = new_stop_loss
                trade.updated_at = datetime.utcnow()
                db.commit()
                
        except Exception as e:
            logger.error(f"❌ Ошибка обновления stop-loss: {e}")
        finally:
            db.close()
    
    async def _mark_partial_closed(self, trade_id: int):
        """Пометить сделку как частично закрытую"""
        db = SessionLocal()
        try:
            trade = db.query(Trade).filter(Trade.id == trade_id).first()
            if trade:
                # Добавляем флаг частичного закрытия
                if not trade.notes:
                    trade.notes = "partial_closed"
                else:
                    trade.notes += ",partial_closed"
                trade.updated_at = datetime.utcnow()
                db.commit()
                
        except Exception as e:
            logger.error(f"❌ Ошибка пометки частичного закрытия: {e}")
        finally:
            db.close()
    
    async def _update_trades_in_db(self, updates: List[TradeUpdate]):
        """Обновление сделок в БД"""
        db = SessionLocal()
        try:
            for update in updates:
                trade = db.query(Trade).filter(Trade.id == update.trade_id).first()
                if trade:
                    trade.status = update.status
                    if update.exit_price:
                        trade.exit_price = update.exit_price
                    if update.profit is not None:
                        trade.profit = update.profit
                    if update.exit_reason:
                        trade.exit_reason = update.exit_reason
                    trade.closed_at = datetime.utcnow()
                    trade.updated_at = datetime.utcnow()
            
            db.commit()
            
            logger.info(
                f"✅ Обновлено сделок в БД: {len(updates)}",
                category='position'
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка обновления сделок в БД: {e}")
        finally:
            db.close()
    
    # =================================================================
    # ПУБЛИЧНЫЕ МЕТОДЫ
    # =================================================================
    
    async def get_positions_summary(self) -> Dict[str, Any]:
        """Получение сводки по позициям"""
        if not self.positions:
            return {
                'total_positions': 0,
                'total_pnl': 0,
                'total_pnl_percent': 0,
                'positions': []
            }
        
        total_pnl = sum(pos.unrealized_pnl for pos in self.positions.values())
        
        # Рассчитываем средний процент PnL
        avg_pnl_percent = sum(pos.unrealized_pnl_percent for pos in self.positions.values()) / len(self.positions)
        
        positions_data = []
        for symbol, pos in self.positions.items():
            positions_data.append({
                'symbol': symbol,
                'side': pos.side,
                'size': pos.size,
                'entry_price': pos.entry_price,
                'current_price': pos.current_price,
                'pnl': pos.unrealized_pnl,
                'pnl_percent': pos.unrealized_pnl_percent,
                'stop_loss': pos.stop_loss,
                'take_profit': pos.take_profit
            })
        
        return {
            'total_positions': len(self.positions),
            'total_pnl': total_pnl,
            'total_pnl_percent': avg_pnl_percent,
            'positions': positions_data
        }
    
    async def emergency_close_all(self) -> bool:
        """Экстренное закрытие всех позиций"""
        try:
            logger.critical("🚨 ЭКСТРЕННОЕ ЗАКРЫТИЕ ВСЕХ ПОЗИЦИЙ!", category='position')
            
            closed_count = await self.exchange.close_all_positions()
            
            if closed_count > 0:
                # Обновляем статус всех активных сделок
                updates = []
                for trade_id in self.active_trades.keys():
                    updates.append(TradeUpdate(
                        trade_id=trade_id,
                        status=TradeStatus.CLOSED,
                        exit_reason="Emergency Stop"
                    ))
                
                await self._update_trades_in_db(updates)
                
                logger.critical(
                    f"🚨 Экстренно закрыто позиций: {closed_count}",
                    category='position'
                )
                
                return True
            
            return False
            
        except Exception as e:
            logger.critical(f"🚨 ОШИБКА ЭКСТРЕННОГО ЗАКРЫТИЯ: {e}", category='position')
            return False
    
    async def set_trailing_stop(self, symbol: str, trailing_distance_percent: float) -> bool:
        """Установка трейлинг стопа для позиции"""
        try:
            trade = self._get_trade_by_symbol(symbol)
            if not trade:
                logger.error(f"❌ Сделка для {symbol} не найдена")
                return False
            
            # Обновляем в БД
            db = SessionLocal()
            try:
                trade.trailing_stop = True
                trade.trailing_distance = trailing_distance_percent
                trade.updated_at = datetime.utcnow()
                db.merge(trade)
                db.commit()
                
                # Обновляем в позиции
                if symbol in self.positions:
                    self.positions[symbol].trailing_stop = True
                    self.positions[symbol].trailing_distance = trailing_distance_percent
                
                logger.info(
                    f"✅ Трейлинг стоп установлен для {symbol}: {trailing_distance_percent}%",
                    category='position',
                    symbol=symbol,
                    trailing_distance=trailing_distance_percent
                )
                
                return True
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"❌ Ошибка установки трейлинг стопа для {symbol}: {e}")
            return False

# Глобальный экземпляр
position_manager = None

def get_position_manager() -> PositionManager:
    """Получить глобальный экземпляр менеджера позиций"""
    global position_manager
    
    if position_manager is None:
        position_manager = PositionManager()
    
    return position_manager

# Экспорты
__all__ = [
    'PositionManager',
    'PositionInfo', 
    'TradeUpdate',
    'get_position_manager'
]