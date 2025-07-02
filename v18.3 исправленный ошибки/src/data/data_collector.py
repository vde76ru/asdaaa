"""
Реальный сборщик рыночных данных для торгового бота
Файл: src/data/data_collector.py
"""
import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from collections import defaultdict

logger = logging.getLogger(__name__)

class DataCollector:
    """Реальный сборщик рыночных данных"""
    
    def __init__(self, exchange_client, db_session=None):
        self.exchange = exchange_client
        self.db = db_session
        self.is_running = False
        self.is_initialized = True
        self.collected_data = defaultdict(dict)
        self.collection_tasks = {}
        self.update_interval = 60  # секунд
        self.active_pairs = []
        
        logger.info("✅ DataCollector инициализирован")
    
    async def start(self):
        """Запуск сборщика данных"""
        self.is_running = True
        logger.info("✅ DataCollector запущен")
        
        # Запускаем фоновые задачи сбора
        asyncio.create_task(self._continuous_collection())
        return True
    
    async def stop(self):
        """Остановка сборщика данных"""
        self.is_running = False
        
        # Отменяем все задачи
        for task in self.collection_tasks.values():
            if not task.done():
                task.cancel()
        
        logger.info("✅ DataCollector остановлен")
        return True
    
    async def _continuous_collection(self):
        """Непрерывный сбор данных"""
        while self.is_running:
            try:
                # Получаем список активных пар
                active_pairs = await self._get_active_pairs()
                
                # Собираем данные для каждой пары
                tasks = []
                for symbol in active_pairs:
                    task = asyncio.create_task(self.collect_market_data(symbol))
                    tasks.append(task)
                
                # Ждем завершения всех задач
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
                
                # Сохраняем в БД если есть подключение
                if self.db:
                    await self._save_to_database()
                
                await asyncio.sleep(self.update_interval)
                
            except Exception as e:
                logger.error(f"❌ Ошибка в continuous_collection: {e}")
                await asyncio.sleep(10)
    
    async def collect_market_data(self, symbol: str, data: dict = None) -> Dict[str, Any]:
        """Сбор рыночных данных для символа"""
        try:
            # Если данные переданы извне (для совместимости)
            if data is not None:  # ✅ ИСПРАВЛЕНО: проверка на None вместо if data
                self.collected_data[symbol] = {
                    'data': data,
                    'timestamp': datetime.utcnow()
                }
                logger.debug(f"📊 Сохранены внешние данные для {symbol}")
                return data
            
            # Иначе собираем сами
            collected = {}
            
            # 1. Получаем текущую цену и тикер
            ticker = await self.exchange.fetch_ticker(symbol)
            if ticker:
                collected['ticker'] = {
                    'symbol': symbol,
                    'last': float(ticker.get('last', 0)),  # ✅ ИСПРАВЛЕНО: преобразование в float
                    'bid': float(ticker.get('bid', 0)),
                    'ask': float(ticker.get('ask', 0)),
                    'volume': float(ticker.get('baseVolume', 0)),
                    'quote_volume': float(ticker.get('quoteVolume', 0)),
                    'change': float(ticker.get('percentage', 0)),
                    'timestamp': datetime.utcnow()
                }
            
            # 2. Получаем стакан ордеров
            orderbook = await self.exchange.fetch_order_book(symbol, limit=20)
            if orderbook:
                collected['orderbook'] = {
                    'bids': orderbook.get('bids', [])[:10],
                    'asks': orderbook.get('asks', [])[:10],
                    'timestamp': orderbook.get('timestamp', datetime.utcnow())
                }
                
                # Рассчитываем спред и глубину
                if orderbook['bids'] and orderbook['asks']:
                    best_bid = float(orderbook['bids'][0][0])  # ✅ ИСПРАВЛЕНО: преобразование в float
                    best_ask = float(orderbook['asks'][0][0])
                    collected['spread'] = (best_ask - best_bid) / best_bid * 100
                    collected['bid_depth'] = sum(float(bid[1]) for bid in orderbook['bids'][:5])
                    collected['ask_depth'] = sum(float(ask[1]) for ask in orderbook['asks'][:5])
            
            # 3. Получаем последние сделки
            trades = await self.exchange.fetch_trades(symbol, limit=100)
            if trades:
                # ✅ ИСПРАВЛЕНО: безопасное получение суммы с преобразованием типов
                buy_volume = sum(float(t.get('amount', 0)) for t in trades if t.get('side') == 'buy')
                sell_volume = sum(float(t.get('amount', 0)) for t in trades if t.get('side') == 'sell')
                total_price = sum(float(t.get('price', 0)) for t in trades)
                
                collected['recent_trades'] = {
                    'count': len(trades),
                    'buy_volume': buy_volume,
                    'sell_volume': sell_volume,
                    'avg_price': total_price / len(trades) if trades else 0,
                    'timestamp': datetime.utcnow()
                }
            
            # 4. Получаем свечи для технического анализа
            ohlcv = await self.exchange.fetch_ohlcv(symbol, '5m', limit=100)
            if ohlcv:
                # ✅ ИСПРАВЛЕНО: преобразование timestamp и безопасная работа с данными
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                
                # Преобразуем колонки в числовые типы
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                
                # Преобразуем timestamp
                if df['timestamp'].dtype == 'object':
                    df['timestamp'] = pd.to_numeric(df['timestamp'], errors='coerce')
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                
                # Удаляем строки с NaN после преобразования
                df = df.dropna()
                
                if len(df) >= 20:  # Проверяем, что есть достаточно данных
                    collected['candles'] = df.to_dict('records')[-20:]  # Последние 20 свечей
                    collected['technical'] = {
                        'sma_20': float(df['close'].rolling(20).mean().iloc[-1]),
                        'volume_avg': float(df['volume'].rolling(20).mean().iloc[-1]),
                        'volatility': float(df['close'].pct_change().std() * 100),
                        'high_24h': float(df['high'].max()),
                        'low_24h': float(df['low'].min())
                    }
            
            # Сохраняем в кеш
            self.collected_data[symbol] = {
                'data': collected,
                'timestamp': datetime.utcnow()
            }
            
            logger.debug(f"📊 Собраны данные для {symbol}")
            return collected
            
        except Exception as e:
            logger.error(f"❌ Ошибка сбора данных для {symbol}: {e}")
            return {}
    
    async def collect_orderbook(self, symbol: str, depth: int = 20) -> Dict[str, Any]:
        """Сбор данных стакана"""
        try:
            orderbook = await self.exchange.fetch_order_book(symbol, limit=depth)
            return orderbook
        except Exception as e:
            logger.error(f"❌ Ошибка сбора стакана {symbol}: {e}")
            return {}
    
    async def _get_active_pairs(self) -> List[str]:
        """Получение списка активных торговых пар"""
        # Если список уже задан
        if self.active_pairs:
            return self.active_pairs
        
        # Получаем из конфигурации
        try:
            from ..core.unified_config import unified_config
            return unified_config.TRADING_PAIRS or ['BTCUSDT', 'ETHUSDT']
        except:
            return ['BTCUSDT', 'ETHUSDT', 'ADAUSDT', 'BNBUSDT', 'SOLUSDT']
    
    def set_active_pairs(self, pairs: List[str]):
        """Установка списка активных пар"""
        self.active_pairs = pairs
        logger.info(f"📊 Установлены активные пары: {pairs}")
    
    async def _save_to_database(self):
        """Сохранение данных в БД"""
        if not self.db:
            return
        
        try:
            # TODO: Реализовать сохранение в таблицы candles, market_conditions
            # Пример структуры:
            # for symbol, data in self.collected_data.items():
            #     candle = Candle(
            #         symbol=symbol,
            #         timeframe='5m',
            #         open=data['ticker']['last'],
            #         high=data['ticker']['last'],
            #         low=data['ticker']['last'],
            #         close=data['ticker']['last'],
            #         volume=data['ticker']['volume'],
            #         timestamp=data['timestamp']
            #     )
            #     self.db.add(candle)
            # self.db.commit()
            pass
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения в БД: {e}")
    
    def get_data(self, symbol: str) -> Dict[str, Any]:
        """Получение собранных данных"""
        return self.collected_data.get(symbol, {})
    
    def get_status(self) -> Dict[str, Any]:
        """Получение статуса сборщика"""
        return {
            'running': self.is_running,
            'initialized': self.is_initialized,
            'data_count': len(self.collected_data),
            'symbols': list(self.collected_data.keys()),
            'last_update': max(
                (d['timestamp'] for d in self.collected_data.values() if 'timestamp' in d),
                default=None
            )
        }
    
    def get_all_data(self) -> Dict[str, Any]:
        """Получение всех собранных данных"""
        return dict(self.collected_data)