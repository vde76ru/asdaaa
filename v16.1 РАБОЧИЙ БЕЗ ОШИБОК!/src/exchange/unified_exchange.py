"""
ЕДИНЫЙ КЛИЕНТ БИРЖИ - Объединение всех exchange модулей
======================================================

Объединяет функциональность из:
- client.py
- real_client.py

Файл: src/exchange/unified_exchange.py
"""

import asyncio
import ccxt
import json
import logging
import random
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
import pandas as pd
import urllib3
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

try:
    from ..core.unified_config import unified_config
    UNIFIED_CONFIG_AVAILABLE = True
except ImportError:
    unified_config = None
    UNIFIED_CONFIG_AVAILABLE = False

# ✅ ИСПРАВЛЕН ИМПОРТ ЛОГГЕРА - принудительный fallback
import logging
logger = logging.getLogger('crypto_bot')



# =================================================================
# БАЗОВЫЕ КЛАССЫ И ИНТЕРФЕЙСЫ (из client.py)
# =================================================================

# Кастомный адаптер для увеличенного пула соединений
class CustomHTTPAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        kwargs['maxsize'] = 50  # Увеличиваем с 10 до 50
        return super().init_poolmanager(*args, **kwargs)

class BaseExchangeClient(ABC):
    """
    Базовый абстрактный класс для всех клиентов бирж
    Из: client.py
    """
    
    def __init__(self):
        self.exchange = None
        self.is_connected = False
        self.last_request_time = None
        self.rate_limiter = {}
        
    @abstractmethod
    async def connect(self) -> bool:
        """Подключение к бирже"""
        pass
    
    @abstractmethod
    async def disconnect(self) -> bool:
        """Отключение от биржи"""
        pass
    
    # @abstractmethod
    # async def get_balance(self) -> Dict[str, Any]:
    #     """Получение баланса"""
    #     pass
    
    @abstractmethod
    async def place_order(self, symbol: str, side: str, amount: float, price: float = None, order_type: str = 'market') -> Dict[str, Any]:
        """Размещение ордера"""
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """Отмена ордера"""
        pass
    
    @abstractmethod
    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """Получение тикера"""
        pass
    
    @abstractmethod
    async def get_order_book(self, symbol: str, limit: int = 20) -> Dict[str, Any]:
        """Получение стакана заявок"""
        pass
    
    def _check_rate_limit(self, endpoint: str) -> bool:
        """Проверка лимита запросов"""
        current_time = datetime.utcnow()
        
        if endpoint not in self.rate_limiter:
            self.rate_limiter[endpoint] = []
        
        # Удаляем старые запросы (старше минуты)
        minute_ago = current_time - timedelta(minutes=1)
        self.rate_limiter[endpoint] = [
            req_time for req_time in self.rate_limiter[endpoint] 
            if req_time > minute_ago
        ]
        
        # Проверяем лимит (max 60 запросов в минуту)
        if len(self.rate_limiter[endpoint]) >= 60:
            return False
        
        # Добавляем текущий запрос
        self.rate_limiter[endpoint].append(current_time)
        return True
    
    async def _wait_for_rate_limit(self, endpoint: str):
        """Ожидание для соблюдения лимита запросов"""
        while not self._check_rate_limit(endpoint):
            await asyncio.sleep(1)

# =================================================================
# ОСНОВНОЙ ОБЪЕДИНЕННЫЙ КЛИЕНТ
# =================================================================

class UnifiedExchangeClient(BaseExchangeClient):
    """
    Единый клиент для всех бирж
    Объединяет функциональность из client.py + real_client.py
    """
    
    def __init__(self):
        super().__init__()
        self.exchange = None
        self.is_connected = False
        self.supported_exchanges = ['bybit', 'binance', 'okx']
        self.current_exchange = 'bybit'  # По умолчанию Bybit
        self.markets = {}
        self.last_price_update = {}
        self.connection_attempts = 0
        self.max_connection_attempts = 3
        self._session = None
        self._setup_connection_pool()
        
        
        
        # ✅ ИСПРАВЛЕНО: Безопасное логирование
        try:
            logger.info("🔗 UnifiedExchangeClient инициализирован")
        except:
            print("INFO: 🔗 UnifiedExchangeClient инициализирован")
        
    # =================================================================
    # МЕТОДЫ ПОДКЛЮЧЕНИЯ (из real_client.py)
    # =================================================================
    
    def _setup_connection_pool(self):
        """Настройка пула соединений для CCXT"""
        try:
            # Создаем сессию с увеличенным пулом
            import requests
            session = requests.Session()
            
            # Настраиваем адаптер с retry политикой
            retry_strategy = Retry(
                total=3,
                backoff_factor=0.3,
                status_forcelist=[429, 500, 502, 503, 504],
            )
            
            adapter = CustomHTTPAdapter(
                pool_connections=20,
                pool_maxsize=50,
                max_retries=retry_strategy
            )
            
            session.mount("http://", adapter)
            session.mount("https://", adapter)
            
            self._session = session
            logger.info("✅ Пул соединений настроен: maxsize=50")
            
        except Exception as e:
            logger.warning(f"⚠️ Не удалось настроить пул соединений: {e}")

    async def connect(self, exchange_name: str = 'bybit', testnet: bool = True) -> bool:
        # Применяем кастомную сессию если доступна
        if self._session and hasattr(self.exchange, 'session'):
            self.exchange.session = self._session
            logger.info("✅ Применена кастомная сессия к exchange")
        
        # Также применяем настройки rate limit
        if hasattr(self.exchange, 'rateLimit'):
            self.exchange.rateLimit = 100  # миллисекунды между запросами
            self.exchange.enableRateLimit = True
            logger.info("✅ Rate limit установлен: 100ms")
        """
        Подключение к реальной бирже
        Из: real_client.py
        """
        try:
            # Проверяем что уже не подключены (избегаем повторных подключений)
            if self.is_connected and self.exchange:
                try:
                    logger.info("✅ Уже подключен к бирже", category='exchange')
                except:
                    print("INFO: ✅ Уже подключен к бирже")
                return True
            
            self.current_exchange = exchange_name.lower()
            
            if self.current_exchange == 'bybit':
                return await self._connect_bybit(testnet)
            elif self.current_exchange == 'binance':
                return await self._connect_binance(testnet)
            elif self.current_exchange == 'okx':
                return await self._connect_okx(testnet)
            else:
                try:
                    logger.error(f"❌ Неподдерживаемая биржа: {exchange_name}")
                except:
                    print(f"ERROR: ❌ Неподдерживаемая биржа: {exchange_name}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к {exchange_name}: {e}")
            self.connection_attempts += 1
            
            if self.connection_attempts < self.max_connection_attempts:
                logger.info(f"🔄 Повторная попытка подключения ({self.connection_attempts}/{self.max_connection_attempts})")
                await asyncio.sleep(5)
                return await self.connect(exchange_name, testnet)
            
            return False
    
    async def _connect_bybit(self, testnet: bool = True) -> bool:
        """Подключение к Bybit с улучшенной обработкой ошибок"""
        import os
        import time
        import random
        import logging
        
        # ✅ ИСПРАВЛЕНО: Создаем локальный logger для метода
        method_logger = logging.getLogger('crypto_bot')
        
        def safe_log(level, message):
            """Безопасное логирование с fallback на print"""
            try:
                getattr(method_logger, level)(message)
            except Exception:
                print(f"{level.upper()}: {message}")
        
        for attempt in range(self.max_connection_attempts):
            try:
                # ✅ ИСПРАВЛЕНО: Правильная проверка конфигурации
                if UNIFIED_CONFIG_AVAILABLE and unified_config:
                    try:
                        config = unified_config.get_bybit_exchange_config()
                        safe_log('info', "📋 Конфигурация получена из unified_config")
                    except Exception as e:
                        safe_log('warning', f"⚠️ Ошибка получения конфигурации из unified_config: {e}")
                        # Fallback конфигурация из unified_config
                        config = {
                            'apiKey': getattr(unified_config, 'BYBIT_API_KEY', ''),
                            'secret': getattr(unified_config, 'BYBIT_API_SECRET', ''),
                            'enableRateLimit': True,
                            'rateLimit': 100
                        }
                else:
                    # Конфигурация из переменных окружения
                    safe_log('info', "📋 Получаем конфигурацию из переменных окружения")
                    config = {
                        'apiKey': os.getenv('BYBIT_TESTNET_API_KEY' if testnet else 'BYBIT_MAINNET_API_KEY', 
                                           os.getenv('BYBIT_API_KEY', '')),
                        'secret': os.getenv('BYBIT_TESTNET_API_SECRET' if testnet else 'BYBIT_MAINNET_API_SECRET',
                                           os.getenv('BYBIT_API_SECRET', '')),
                        'enableRateLimit': True,
                        'rateLimit': 100
                    }
                
                # ✅ ОБЯЗАТЕЛЬНЫЕ НАСТРОЙКИ
                config['sandbox'] = testnet
                config['timeout'] = 30000  # 30 секунд
                config['rateLimit'] = 100  # Снижаем частоту запросов
                
                # ✅ УЛУЧШЕННЫЕ НАСТРОЙКИ ПОДКЛЮЧЕНИЯ
                config['options'] = {
                    **config.get('options', {}),
                    'adjustForTimeDifference': True,
                    'recvWindow': 10000,  # Увеличиваем окно
                    'fetchCurrencies': False,  # Отключаем загрузку валют (проблемная операция)
                    'fetchFundingHistory': False,
                    'fetchOHLCV': 'emulated',
                    'defaultType': 'spot'
                }
                
                # Дополнительные настройки для стабильности
                config['headers'] = {
                    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
                    'Accept': 'application/json',
                    'Connection': 'keep-alive'
                }
                
                # ✅ ПРОВЕРЯЕМ API КЛЮЧИ
                if not config['apiKey'] or not config['secret']:
                    safe_log('error', "❌ API ключи Bybit не найдены")
                    return False
                    
                safe_log('info', f"🔄 Попытка подключения к Bybit #{attempt + 1}/{self.max_connection_attempts}")
                safe_log('info', f"🔐 API Key: {config['apiKey'][:8]}..." if config['apiKey'] else "🔐 API Key: НЕ НАЙДЕН")
                
                # ✅ СОЗДАЕМ EXCHANGE ОБЪЕКТ
                self.exchange = ccxt.bybit(config)
                
                # ✅ ПОЭТАПНАЯ ЗАГРУЗКА С ПРОВЕРКАМИ
                safe_log('info', "📡 Тестируем соединение...")
                
                # Сначала простой ping
                try:
                    # ✅ ИСПРАВЛЕНО: Убираем await для синхронной функции
                    def ping_sync():
                                return self.exchange.fetch_time()
                    
                    await asyncio.get_event_loop().run_in_executor(None, self.exchange.fetch_time)
                    safe_log('info', "✅ Ping успешный")
                except Exception as ping_error:
                    safe_log('warning', f"⚠️ Ping ошибка: {ping_error}")
                    if self.exchange:
                        self.exchange = None
                    continue
                
                # Теперь загружаем рынки БЕЗ валют
                safe_log('info', "📊 Загружаем торговые пары...")
                try:
                    # ✅ ИСПРАВЛЕНО: Убираем await для синхронной функции
                    def load_markets_sync():
                        return self.exchange.load_markets(reload=False)
                    
                    markets = await asyncio.get_event_loop().run_in_executor(
                        None, 
                        self.exchange.load_markets, 
                        False  # reload параметр
                    )
                    
                    if not markets:
                        raise Exception("Получен пустой список рынков")
                        
                    self.markets = markets
                    self.is_connected = True
                    self.connection_attempts = 0  # Сбрасываем счетчик при успехе
                    
                    safe_log('info', f"✅ Подключение к Bybit установлено (testnet: {testnet}, markets: {len(markets)})")
                    
                    # ✅ ДОПОЛНИТЕЛЬНАЯ ПРОВЕРКА БАЛАНСА
                    try:
                        try:
                            balance_test = await asyncio.wait_for(
                                asyncio.get_event_loop().run_in_executor(
                                    None, 
                                    self.exchange.fetch_balance
                                ), 
                                timeout=10
                            )
                            logger.info("✅ Проверка баланса успешна")
                        except Exception as balance_error:
                            logger.warning(f"⚠️ Проверка баланса не удалась: {balance_error}")
                            # Не прерываем подключение - баланс может быть недоступен по разным причинам
                        safe_log('info', "✅ Проверка баланса успешна")
                    except Exception as balance_error:
                        safe_log('warning', f"⚠️ Проверка баланса не удалась: {balance_error}")
                        # Не прерываем подключение - баланс может быть недоступен по разным причинам
                    
                    return True
                    
                except asyncio.TimeoutError:
                    safe_log('warning', f"⚠️ Timeout загрузки рынков на попытке {attempt + 1}")
                    if self.exchange:
                        self.exchange = None
                    continue
                except Exception as market_error:
                    safe_log('warning', f"⚠️ Ошибка загрузки рынков: {market_error}")
                    if self.exchange:
                        self.exchange = None
                    continue
                    
            except Exception as e:
                safe_log('error', f"❌ Ошибка подключения к bybit: {e}")
                if self.exchange:
                    self.exchange = None
                
                if attempt < self.max_connection_attempts - 1:
                    delay = 5 + (attempt * 2)  # Увеличиваем задержку с каждой попыткой
                    safe_log('info', f"🔄 Повторная попытка через {delay} секунд...")
                    await asyncio.sleep(delay)
                    continue
        
        # ✅ ВСЕ ПОПЫТКИ ИСЧЕРПАНЫ
        safe_log('error', f"❌ Не удалось подключиться к Bybit после {self.max_connection_attempts} попыток")
        self.is_connected = False
        self.exchange = None
        return False
        
    async def _connect_binance(self, testnet: bool = True) -> bool:
        """Подключение к Binance"""
        try:
            self.exchange = ccxt.binance({
                'apiKey': unified_config.BINANCE_API_KEY,
                'secret': unified_config.BINANCE_API_SECRET,
                'sandbox': testnet,
                'enableRateLimit': True,
                'rateLimit': 50,
                'options': {
                    'defaultType': 'spot',
                    'adjustForTimeDifference': True
                }
            })
            
            markets = await self.exchange.load_markets()
            self.markets = markets
            self.is_connected = True
            
            # Инициализируем V5 интеграцию - ДОБАВЛЕНО
            try:
                await self.initialize_v5_integration()
            except Exception as e:
                logger.warning(f"⚠️ V5 интеграция недоступна: {e}")
            
            logger.info(f"✅ Подключение к Bybit установлено (testnet: {testnet})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к Binance: {e}")
            return False
    
    async def _connect_okx(self, testnet: bool = True) -> bool:
        """Подключение к OKX"""
        try:
            self.exchange = ccxt.okx({
                'apiKey': unified_config.OKX_API_KEY,
                'secret': unified_config.OKX_API_SECRET,
                'password': unified_config.OKX_PASSPHRASE,
                'sandbox': testnet,
                'enableRateLimit': True,
                'rateLimit': 100,
                'options': {
                    'defaultType': 'spot'
                }
            })
            
            markets = await self.exchange.load_markets()
            self.markets = markets
            self.is_connected = True
            
            logger.info(f"✅ Подключение к OKX установлено (testnet: {testnet})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к OKX: {e}")
            return False
    
    async def disconnect(self) -> bool:
        """
        Отключение от биржи
        Из: real_client.py
        """
        try:
            if self.exchange:
                # CCXT не требует явного закрытия, но обнуляем переменные
                self.exchange = None
                self.is_connected = False
                self.markets = {}
                
                logger.info(f"✅ Отключен от биржи {self.current_exchange}")
                return True
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка отключения: {e}")
            return False
    
    # =================================================================
    # МЕТОДЫ ПОЛУЧЕНИЯ ДАННЫХ (из real_client.py)
    # =================================================================
    
    async def get_balance(self) -> Dict[str, Any]:
        """
        Получение баланса с биржи
        Из: real_client.py
        """
        if not self.is_connected or not self.exchange:
            return {'error': 'Not connected to exchange'}
        
        try:
            await self._wait_for_rate_limit('balance')
            
            # ✅ ИСПРАВЛЕНО: используем run_in_executor для синхронного метода
            loop = asyncio.get_event_loop()
            balance = await loop.run_in_executor(None, self.exchange.fetch_balance)
            
            # Форматируем баланс в унифицированном виде
            formatted_balance = {
                'total_usdt': 0,
                'free_usdt': 0,
                'used_usdt': 0,
                'assets': {},
                'exchange': self.current_exchange,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            for symbol, amounts in balance['total'].items():
                if amounts > 0:
                    free_amount = balance['free'].get(symbol, 0)
                    used_amount = balance['used'].get(symbol, 0)
                    
                    formatted_balance['assets'][symbol] = {
                        'free': float(free_amount),
                        'used': float(used_amount),
                        'total': float(amounts)
                    }
                    
                    # Подсчитываем USDT
                    if symbol == 'USDT':
                        formatted_balance['total_usdt'] = float(amounts)
                        formatted_balance['free_usdt'] = float(free_amount)
                        formatted_balance['used_usdt'] = float(used_amount)
            
            return formatted_balance
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения баланса: {e}")
            return {'error': str(e)}
    
    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        Получение тикера
        Из: real_client.py
        """
        if not self.is_connected or not self.exchange:
            return {'error': 'Not connected to exchange'}
        
        try:
            await self._wait_for_rate_limit('ticker')
            
            loop = asyncio.get_event_loop()
            ticker = await loop.run_in_executor(None, self.exchange.fetch_ticker, symbol)
            
            return {
                'symbol': symbol,
                'price': float(ticker['last']),
                'bid': float(ticker['bid']) if ticker['bid'] else None,
                'ask': float(ticker['ask']) if ticker['ask'] else None,
                'volume': float(ticker['baseVolume']) if ticker['baseVolume'] else 0,
                'volume_quote': float(ticker['quoteVolume']) if ticker['quoteVolume'] else 0,
                'change_24h': float(ticker['change']) if ticker['change'] else 0,
                'change_percent_24h': float(ticker['percentage']) if ticker['percentage'] else 0,
                'high_24h': float(ticker['high']) if ticker['high'] else None,
                'low_24h': float(ticker['low']) if ticker['low'] else None,
                'timestamp': ticker['timestamp'],
                'exchange': self.current_exchange
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения тикера {symbol}: {e}")
            return {'error': str(e)}
    
    async def get_order_book(self, symbol: str, limit: int = 20) -> Dict[str, Any]:
        """
        Получение стакана заявок
        Из: real_client.py
        """
        if not self.is_connected or not self.exchange:
            return {'error': 'Not connected to exchange'}
        
        try:
            await self._wait_for_rate_limit('orderbook')
            
            loop = asyncio.get_event_loop()
            orderbook = await loop.run_in_executor(None, self.exchange.fetch_order_book, symbol, limit)
            
            return {
                'symbol': symbol,
                'bids': orderbook['bids'][:limit],
                'asks': orderbook['asks'][:limit],
                'timestamp': orderbook['timestamp'],
                'nonce': orderbook['nonce'],
                'exchange': self.current_exchange
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения стакана {symbol}: {e}")
            return {'error': str(e)}
    
    async def get_klines(self, symbol: str, interval: str = None, timeframe: str = '1m', limit: int = 100) -> List[Dict]:
        """
        Получение исторических данных (свечей) - с поддержкой обоих параметров
        """
        # Если передан interval, используем его вместо timeframe
        if interval:
            timeframe = interval
            
        if not self.is_connected or not self.exchange:
            return []
        
        try:
            await self._wait_for_rate_limit('klines')
            
            # ✅ ИСПРАВЛЕНО: используем run_in_executor для синхронного метода
            loop = asyncio.get_event_loop()
            ohlcv = await loop.run_in_executor(
                None, 
                self.exchange.fetch_ohlcv, 
                symbol, 
                timeframe, 
                None,  # since
                limit
            )
            
            klines = []
            for candle in ohlcv:
                klines.append({
                    'timestamp': candle[0],
                    'open': float(candle[1]),
                    'high': float(candle[2]),
                    'low': float(candle[3]),
                    'close': float(candle[4]),
                    'volume': float(candle[5]) if candle[5] else 0
                })
            
            return klines
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения свечей {symbol}: {e}")
            return []
    
    # =================================================================
    # МЕТОДЫ ТОРГОВЛИ (из real_client.py)
    # =================================================================
    
    async def place_order(self, symbol: str, side: str, amount: float, price: float = None, order_type: str = 'market') -> Dict[str, Any]:
        """
        Размещение ордера
        Из: real_client.py
        """
        if not self.is_connected or not self.exchange:
            return {'error': 'Not connected to exchange'}
        
        # В тестовом режиме не размещаем реальные ордера
        if unified_config.PAPER_TRADING:
            return self._simulate_order(symbol, side, amount, price, order_type)
        
        try:
            await self._wait_for_rate_limit('trade')
            
            # Проверяем минимальный размер ордера
            min_size = self._get_min_order_size(symbol)
            if amount < min_size:
                return {'error': f'Amount {amount} below minimum {min_size} for {symbol}'}
            
            # Размещаем ордер
            if order_type == 'market':
                order = await self.exchange.create_market_order(symbol, side, amount)
            elif order_type == 'limit':
                if price is None:
                    return {'error': 'Price required for limit orders'}
                order = await self.exchange.create_limit_order(symbol, side, amount, price)
            else:
                return {'error': f'Unsupported order type: {order_type}'}
            
            return {
                'success': True,
                'order_id': order['id'],
                'symbol': symbol,
                'side': side,
                'amount': amount,
                'price': price,
                'type': order_type,
                'status': order['status'],
                'filled': order.get('filled', 0),
                'timestamp': order['timestamp'],
                'exchange': self.current_exchange
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка размещения ордера {symbol}: {e}")
            return {'error': str(e)}
    
    async def cancel_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """
        Отмена ордера
        Из: real_client.py
        """
        if not self.is_connected or not self.exchange:
            return {'error': 'Not connected to exchange'}
        
        try:
            await self._wait_for_rate_limit('trade')
            
            result = await self.exchange.cancel_order(order_id, symbol)
            
            return {
                'success': True,
                'order_id': order_id,
                'symbol': symbol,
                'status': 'cancelled',
                'timestamp': datetime.utcnow().timestamp() * 1000,
                'exchange': self.current_exchange
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка отмены ордера {order_id}: {e}")
            return {'error': str(e)}
    
    async def get_order_status(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """
        Получение статуса ордера
        Из: real_client.py
        """
        if not self.is_connected or not self.exchange:
            return {'error': 'Not connected to exchange'}
        
        try:
            await self._wait_for_rate_limit('order_status')
            
            order = await self.exchange.fetch_order(order_id, symbol)
            
            return {
                'order_id': order['id'],
                'symbol': order['symbol'],
                'status': order['status'],
                'side': order['side'],
                'amount': order['amount'],
                'filled': order['filled'],
                'price': order['price'],
                'average': order['average'],
                'timestamp': order['timestamp'],
                'exchange': self.current_exchange
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения статуса ордера {order_id}: {e}")
            return {'error': str(e)}
    
    # =================================================================
    # МЕТОДЫ ПОЛУЧЕНИЯ РЫНОЧНЫХ ДАННЫХ (из real_client.py)
    # =================================================================
    
    async def fetch_trading_pairs(self) -> List[str]:
        """
        Получение списка доступных торговых пар
        Из: real_client.py
        """
        if not self.is_connected or not self.exchange:
            return []
        
        try:
            if not self.markets:
                self.markets = await self.exchange.load_markets()
            
            # Фильтруем только USDT пары и активные
            usdt_pairs = []
            for symbol, market in self.markets.items():
                if (market['quote'] == 'USDT' and 
                    market['spot'] and 
                    market['active']):
                    usdt_pairs.append(symbol)
            
            logger.info(f"📈 Загружено {len(usdt_pairs)} USDT торговых пар")
            return usdt_pairs[:50]  # Ограничиваем для производительности
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения торговых пар: {e}")
            return ['BTC/USDT', 'ETH/USDT']  # Fallback
    
    async def fetch_market_data(self, symbols: List[str]) -> Dict[str, Dict]:
        """
        Получение рыночных данных для нескольких символов
        Из: real_client.py
        """
        if not self.is_connected or not self.exchange:
            return {}
        
        market_data = {}
        
        for symbol in symbols:
            try:
                ticker = await self.get_ticker(symbol)
                if 'error' not in ticker:
                    market_data[symbol] = ticker
                
                # Небольшая пауза между запросами
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.warning(f"⚠️ Ошибка получения данных для {symbol}: {e}")
                continue
        
        logger.info(f"📊 Загружены данные для {len(market_data)} символов")
        return market_data
        
    async def fetch_trades(self, symbol: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Получение последних сделок по символу
        Добавлено для совместимости с DataCollector
        """
        if not self.is_connected or not self.exchange:
            return []
        
        try:
            await self._wait_for_rate_limit('trades')
            
            # ✅ ИСПРАВЛЕНО: используем run_in_executor для синхронного метода
            loop = asyncio.get_event_loop()
            trades = await loop.run_in_executor(
                None, 
                lambda: self.exchange.fetch_trades(symbol, limit=limit)
            )
            
            # Форматируем сделки в унифицированном виде
            formatted_trades = []
            for trade in trades:
                formatted_trade = {
                    'id': trade.get('id'),
                    'symbol': trade.get('symbol', symbol),
                    'side': trade.get('side'),  # 'buy' or 'sell'
                    'amount': float(trade.get('amount', 0)),
                    'price': float(trade.get('price', 0)),
                    'cost': float(trade.get('cost', 0)),
                    'timestamp': trade.get('timestamp'),
                    'datetime': trade.get('datetime'),
                    'exchange': self.current_exchange
                }
                formatted_trades.append(formatted_trade)
            
            logger.debug(f"📈 Получено {len(formatted_trades)} сделок для {symbol}")
            return formatted_trades
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения сделок для {symbol}: {e}")
            return []
    
    # =================================================================
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # =================================================================
    
    def _simulate_order(self, symbol: str, side: str, amount: float, price: float = None, order_type: str = 'market') -> Dict[str, Any]:
        """Симуляция ордера для paper trading"""
        import uuid
        
        # Получаем текущую цену для симуляции
        current_price = price if price else 50000.0  # Fallback цена
        
        return {
            'success': True,
            'order_id': str(uuid.uuid4()),
            'symbol': symbol,
            'side': side,
            'amount': amount,
            'price': current_price,
            'type': order_type,
            'status': 'filled',  # В симуляции сразу исполняем
            'filled': amount,
            'timestamp': datetime.utcnow().timestamp() * 1000,
            'exchange': f'{self.current_exchange}_simulation'
        }
    
    def _get_min_order_size(self, symbol: str) -> float:
        """Получение минимального размера ордера для символа"""
        if self.current_exchange == 'bybit':
            params = unified_config.get_bybit_trading_params()
            return params['min_order_sizes'].get(symbol, 0.001)
        
        # Fallback значения для других бирж
        return 0.001
    
    def get_supported_exchanges(self) -> List[str]:
        """Получение списка поддерживаемых бирж"""
        return self.supported_exchanges
    
    def get_current_exchange(self) -> str:
        """Получение текущей биржи"""
        return self.current_exchange
    
    def is_exchange_connected(self) -> bool:
        """Проверка подключения к бирже"""
        return self.is_connected and self.exchange is not None
    
    async def ping(self) -> bool:
        """Проверка соединения с биржей"""
        if not self.is_connected or not self.exchange:
            return False
        
        try:
            # ✅ ИСПРАВЛЕНО: используем run_in_executor для синхронного метода
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.exchange.fetch_time)
            return True
        except Exception as e:
            logger.warning(f"⚠️ Ping failed: {e}")
            return False
    
    async def reconnect(self) -> bool:
        """Переподключение к бирже"""
        logger.info("🔄 Попытка переподключения...")
        
        await self.disconnect()
        await asyncio.sleep(2)
        
        return await self.connect(self.current_exchange, unified_config.BYBIT_TESTNET)
    
    # Алиасы для совместимости
    fetch_balance = get_balance
    fetch_ticker = get_ticker
    fetch_order_book = get_order_book
    fetch_ohlcv = get_klines
    

# =================================================================
# ФАБРИКА КЛИЕНТОВ
# =================================================================

class ExchangeClientFactory:
    """
    Фабрика для создания клиентов бирж
    Из: client.py
    """
    
    @staticmethod
    def create_client(exchange_name: str = 'bybit') -> UnifiedExchangeClient:
        """Создание клиента для конкретной биржи"""
        client = UnifiedExchangeClient()
        client.current_exchange = exchange_name.lower()
        return client
    
    @staticmethod
    def get_available_exchanges() -> List[str]:
        """Получение списка доступных бирж"""
        return ['bybit', 'binance', 'okx']

# =================================================================
# ФУНКЦИИ ДЛЯ ОБРАТНОЙ СОВМЕСТИМОСТИ
# =================================================================

def get_real_exchange_client() -> UnifiedExchangeClient:
    """
    Получение реального клиента биржи
    ЗАМЕНЯЕТ: get_real_exchange_client() из real_client.py
    """
    return ExchangeClientFactory.create_client('bybit')

def get_exchange_client(exchange_name: str = 'bybit') -> UnifiedExchangeClient:
    """
    Получение клиента конкретной биржи
    ЗАМЕНЯЕТ: ExchangeClient из client.py
    """
    return ExchangeClientFactory.create_client(exchange_name)

# =================================================================
# ЭКСПОРТЫ
# =================================================================

__all__ = [
    'UnifiedExchangeClient',
    'BaseExchangeClient', 
    'ExchangeClientFactory',
    'get_real_exchange_client',
    'get_exchange_client'
]