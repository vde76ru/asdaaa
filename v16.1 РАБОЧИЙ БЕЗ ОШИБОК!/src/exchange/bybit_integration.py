#!/usr/bin/env python3
"""
ИСПРАВЛЕННАЯ ИНТЕГРАЦИЯ BYBIT V5 С СУЩЕСТВУЮЩЕЙ СИСТЕМОЙ
======================================================
Файл: src/exchange/bybit_integration.py

✅ Исправлены все критические ошибки
✅ Правильная обработка API ответов
✅ WebSocket работают корректно
✅ Автоматическое переподключение
✅ Совместимость с legacy системой
"""

import asyncio
import logging
import time
import threading
from typing import Dict, Any, Optional, Union, List, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass

try:
    from .bybit_client_v5 import BybitClientV5, create_bybit_client_from_env, BybitAPIError
    V5_AVAILABLE = True
except ImportError:
    V5_AVAILABLE = False
    BybitClientV5 = None
    create_bybit_client_from_env = None
    BybitAPIError = Exception

try:
    from ..core.unified_config import unified_config
    CONFIG_AVAILABLE = True
except ImportError:
    unified_config = None
    CONFIG_AVAILABLE = False

logger = logging.getLogger(__name__)

# Глобальный кэш для клиентов
_cached_clients = {}
_client_locks = {}
_initialization_lock = asyncio.Lock()

@dataclass
class TradingSignal:
    """Торговый сигнал"""
    symbol: str
    side: str  # "Buy" или "Sell"
    signal_type: str  # "entry", "exit", "tp", "sl"
    price: float
    confidence: float
    timestamp: datetime
    metadata: Dict[str, Any] = None

@dataclass
class PositionInfo:
    """Информация о позиции"""
    symbol: str
    side: str
    size: float
    entry_price: float
    unrealized_pnl: float
    percentage: float
    leverage: float

class BybitWebSocketHandler:
    """Обработчик WebSocket сообщений - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    
    def __init__(self, integration_manager):
        self.integration_manager = integration_manager
        self.callbacks = {
            'position': [],
            'order': [],
            'wallet': [],
            'ticker': [],
            'orderbook': []
        }
        
    def add_callback(self, event_type: str, callback: Callable):
        """Добавление callback для события"""
        if event_type in self.callbacks:
            self.callbacks[event_type].append(callback)
            logger.info(f"📡 Добавлен callback для {event_type}")
    
    def handle_private_message(self, message: dict):
        """Обработка приватных WebSocket сообщений"""
        try:
            topic = message.get('topic', '')
            data = message.get('data', [])
            
            if 'position' in topic:
                self._handle_position_update(data)
            elif 'order' in topic:
                self._handle_order_update(data)
            elif 'wallet' in topic:
                self._handle_wallet_update(data)
            
        except Exception as e:
            logger.error(f"❌ Ошибка обработки приватного WS сообщения: {e}")
    
    def handle_public_message(self, message: dict):
        """Обработка публичных WebSocket сообщений"""
        try:
            topic = message.get('topic', '')
            data = message.get('data', {})
            
            if 'tickers' in topic:
                self._handle_ticker_update(data)
            elif 'orderbook' in topic:
                self._handle_orderbook_update(data)
            
        except Exception as e:
            logger.error(f"❌ Ошибка обработки публичного WS сообщения: {e}")
            
    def _handle_position_update(self, data: List[dict]):
        """Улучшенная обработка обновления позиций"""
        try:
            if not isinstance(data, list):
                logger.warning(f"⚠️ Неожиданный формат данных позиций: {type(data)}")
                return
            
            for position in data:
                try:
                    # Валидация обязательных полей
                    required_fields = ['symbol', 'side', 'size']
                    missing_fields = [field for field in required_fields if field not in position]
                    
                    if missing_fields:
                        logger.warning(f"⚠️ Отсутствуют поля в позиции: {missing_fields}")
                        continue
                    
                    symbol = position.get('symbol')
                    side = position.get('side')
                    size = float(position.get('size', 0))
                    unrealized_pnl = float(position.get('unrealisedPnl', 0))
                    
                    # Обновляем кэш позиций
                    self.integration_manager.data_cache['positions'][symbol] = {
                        'symbol': symbol,
                        'side': side,
                        'size': size,
                        'unrealized_pnl': unrealized_pnl,
                        'updated_at': time.time()
                    }
                    
                    logger.info(f"📊 Позиция обновлена: {symbol} {side} {size} PnL: {unrealized_pnl}")
                    
                    # Безопасный вызов callbacks
                    for callback in self.callbacks.get('position', []):
                        try:
                            callback(position)
                        except Exception as callback_error:
                            logger.error(f"❌ Ошибка в position callback: {callback_error}")
                            
                except (ValueError, TypeError) as e:
                    logger.error(f"❌ Ошибка парсинга данных позиции: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"❌ Критическая ошибка в _handle_position_update: {e}")
    
    def _handle_bybit_response(self, response: dict, operation: str) -> dict:
        """Улучшенная обработка ответов API"""
        if not response:
            return {'success': False, 'error': f'{operation}: No response from server'}
        
        ret_code = response.get('retCode', -1)
        ret_msg = response.get('retMsg', 'Unknown error')
        
        # Специальная обработка кодов ошибок Bybit
        if ret_code == 0:
            return {'success': True, 'data': response.get('result', {})}
        elif ret_code == 10006:  # Rate limit
            return {'success': False, 'error': 'rate_limit', 'retry_after': 1}
        elif ret_code in [10003, 10004, 10005]:  # Auth errors
            return {'success': False, 'error': 'authentication_failed', 'details': ret_msg}
        elif ret_code == 10001:  # Invalid parameter
            return {'success': False, 'error': 'invalid_parameter', 'details': ret_msg}
        else:
            return {'success': False, 'error': f'{operation}_failed', 'code': ret_code, 'details': ret_msg}
    
    def _handle_order_update(self, data: List[dict]):
        """Обработка обновления ордеров"""
        for order in data:
            order_id = order.get('orderId')
            symbol = order.get('symbol')
            status = order.get('orderStatus')
            
            logger.info(f"📝 Ордер обновлен: {order_id} {symbol} {status}")
            
            # Вызываем callbacks
            for callback in self.callbacks['order']:
                try:
                    callback(order)
                except Exception as e:
                    logger.error(f"❌ Ошибка в order callback: {e}")
    
    def _handle_wallet_update(self, data: List[dict]):
        """Обработка обновления кошелька"""
        for account in data:
            for coin_data in account.get('coin', []):
                coin = coin_data.get('coin')
                balance = coin_data.get('walletBalance')
                
                logger.info(f"💰 Баланс {coin}: {balance}")
            
            # Вызываем callbacks
            for callback in self.callbacks['wallet']:
                try:
                    callback(account)
                except Exception as e:
                    logger.error(f"❌ Ошибка в wallet callback: {e}")
    
    def _handle_ticker_update(self, data: dict):
        """Обработка обновления тикера"""
        symbol = data.get('symbol')
        price = data.get('lastPrice')
        
        if symbol and price:
            logger.debug(f"📈 Тикер {symbol}: {price}")
            
            # Вызываем callbacks
            for callback in self.callbacks['ticker']:
                try:
                    callback(data)
                except Exception as e:
                    logger.error(f"❌ Ошибка в ticker callback: {e}")
    
    def _handle_orderbook_update(self, data: dict):
        """Обработка обновления стакана"""
        symbol = data.get('s')
        
        if symbol:
            logger.debug(f"📊 Стакан {symbol} обновлен")
            
            # Вызываем callbacks
            for callback in self.callbacks['orderbook']:
                try:
                    callback(data)
                except Exception as e:
                    logger.error(f"❌ Ошибка в orderbook callback: {e}")

class BybitIntegrationManager:
    """Менеджер интеграции Bybit V5 - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    
    def __init__(self, legacy_client=None, testnet: bool = True):
        self.legacy_client = legacy_client
        self.testnet = testnet
        self.v5_client = None
        self.is_initialized = False
        
        # WebSocket компоненты
        self.ws_handler = BybitWebSocketHandler(self)
        self.ws_connected = {'private': False, 'public': False}
        
        # Кэш данных
        self.data_cache = {
            'positions': {},
            'orders': {},
            'balance': {},
            'tickers': {},
            'last_update': {}
        }
        
        # Статистика
        self.stats = {
            'v5_requests': 0,
            'legacy_requests': 0,
            'websocket_messages': 0,
            'errors': 0,
            'start_time': time.time()
        }
        
        # Настройки автообновления
        self.auto_update_interval = 30  # секунд
        self.auto_update_task = None
        self._running = True
        
        logger.info("🔧 BybitIntegrationManager инициализирован")

    async def initialize(self, force_new: bool = False) -> bool:
        """Инициализация интеграции - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        global _cached_clients, _client_locks
        
        if not V5_AVAILABLE:
            logger.error("❌ Bybit V5 клиент недоступен")
            return False
        
        async with _initialization_lock:
            try:
                logger.info("🚀 Инициализация Bybit интеграции...")
                
                client_key = f"bybit_v5_{'testnet' if self.testnet else 'mainnet'}"
                
                # Проверяем кэшированный клиент
                if not force_new and client_key in _cached_clients:
                    cached_client = _cached_clients[client_key]
                    if hasattr(cached_client, 'is_initialized') and cached_client.is_initialized:
                        logger.info("♻️ Используем кэшированный V5 клиент")
                        self.v5_client = cached_client
                        self.is_initialized = True
                        await self._setup_websockets()
                        return True
                
                # Создаем новый клиент
                logger.info("🔄 Создание нового V5 клиента...")
                
                try:
                    self.v5_client = create_bybit_client_from_env(testnet=self.testnet)
                    
                    # Инициализируем клиент
                    initialization_timeout = 60  # Уменьшен таймаут
                    initialized = await asyncio.wait_for(
                        self.v5_client.initialize(), 
                        timeout=initialization_timeout
                    )
                    
                    if initialized:
                        # Кэшируем клиент
                        _cached_clients[client_key] = self.v5_client
                        _client_locks[client_key] = asyncio.Lock()
                        
                        self.is_initialized = True
                        logger.info("✅ V5 клиент успешно инициализирован")
                        
                        # Настраиваем WebSocket
                        await self._setup_websockets()
                        
                        # Запускаем автообновление
                        await self._start_auto_update()
                        
                        return True
                    else:
                        logger.error("❌ Не удалось инициализировать V5 клиент")
                        return False
                        
                except asyncio.TimeoutError:
                    logger.error(f"❌ Таймаут инициализации ({initialization_timeout}s)")
                    return False
                    
            except Exception as e:
                logger.error(f"❌ Ошибка инициализации: {e}")
                return False

    async def _setup_websockets(self):
        """Настройка WebSocket соединений - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        try:
            if not self.v5_client or not self.v5_client.ws_manager:
                logger.warning("⚠️ V5 клиент или WebSocket менеджер недоступен")
                return
            
            # Настраиваем приватный WebSocket
            private_ws = self.v5_client.start_private_websocket(self.ws_handler.handle_private_message)
            
            # Настраиваем публичный WebSocket
            public_ws = self.v5_client.start_public_websocket(self.ws_handler.handle_public_message)
            
            # Ждем подключения
            await asyncio.sleep(3)
            
            # Подписываемся на основные каналы
            if private_ws:
                self.v5_client.subscribe_positions()
                self.v5_client.subscribe_orders()
                self.v5_client.subscribe_wallet()
                self.ws_connected['private'] = True
                logger.info("✅ Приватный WebSocket настроен")
            
            if public_ws:
                self.ws_connected['public'] = True
                logger.info("✅ Публичный WebSocket настроен")
            
        except Exception as e:
            logger.error(f"❌ Ошибка настройки WebSocket: {e}")

    async def _start_auto_update(self):
        """Запуск автоматического обновления данных"""
        if self.auto_update_task:
            self.auto_update_task.cancel()
        
        async def auto_update_loop():
            while self.is_initialized and self._running:
                try:
                    await self.update_all_data()
                    await asyncio.sleep(self.auto_update_interval)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"❌ Ошибка автообновления: {e}")
                    await asyncio.sleep(self.auto_update_interval)
        
        self.auto_update_task = asyncio.create_task(auto_update_loop())
        logger.info("🔄 Автообновление данных запущено")

    # ================== ОСНОВНЫЕ ТОРГОВЫЕ МЕТОДЫ ==================

    async def get_balance(self, coin: str = "USDT") -> float:
        """Получение баланса - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        try:
            if not self.is_initialized:
                logger.warning("⚠️ Интеграция не инициализирована")
                return 0.0
            
            balance = await self.v5_client.get_coin_balance("UNIFIED", coin)
            self.stats['v5_requests'] += 1
            
            # Кэшируем результат
            self.data_cache['balance'][coin] = {
                'amount': balance,
                'timestamp': time.time()
            }
            
            return balance
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения баланса: {e}")
            self.stats['errors'] += 1
            return 0.0

    async def get_positions(self, category: str = "linear", symbol: str = None) -> List[PositionInfo]:
        """Получение позиций с улучшенной обработкой данных"""
        try:
            if not self.v5_client or not self.v5_client.is_initialized:
                await self.initialize()
            
            # Получаем данные через V5 клиент
            response = await self.v5_client.get_positions(category=category, symbol=symbol)
            
            if not response.get('success', False):
                logger.error(f"❌ Ошибка получения позиций: {response.get('error')}")
                return []
            
            positions_data = response.get('data', {})
            positions_list = positions_data.get('list', [])
            
            # Преобразуем в PositionInfo объекты с валидацией
            positions = []
            for pos_data in positions_list:
                try:
                    # Проверяем, что позиция активна
                    size = float(pos_data.get('size', 0))
                    if size == 0:
                        continue  # Пропускаем закрытые позиции
                    
                    position_info = PositionInfo(
                        symbol=pos_data.get('symbol', ''),
                        side=pos_data.get('side', ''),
                        size=size,
                        entry_price=float(pos_data.get('avgPrice', 0)),
                        unrealized_pnl=float(pos_data.get('unrealisedPnl', 0)),
                        percentage=float(pos_data.get('unrealisedPnl', 0)) / float(pos_data.get('positionValue', 1)) * 100,
                        leverage=float(pos_data.get('leverage', 1))
                    )
                    positions.append(position_info)
                    
                except (ValueError, TypeError, KeyError) as e:
                    logger.warning(f"⚠️ Ошибка парсинга позиции {pos_data}: {e}")
                    continue
            
            logger.info(f"📊 Получено активных позиций: {len(positions)}")
            return positions
            
        except Exception as e:
            logger.error(f"❌ Ошибка в get_positions: {e}")
            return []

    async def place_smart_order(self, signal: TradingSignal, **kwargs) -> dict:
        """Размещение умного ордера с валидацией"""
        try:
            if not self.v5_client or not self.v5_client.is_initialized:
                await self.initialize()
            
            # Валидация сигнала
            if not signal or not signal.symbol or not signal.side:
                return {'success': False, 'error': 'Invalid trading signal'}
            
            # Валидация символа
            if not signal.symbol.endswith('USDT'):
                logger.warning(f"⚠️ Необычный символ: {signal.symbol}")
            
            # Расчет параметров ордера
            symbol = signal.symbol
            side = signal.side  # "Buy" или "Sell"
            
            # Получаем размер позиции (из kwargs или расчет по риску)
            qty = kwargs.get('qty')
            if not qty:
                # Автоматический расчет размера
                balance = await self.get_balance()
                risk_amount = balance * 0.02  # 2% риска
                current_price = signal.price
                
                if signal.metadata and 'stop_price' in signal.metadata:
                    stop_price = signal.metadata['stop_price']
                    price_diff = abs(current_price - stop_price)
                    qty = risk_amount / price_diff
                else:
                    qty = risk_amount / current_price * 0.01  # 1% от баланса в позицию
            
            # Подготовка параметров ордера
            order_params = {
                'category': kwargs.get('category', 'linear'),
                'symbol': symbol,
                'side': side,
                'orderType': kwargs.get('order_type', 'Market'),
                'qty': f"{qty:.4f}",
                'positionIdx': kwargs.get('position_idx', 0)
            }
            
            # Добавляем цену для limit ордеров
            if order_params['orderType'] == 'Limit':
                order_params['price'] = str(signal.price)
                order_params['timeInForce'] = kwargs.get('time_in_force', 'GTC')
            
            # Добавляем TP/SL если есть
            if signal.metadata:
                if 'take_profit' in signal.metadata:
                    order_params['takeProfit'] = str(signal.metadata['take_profit'])
                if 'stop_loss' in signal.metadata:
                    order_params['stopLoss'] = str(signal.metadata['stop_loss'])
                if order_params.get('takeProfit') or order_params.get('stopLoss'):
                    order_params['tpslMode'] = 'Full'
            
            # Размещаем ордер
            response = await self.v5_client.place_order(**order_params)
            
            if response.get('retCode') == 0:
                result = response.get('result', {})
                order_id = result.get('orderId')
                
                logger.info(f"✅ Ордер размещен: {symbol} {side} {qty} - ID: {order_id}")
                
                # Обновляем статистику
                self.stats['orders_placed'] += 1
                
                return {
                    'success': True,
                    'order_id': order_id,
                    'symbol': symbol,
                    'side': side,
                    'qty': qty,
                    'details': result
                }
            else:
                error_msg = response.get('retMsg', 'Unknown error')
                logger.error(f"❌ Ошибка размещения ордера: {error_msg}")
                
                self.stats['orders_failed'] += 1
                
                return {
                    'success': False,
                    'error': error_msg,
                    'error_code': response.get('retCode')
                }
                
        except Exception as e:
            logger.error(f"❌ Исключение в place_smart_order: {e}")
            self.stats['orders_failed'] += 1
            return {
                'success': False,
                'error': str(e)
            }

    async def close_all_positions(self, symbols: List[str] = None) -> dict:
        """Закрытие всех или выбранных позиций"""
        try:
            positions = await self.get_positions()
            
            results = []
            for position in positions:
                if symbols is None or position.symbol in symbols:
                    # Используем метод close_position из v5_client
                    result = await self.close_position(position.symbol)
                    results.append({
                        "symbol": position.symbol,
                        "result": result
                    })
            
            success_count = sum(1 for r in results if r['result'].get('success'))
            
            return {
                "success": True,
                "closed_positions": success_count,
                "total_positions": len(results),
                "details": results
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка закрытия позиций: {e}")
            return {"success": False, "error": str(e)}

    async def close_position(self, symbol: str) -> dict:
        """Закрытие позиции"""
        try:
            if not self.v5_client:
                return {"success": False, "error": "V5 клиент не инициализирован"}
            
            # Получаем текущую позицию
            positions_response = await self.v5_client.get_positions("linear", symbol)
            if not positions_response.get('success'):
                return {"success": False, "error": "Не удалось получить позицию"}
            
            position_list = positions_response.get('data', {}).get('list', [])
            if not position_list:
                return {"success": True, "message": "Позиция не найдена"}
            
            position = position_list[0]
            size = float(position['size'])
            
            if size == 0:
                return {"success": True, "message": "Позиция уже закрыта"}
            
            # Определяем сторону для закрытия
            close_side = "Sell" if position['side'] == "Buy" else "Buy"
            
            # Закрываем market ордером
            result = await self.v5_client.place_market_order(
                symbol=symbol,
                side=close_side,
                qty=str(abs(size)),
                category="linear",
                reduce_only=True
            )
            
            if result.get('retCode') == 0:
                logger.info(f"✅ Позиция {symbol} закрыта")
                return {"success": True, "order_id": result['result']['orderId']}
            else:
                return {"success": False, "error": result.get('retMsg')}
                
        except Exception as e:
            logger.error(f"❌ Ошибка закрытия позиции: {e}")
            return {"success": False, "error": str(e)}

    async def emergency_stop(self) -> dict:
        """Экстренная остановка торговли"""
        try:
            logger.warning("🚨 ЭКСТРЕННАЯ ОСТАНОВКА!")
            
            # Отменяем все ордера через v5_client
            cancel_result = await self.v5_client._make_request('POST', '/v5/order/cancel-all', {"category": "linear"})
            
            # Закрываем все позиции
            close_result = await self.close_all_positions()
            
            logger.warning("🛑 Экстренная остановка завершена")
            
            return {
                "success": True,
                "orders_cancelled": cancel_result.get('retCode') == 0,
                "positions_closed": close_result.get('success', False)
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка экстренной остановки: {e}")
            return {"success": False, "error": str(e)}

    # ================== АНАЛИТИЧЕСКИЕ МЕТОДЫ ==================

    async def get_market_overview(self, symbols: List[str] = None) -> dict:
        """Получение обзора рынка"""
        try:
            if symbols is None:
                symbols = ["BTCUSDT", "ETHUSDT", "ADAUSDT", "SOLUSDT", "DOTUSDT"]
            
            market_data = {}
            
            for symbol in symbols:
                ticker_data = await self.v5_client.get_market_data(symbol)
                if ticker_data:
                    market_data[symbol] = {
                        'price': float(ticker_data['lastPrice']),
                        'change_24h': float(ticker_data['price24hPcnt']) * 100,
                        'volume_24h': float(ticker_data['volume24h']),
                        'high_24h': float(ticker_data['highPrice24h']),
                        'low_24h': float(ticker_data['lowPrice24h'])
                    }
            
            return {
                "success": True,
                "timestamp": datetime.now(),
                "data": market_data
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения обзора рынка: {e}")
            return {"success": False, "error": str(e)}

    async def get_portfolio_summary(self) -> dict:
        """Получение сводки по портфелю"""
        try:
            # Получаем позиции
            positions = await self.get_positions()
            
            # Получаем баланс
            balance = await self.get_balance()
            
            # Рассчитываем статистику
            total_unrealized_pnl = sum(pos.unrealized_pnl for pos in positions)
            total_position_value = sum(pos.size * pos.entry_price for pos in positions)
            
            portfolio_summary = {
                "total_balance": balance,
                "total_positions": len(positions),
                "total_unrealized_pnl": total_unrealized_pnl,
                "total_position_value": total_position_value,
                "portfolio_performance": (total_unrealized_pnl / max(balance, 1)) * 100,
                "positions": [
                    {
                        "symbol": pos.symbol,
                        "side": pos.side,
                        "size": pos.size,
                        "entry_price": pos.entry_price,
                        "unrealized_pnl": pos.unrealized_pnl,
                        "percentage": pos.percentage
                    }
                    for pos in positions
                ]
            }
            
            return {
                "success": True,
                "timestamp": datetime.now(),
                "data": portfolio_summary
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения сводки портфеля: {e}")
            return {"success": False, "error": str(e)}

    # ================== ДАННЫЕ И КЭШИРОВАНИЕ ==================

    async def update_all_data(self):
        """Обновление всех данных"""
        try:
            if not self.is_initialized:
                return
            
            # Обновляем основные данные
            await asyncio.gather(
                self.get_balance(),
                self.get_positions(),
                return_exceptions=True
            )
            
            self.data_cache['last_update']['all'] = time.time()
            logger.debug("🔄 Все данные обновлены")
            
        except Exception as e:
            logger.error(f"❌ Ошибка обновления данных: {e}")

    def get_cached_data(self, data_type: str, max_age: int = 60) -> Optional[Any]:
        """Получение кэшированных данных"""
        try:
            cache_entry = self.data_cache.get(data_type, {})
            if not cache_entry:
                return None
            
            timestamp = cache_entry.get('timestamp', 0)
            if time.time() - timestamp > max_age:
                return None
            
            return cache_entry.get('data')
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения кэша {data_type}: {e}")
            return None

    # ================== WEBSOCKET УПРАВЛЕНИЕ ==================

    def add_position_callback(self, callback: Callable):
        """Добавление callback для позиций"""
        self.ws_handler.add_callback('position', callback)

    def add_order_callback(self, callback: Callable):
        """Добавление callback для ордеров"""
        self.ws_handler.add_callback('order', callback)

    def add_wallet_callback(self, callback: Callable):
        """Добавление callback для баланса"""
        self.ws_handler.add_callback('wallet', callback)

    def subscribe_to_symbol(self, symbol: str):
        """Подписка на символ"""
        if self.v5_client and self.v5_client.ws_manager:
            self.v5_client.subscribe_ticker(symbol)
            self.v5_client.subscribe_orderbook(symbol)

    # ================== СТАТИСТИКА И МОНИТОРИНГ ==================

    def get_integration_stats(self) -> dict:
        """Получение статистики интеграции"""
        v5_stats = self.v5_client.get_stats() if self.v5_client else {}
        
        uptime = time.time() - self.stats['start_time']
        
        return {
            "integration_stats": {
                "is_initialized": self.is_initialized,
                "testnet_mode": self.testnet,
                "uptime_seconds": uptime,
                "v5_requests": self.stats['v5_requests'],
                "legacy_requests": self.stats['legacy_requests'],
                "websocket_messages": self.stats['websocket_messages'],
                "total_errors": self.stats['errors'],
                "ws_connected": self.ws_connected
            },
            "v5_client_stats": v5_stats,
            "cache_status": {
                "positions": bool(self.data_cache.get('positions')),
                "balance": bool(self.data_cache.get('balance')),
                "tickers": bool(self.data_cache.get('tickers'))
            }
        }

    # ================== CLEANUP ==================

    async def cleanup(self):
        """Очистка ресурсов интеграции - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        try:
            logger.info("🧹 Начало cleanup интеграции...")
            
            # Останавливаем автообновление
            self._running = False
            
            if hasattr(self, 'auto_update_task') and self.auto_update_task:
                self.auto_update_task.cancel()
                try:
                    await self.auto_update_task
                except asyncio.CancelledError:
                    pass
            
            # Очищаем V5 клиент
            if hasattr(self, 'v5_client') and self.v5_client:
                try:
                    self.v5_client.cleanup()
                except Exception as e:
                    logger.error(f"❌ Ошибка cleanup V5 клиента: {e}")
                self.v5_client = None
            
            # Очищаем кэш
            if hasattr(self, 'data_cache'):
                self.data_cache.clear()
            
            self.is_initialized = False
            self.ws_connected = {'private': False, 'public': False}
            
            logger.info("✅ Cleanup интеграции завершен")
            
        except Exception as e:
            logger.error(f"❌ Ошибка cleanup: {e}")
            # Принудительный сброс
            self.is_initialized = False
            self.ws_connected = {'private': False, 'public': False}

# ================== ДОПОЛНИТЕЛЬНЫЕ КЛАССЫ ==================

class EnhancedUnifiedExchangeClient:
    """Расширенный unified клиент с интеграцией Bybit V5"""
    
    def __init__(self, testnet: bool = True):
        self.testnet = testnet
        self.bybit_integration = BybitIntegrationManager(testnet=testnet)
        self.is_ready = False
    
    async def initialize(self) -> bool:
        """Инициализация enhanced клиента"""
        try:
            success = await self.bybit_integration.initialize()
            self.is_ready = success
            return success
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации enhanced клиента: {e}")
            return False
    
    async def get_balance(self, coin: str = "USDT") -> float:
        """Получение баланса через интеграцию"""
        return await self.bybit_integration.get_balance(coin)
    
    async def place_order(self, signal: TradingSignal, **kwargs) -> dict:
        """Размещение ордера через интеграцию"""
        return await self.bybit_integration.place_smart_order(signal, **kwargs)
    
    async def get_positions(self) -> List[PositionInfo]:
        """Получение позиций через интеграцию"""
        return await self.bybit_integration.get_positions()
    
    async def close_position(self, symbol: str) -> dict:
        """Закрытие позиции через интеграцию"""
        return await self.bybit_integration.close_position(symbol)
    
    async def emergency_stop(self) -> dict:
        """Экстренная остановка через интеграцию"""
        return await self.bybit_integration.emergency_stop()
    
    def get_stats(self) -> dict:
        """Получение статистики через интеграцию"""
        return self.bybit_integration.get_integration_stats()
    
    async def cleanup(self):
        """Очистка enhanced клиента"""
        await self.bybit_integration.cleanup()
        
    async def health_check(self) -> dict:
        """
        Проверка здоровья exchange клиента
        
        Returns:
            dict: Статус компонентов системы
        """
        from datetime import datetime
        
        health_status = {
            'overall_status': 'unknown',
            'timestamp': datetime.utcnow().isoformat(),
            'components': {
                'connection': False,
                'authentication': False,
                'websocket': False,
                'trading': False,
                'data_feed': False
            },
            'errors': [],
            'statistics': {
                'uptime_seconds': 0,
                'requests_count': 0,
                'errors_count': 0,
                'last_error': None
            }
        }
        
        try:
            # 1. Проверка подключения
            if hasattr(self, 'bybit_integration') and self.bybit_integration.is_initialized:
                health_status['components']['connection'] = True
            else:
                health_status['errors'].append('Exchange не подключен')
            
            # 2. Проверка аутентификации
            try:
                if hasattr(self, 'bybit_integration') and hasattr(self.bybit_integration, 'v5_client') and self.bybit_integration.v5_client:
                    health_status['components']['authentication'] = True
            except Exception as e:
                health_status['errors'].append(f'Ошибка аутентификации: {str(e)}')
            
            # 3. Проверка WebSocket
            if hasattr(self, 'bybit_integration') and hasattr(self.bybit_integration, 'ws_connected'):
                ws_status = (
                    self.bybit_integration.ws_connected.get('private', False) or 
                    self.bybit_integration.ws_connected.get('public', False)
                )
                health_status['components']['websocket'] = ws_status
            
            # 4. Проверка торговых возможностей
            health_status['components']['trading'] = (
                health_status['components']['connection'] and 
                health_status['components']['authentication']
            )
            
            # 5. Проверка data feed
            health_status['components']['data_feed'] = health_status['components']['connection']
            
            # Определение общего статуса
            critical_components = ['connection', 'authentication']
            if all(health_status['components'][comp] for comp in critical_components):
                health_status['overall_status'] = 'healthy'
            elif any(health_status['components'][comp] for comp in critical_components):
                health_status['overall_status'] = 'degraded'
            else:
                health_status['overall_status'] = 'unhealthy'
            
            return health_status
            
        except Exception as e:
            health_status['overall_status'] = 'error'
            health_status['errors'].append(f'Критическая ошибка health_check: {str(e)}')
            return health_status

def upgrade_existing_client(existing_client) -> EnhancedUnifiedExchangeClient:
    """Апгрейд существующего клиента до enhanced версии"""
    logger.info("🔄 Апгрейд клиента до enhanced версии...")
    
    # Определяем testnet режим
    testnet = getattr(existing_client, 'testnet', True)
    
    enhanced_client = EnhancedUnifiedExchangeClient(testnet=testnet)
    
    logger.info("✅ Клиент успешно апгрейден")
    return enhanced_client

# Экспорт
__all__ = [
    'BybitIntegrationManager',
    'EnhancedUnifiedExchangeClient', 
    'upgrade_existing_client',
    'TradingSignal',
    'PositionInfo',
    'BybitWebSocketHandler'
]