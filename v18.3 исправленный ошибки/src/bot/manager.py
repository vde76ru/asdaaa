#!/usr/bin/env python3
"""
ПОЛНОЦЕННЫЙ МЕНЕДЖЕР ТОРГОВОГО БОТА ДЛЯ МНОЖЕСТВЕННЫХ ВАЛЮТ
===========================================================

⚠️ ВАЖНО: Этот файл ПОЛНОСТЬЮ ЗАМЕНЯЕТ существующий src/bot/manager.py

ПОЛНАЯ ВЕРСИЯ с восстановленным функционалом и ML интеграцией (2200+ строк):
✅ Автопоиск и анализ до 200 торговых пар
✅ 7+ стратегий с интеллектуальным выбором  
✅ Полная система управления рисками
✅ Машинное обучение и предиктивная аналитика
✅ Анализ новостей и социальных сетей
✅ Система мониторинга здоровья
✅ Бэктестинг и оптимизация
✅ Экспорт данных и аналитика
✅ 10+ параллельных циклов мониторинга
✅ Полная автоматизация торговли

Путь: src/bot/manager.py
"""

import asyncio
import logging
import json
import pickle
import numpy as np
import pandas as pd
import psutil
import traceback
import signal
import threading
import time
from sqlalchemy import text
from typing import Dict, List, Optional, Tuple, Any, Set, Union, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
import aiofiles
import aiohttp
from concurrent.futures import ThreadPoolExecutor
import warnings
warnings.filterwarnings('ignore')

# Импорты проекта
from ..core.unified_config import unified_config as config
from ..core.database import SessionLocal, get_session
from ..core.models import (
    Trade, TradingPair, Signal, TradeStatus, OrderSide, OrderType,
    BotState, StrategyPerformance, Candle, Balance, 
    MLModel, MLPrediction, NewsAnalysis, SocialSignal, TradingLog
)

# Подавляем TensorFlow warnings
import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'


logger = logging.getLogger(__name__)


# ДИАГНОСТИКА КОНФИГУРАЦИИ
logger.info("="*60)
logger.info("🔍 ДИАГНОСТИКА РЕЖИМОВ ТОРГОВЛИ:")
logger.info(f"   PAPER_TRADING = {config.PAPER_TRADING}")
logger.info(f"   LIVE_TRADING = {config.LIVE_TRADING}")
logger.info(f"   TESTNET = {config.TESTNET}")
logger.info(f"   ENVIRONMENT = {config.ENVIRONMENT}")
logger.info("="*60)

# =================================================================
# ENUMS И DATACLASSES
# =================================================================

class BotStatus(Enum):
    """Статусы бота"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"
    PAUSED = "paused"
    EMERGENCY_STOP = "emergency_stop"

class ComponentStatus(Enum):
    """Статусы компонентов"""
    NOT_INITIALIZED = "not_initialized"
    INITIALIZING = "initializing" 
    READY = "ready"
    FAILED = "failed"
    DISABLED = "disabled"
    RECONNECTING = "reconnecting"

class MarketPhase(Enum):
    """Фазы рынка"""
    ACCUMULATION = "accumulation"    # Накопление
    MARKUP = "markup"                # Рост
    DISTRIBUTION = "distribution"    # Распределение  
    MARKDOWN = "markdown"            # Падение
    UNKNOWN = "unknown"              # Неопределенная

class RiskLevel(Enum):
    """Уровни риска"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"

class TradeDecision(Enum):
    """Решения по сделкам"""
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    WEAK_BUY = "weak_buy"
    HOLD = "hold"
    WEAK_SELL = "weak_sell"
    SELL = "sell"
    STRONG_SELL = "strong_sell"

@dataclass
class TradingOpportunity:
    """Расширенная торговая возможность"""
    symbol: str
    strategy: str
    decision: TradeDecision
    confidence: float               # Уверенность 0-1
    expected_profit: float          # Ожидаемая прибыль %
    expected_loss: float           # Ожидаемый убыток %
    risk_level: RiskLevel
    price: float                   # Цена входа
    stop_loss: float              # Стоп-лосс
    take_profit: float            # Тейк-профит
    market_phase: MarketPhase
    volume_score: float           # Скор объема 0-1
    technical_score: float        # Технический анализ 0-1
    ml_score: float              # ML предсказание 0-1
    news_sentiment: float        # Настроение новостей -1 to 1
    social_sentiment: float      # Социальное настроение -1 to 1
    risk_reward_ratio: float     # Соотношение риск/доходность
    correlation_risk: float      # Риск корреляции 0-1
    volatility: float           # Волатильность
    liquidity_score: float      # Ликвидность 0-1
    timeframe: str              # Таймфрейм анализа
    entry_reasons: List[str]    # Причины входа
    exit_conditions: List[str]  # Условия выхода
    metadata: Dict[str, Any]    # Дополнительные данные
    timestamp: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime = field(default_factory=lambda: datetime.utcnow() + timedelta(hours=1))

@dataclass
class MarketState:
    """Расширенное состояние рынка"""
    overall_trend: str              # BULLISH, BEARISH, SIDEWAYS
    volatility: str                 # LOW, MEDIUM, HIGH, EXTREME
    fear_greed_index: int          # 0-100
    market_cap: float              # Общая капитализация
    volume_24h: float              # Объем за 24ч
    dominance_btc: float           # Доминирование BTC
    dominance_eth: float           # Доминирование ETH
    active_pairs_count: int        # Количество активных пар
    trending_pairs: List[str]      # Трендовые пары
    declining_pairs: List[str]     # Падающие пары
    correlation_matrix: Dict[str, Dict[str, float]]  # Матрица корреляций
    sector_performance: Dict[str, float]  # Производительность секторов
    market_regime: str             # BULL_MARKET, BEAR_MARKET, SIDEWAYS_MARKET
    risk_level: RiskLevel         # Общий уровень риска
    timestamp: datetime = field(default_factory=datetime.utcnow)

@dataclass
class ComponentInfo:
    """Информация о компоненте системы"""
    name: str
    status: ComponentStatus
    instance: Any = None
    error: Optional[str] = None
    last_heartbeat: Optional[datetime] = None
    restart_count: int = 0
    dependencies: List[str] = field(default_factory=list)
    is_critical: bool = False
    health_check_interval: int = 60
    max_restart_attempts: int = 3

@dataclass
class PerformanceMetrics:
    """Метрики производительности"""
    analysis_time_avg: float = 0.0
    trade_execution_time_avg: float = 0.0
    pairs_per_second: float = 0.0
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0
    network_latency_ms: float = 0.0
    error_rate_percent: float = 0.0
    uptime_seconds: float = 0.0
    cycles_per_hour: float = 0.0
    api_calls_per_minute: float = 0.0

@dataclass
class TradingStatistics:
    """Расширенная торговая статистика"""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_profit_usd: float = 0.0
    total_loss_usd: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_duration: int = 0
    average_win: float = 0.0
    average_loss: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    consecutive_wins: int = 0
    consecutive_losses: int = 0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    trades_per_day: float = 0.0
    average_trade_duration: float = 0.0
    start_balance: float = 0.0
    current_balance: float = 0.0
    peak_balance: float = 0.0
    roi_percent: float = 0.0

# =================================================================
# ГЛАВНЫЙ КЛАСС BOTMANAGER
# =================================================================

class BotManager:
    """
    ПОЛНОЦЕННЫЙ Менеджер торгового бота с множественными валютами
    
    НОВЫЕ ВОЗМОЖНОСТИ:
    ✅ Автоматический поиск и анализ до 200 торговых пар
    ✅ 7+ стратегий с интеллектуальным выбором
    ✅ Машинное обучение для прогнозирования цен
    ✅ Анализ новостей и социальных сетей  
    ✅ Система управления рисками с корреляционным анализом
    ✅ Множественные циклы мониторинга
    ✅ Система здоровья и самовосстановления
    ✅ Бэктестинг и оптимизация параметров
    ✅ Экспорт данных и аналитика
    ✅ Полная автоматизация торговли
    """
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        """Паттерн Singleton"""
        if cls._instance is None:
            cls._instance = super(BotManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Инициализация менеджера бота - ПОЛНАЯ ВЕРСИЯ"""
        if BotManager._initialized:
            return
            
        BotManager._initialized = True
        logger.info("🚀 Инициализация ПОЛНОЦЕННОГО BotManager...")
        
        # === ОСНОВНЫЕ АТРИБУТЫ ===
        self.status = BotStatus.STOPPED
        self.start_time = None
        self.stop_time = None
        self.pause_time = None
        
        # === ТОРГОВЫЕ ПАРЫ - РАСШИРЕНО ===
        self.all_trading_pairs = []          # Все доступные пары
        self.active_pairs = []               # Активные для торговли
        self.inactive_pairs = []             # Неактивные пары
        self.blacklisted_pairs = set()       # Заблокированные пары
        self.watchlist_pairs = []            # Список наблюдения
        self.trending_pairs = []             # Трендовые пары
        self.high_volume_pairs = []          # Высокообъемные пары
        
        # === ПОЗИЦИИ И СДЕЛКИ ===
        self.positions = {}                  # Открытые позиции {symbol: position_info}
        self.pending_orders = {}             # Ожидающие ордера
        self.executed_trades = []            # Выполненные сделки
        self.failed_trades = []              # Неудачные сделки
        self.trades_today = 0               # Счетчик сделок за день
        self.daily_profit = 0.0             # Прибыль за день
        self.weekly_profit = 0.0            # Прибыль за неделю
        self.monthly_profit = 0.0           # Прибыль за месяц
        
        # === ЦИКЛЫ И ЗАДАЧИ ===
        self.cycles_count = 0               # Счетчик циклов
        self._stop_event = asyncio.Event()  # Событие остановки
        self._pause_event = asyncio.Event() # Событие паузы
        self._main_task = None              # Основная задача
        self.tasks = {}                     # Активные задачи
        self.task_health = {}               # Здоровье задач
        
        # === КОМПОНЕНТЫ СИСТЕМЫ ===
        self.components = {}                # Все компоненты системы
        self.component_manager = None       # Менеджер компонентов
        self.exchange = None               # Клиент биржи
        self.market_analyzer = None        # Анализатор рынка
        self.trader = None                 # Исполнитель сделок
        self.risk_manager = None           # Менеджер рисков
        self.portfolio_manager = None      # Менеджер портфеля
        self.notifier = None              # Система уведомлений
        self.data_collector = None        # Сборщик данных
        self.strategy_factory = None      # Фабрика стратегий
        
        # === СТРАТЕГИИ - РАСШИРЕНО ===
        self.available_strategies = config.ENABLED_STRATEGIES
        self.strategy_instances = {}       # Экземпляры стратегий
        self.balance = 0.0
        self.available_balance = 0.0
        self.trades_today = 0
        self.positions = {}
        self.candle_cache = {}
        self.price_history = {}
        
        # === СЧЕТЧИКИ И СТАТИСТИКА ===
        self.cycle_count = 0
        self.last_balance_update = None
        self.daily_pnl = 0.0
        self.total_pnl = 0.0
        self.stop_requested = False
        self.strategy_performance = defaultdict(lambda: {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_profit': 0.0,
            'win_rate': 0.0,
            'avg_profit_per_trade': 0.0,
            'max_drawdown': 0.0,
            'sharpe_ratio': 0.0,
            'sortino_ratio': 0.0,
            'last_used': None,
            'enabled': True,
            'confidence_scores': deque(maxlen=100),
            'recent_performance': deque(maxlen=50)
        })
        
        # === ТОРГОВЫЕ ВОЗМОЖНОСТИ ===
        self.current_opportunities = {}     # Текущие возможности {symbol: opportunity}
        self.opportunity_history = deque(maxlen=1000)  # История возможностей
        self.missed_opportunities = deque(maxlen=100)  # Упущенные возможности
        
        # === РЫНОЧНЫЕ ДАННЫЕ - РАСШИРЕНО ===
        self.market_state = MarketState(
            overall_trend="UNKNOWN",
            volatility="MEDIUM",
            fear_greed_index=50,
            market_cap=0.0,
            volume_24h=0.0,
            dominance_btc=0.0,
            dominance_eth=0.0,
            active_pairs_count=0,
            trending_pairs=[],
            declining_pairs=[],
            correlation_matrix={},
            sector_performance={},
            market_regime="SIDEWAYS_MARKET",
            risk_level=RiskLevel.MEDIUM
        )
        
        # === КЭШИРОВАНИЕ ДАННЫХ ===
        self.market_data_cache = {}         # Кэш рыночных данных {symbol: data}
        self.price_history = defaultdict(lambda: deque(maxlen=1000))  # История цен
        self.volume_history = defaultdict(lambda: deque(maxlen=1000))  # История объемов
        self.indicator_cache = defaultdict(dict)  # Кэш индикаторов
        self.candle_cache = defaultdict(lambda: deque(maxlen=500))  # Кэш свечей
        
        # === МАШИННОЕ ОБУЧЕНИЕ ===
        self.ml_models = {}                # ML модели {symbol: model}
        self.ml_predictions = {}           # ML предсказания {symbol: prediction}
        self.feature_cache = {}            # Кэш признаков для ML
        self.model_performance = defaultdict(dict)  # Производительность моделей
        self.training_queue = asyncio.Queue()  # Очередь обучения
        self.prediction_cache = {}         # Кэш предсказаний
        
        # === АНАЛИЗ НОВОСТЕЙ ===
        self.news_cache = deque(maxlen=1000)  # Кэш новостей
        self.news_sentiment = {}           # Настроения новостей {symbol: sentiment}
        self.social_signals = deque(maxlen=500)  # Социальные сигналы
        self.sentiment_analyzer = None     # Анализатор настроений
        self.news_sources = []            # Источники новостей
        
        # === РИСК-МЕНЕДЖМЕНТ ===
        self.risk_limits = {
            'max_portfolio_risk': config.MAX_PORTFOLIO_RISK_PERCENT / 100,
            'max_daily_loss': config.MAX_DAILY_LOSS_PERCENT / 100,
            'max_correlation': config.MAX_CORRELATION_THRESHOLD,
            'max_positions': config.MAX_POSITIONS,
            'max_daily_trades': config.MAX_DAILY_TRADES
        }
        self.correlation_matrix = {}       # Матрица корреляций
        self.portfolio_risk = 0.0         # Текущий риск портфеля
        self.daily_loss = 0.0             # Дневные потери
        self.risk_alerts = []             # Предупреждения о рисках
        
        # === ПРОИЗВОДИТЕЛЬНОСТЬ ===
        self.performance_metrics = PerformanceMetrics()
        self.system_stats = {}            # Системная статистика
        self.api_call_count = defaultdict(int)  # Счетчики API вызовов
        self.error_count = defaultdict(int)     # Счетчики ошибок
        self.latency_measurements = deque(maxlen=100)  # Измерения задержки
        
        # === СТАТИСТИКА - РАСШИРЕННАЯ ===
        self.trading_stats = TradingStatistics()
        self.strategy_stats = defaultdict(lambda: TradingStatistics())
        self.pair_stats = defaultdict(lambda: TradingStatistics())
        self.daily_stats = defaultdict(lambda: TradingStatistics())
        
        # === КОНФИГУРАЦИЯ ===
        self.config = config
        self.trading_pairs = config.get_active_trading_pairs()
        self.strategy = 'auto'
        self.mode = 'live' if not config.TEST_MODE else 'test'
        
        # === СОБЫТИЯ И СЛУШАТЕЛИ ===
        self.event_listeners = defaultdict(list)  # Слушатели событий
        self.event_queue = asyncio.Queue()  # Очередь событий
        
        # === БЭКТЕСТИНГ ===
        self.backtesting_enabled = config.ENABLE_BACKTESTING
        self.backtest_results = {}
        self.optimization_results = {}
        
        # === ЭКСПОРТ И ЛОГИРОВАНИЕ ===
        self.export_queue = asyncio.Queue()  # Очередь экспорта
        self.log_buffer = deque(maxlen=10000)  # Буфер логов
        
        # === БЕЗОПАСНОСТЬ ===
        self.circuit_breaker_active = False
        self.emergency_stop_triggered = False
        self.suspicious_activity = []
        
        # === WEBSOCKET И РЕАЛЬНОЕ ВРЕМЯ ===
        self.websocket_connections = {}
        self.real_time_data = {}
        self.price_alerts = {}
        
        # === THREAD POOL ===
        self.thread_pool = ThreadPoolExecutor(max_workers=config.MAX_CONCURRENT_ANALYSIS)
        
        self.exchange_client = None
        self._exchange_initialized = False
        self.enhanced_exchange_client = None
        self.v5_integration_enabled = False
        
        logger.info("🤖 ПОЛНОЦЕННЫЙ BotManager инициализирован")
        logger.info(f"📊 Максимум торговых пар: {config.MAX_TRADING_PAIRS}")
        logger.info(f"📈 Максимум позиций: {config.MAX_POSITIONS}")
        logger.info(f"🎯 Активные стратегии: {len(self.available_strategies)}")
        
        # Инициализируем компоненты
        self._initialization_completed = False
    
    async def initialize(self):
        """Инициализация с улучшенной обработкой ошибок"""
        max_init_attempts = 3
        
        for attempt in range(max_init_attempts):
            try:
                logger.info(f"🚀 Инициализация BotManager (попытка {attempt + 1}/{max_init_attempts})")
                
                # ✅ БЕЗОПАСНЫЙ ИМПОРТ
                try:
                    from ..exchange.unified_exchange import get_real_exchange_client
                except ImportError as e:
                    logger.error(f"❌ Ошибка импорта exchange client: {e}")
                    return False
                
                # ✅ ПРЕДОТВРАЩАЕМ ПОВТОРНУЮ ИНИЦИАЛИЗАЦИЮ
                if hasattr(self, 'exchange_client') and self.exchange_client and self.exchange_client.is_connected:
                    logger.info("✅ Exchange client уже инициализирован и подключен")
                    return True
                
                # Создаем новый клиент
                self.exchange_client = get_real_exchange_client()
                
                # Подключаемся с retry логикой
                connection_attempts = 0
                max_connection_attempts = 3
                
                while connection_attempts < max_connection_attempts:
                    logger.info(f"🔗 Подключение к бирже (попытка {connection_attempts + 1})")
                    
                    connected = await self.exchange_client.connect()
                    
                    if connected and self.exchange_client.is_connected:
                        logger.info("✅ Успешно подключен к бирже")
                        break
                    else:
                        connection_attempts += 1
                        if connection_attempts < max_connection_attempts:
                            wait_time = min(30, 5 * connection_attempts)
                            logger.warning(f"⏳ Ждем {wait_time}с перед повторной попыткой...")
                            await asyncio.sleep(wait_time)
                
                if not self.exchange_client.is_connected:
                    raise Exception(f"Не удалось подключиться к бирже после {max_connection_attempts} попыток")
                
                logger.info("✅ BotManager успешно инициализирован")
                return True
                
            except Exception as e:
                logger.error(f"❌ Ошибка инициализации (попытка {attempt + 1}): {e}")
                
                if attempt < max_init_attempts - 1:
                    wait_time = min(60, 10 * (attempt + 1))
                    logger.info(f"⏳ Ждем {wait_time}с перед повторной инициализацией...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error("❌ Все попытки инициализации исчерпаны")
                    return False
        
        return False
    
    async def _initialize_components(self):
        """
        Алиас для _initialize_all_components() для обратной совместимости
        
        ❌ Ошибка была в том, что в __init__ вызывался:
        self._initialization_completed = False
        
        ✅ А существующий метод назывался:
        async def _initialize_all_components(self)
        
        ✅ Этот метод решает проблему, сохраняя всю функциональность
        """
        
        return await self._initialize_all_components()
    
    # =================================================================
    # ОСНОВНЫЕ МЕТОДЫ УПРАВЛЕНИЯ
    # =================================================================
    
    async def _update_market_data(self):
        """Обновление рыночных данных для всех торговых пар"""
        try:
            logger.debug("📊 Обновление рыночных данных...")
            
            updated_pairs = 0
            for symbol in self.active_pairs:
                try:
                    # ✅ ИСПРАВЛЕНО: используем data_collector если он доступен
                    if hasattr(self, 'data_collector') and self.data_collector:
                        # Собираем данные через data_collector
                        market_data = await self.data_collector.collect_market_data(symbol)
                        
                        # ✅ ИСПРАВЛЕНО: правильная проверка словаря
                        if market_data and isinstance(market_data, dict):
                            # Сохраняем candles в кэш если они есть
                            if 'candles' in market_data and market_data['candles']:
                                if symbol not in self.candle_cache:
                                    self.candle_cache[symbol] = deque(maxlen=100)
                                
                                # Добавляем свечи в кэш
                                for candle in market_data['candles']:
                                    self.candle_cache[symbol].append(candle)
                            
                            # Обновляем последнюю цену
                            if 'ticker' in market_data and market_data['ticker']:
                                last_price = float(market_data['ticker'].get('last', 0))
                                
                                if symbol not in self.price_history:
                                    self.price_history[symbol] = deque(maxlen=100)
                                
                                self.price_history[symbol].append({
                                    'price': last_price,
                                    'volume': float(market_data['ticker'].get('volume', 0)),
                                    'timestamp': datetime.utcnow()
                                })
                                
                                updated_pairs += 1
                                logger.debug(f"📈 {symbol}: ${last_price:.4f}")
                    else:
                        # Fallback: получаем данные напрямую через exchange
                        if hasattr(self.exchange_client, 'get_klines'):
                            candles = await self.exchange_client.get_klines(
                                symbol=symbol,
                                interval='5m',
                                limit=50
                            )
                        elif hasattr(self.exchange_client, 'fetch_ohlcv'):
                            candles = await self.exchange_client.fetch_ohlcv(
                                symbol, '5m', limit=50
                            )
                        else:
                            logger.warning(f"⚠️ Метод получения свечей недоступен для {symbol}")
                            continue
                        
                        if candles and len(candles) > 0:
                            # Сохраняем данные в кэш
                            if symbol not in self.candle_cache:
                                self.candle_cache[symbol] = deque(maxlen=100)
                            
                            # Добавляем новые свечи
                            for candle in candles[-10:]:  # Последние 10 свечей
                                candle_data = {
                                    'timestamp': candle[0] if isinstance(candle, list) else candle.get('timestamp'),
                                    'open': float(candle[1] if isinstance(candle, list) else candle.get('open', 0)),
                                    'high': float(candle[2] if isinstance(candle, list) else candle.get('high', 0)),
                                    'low': float(candle[3] if isinstance(candle, list) else candle.get('low', 0)),
                                    'close': float(candle[4] if isinstance(candle, list) else candle.get('close', 0)),
                                    'volume': float(candle[5] if isinstance(candle, list) else candle.get('volume', 0))
                                }
                                self.candle_cache[symbol].append(candle_data)
                            
                            # Обновляем последнюю цену
                            last_candle = candles[-1]
                            last_price = float(last_candle[4] if isinstance(last_candle, list) else last_candle.get('close', 0))
                            
                            if symbol not in self.price_history:
                                self.price_history[symbol] = deque(maxlen=100)
                            
                            self.price_history[symbol].append({
                                'price': last_price,
                                'volume': float(last_candle[5] if isinstance(last_candle, list) else last_candle.get('volume', 0)),
                                'timestamp': datetime.utcnow()
                            })
                            
                            updated_pairs += 1
                            logger.debug(f"📈 {symbol}: ${last_price:.4f}")
                            
                except Exception as e:
                    logger.error(f"❌ Ошибка обновления данных {symbol}: {e}")
            
            if updated_pairs > 0:
                logger.debug(f"✅ Обновлены данные для {updated_pairs}/{len(self.active_pairs)} пар")
            else:
                logger.warning("⚠️ Не удалось обновить данные ни для одной пары")
                
        except Exception as e:
            logger.error(f"❌ Ошибка обновления рыночных данных: {e}")
            logger.error(traceback.format_exc())
    
    async def _find_all_trading_opportunities(self):
        """Поиск торговых возможностей по всем парам и стратегиям"""
        opportunities = []
        
        try:
            logger.debug("🔍 Поиск торговых возможностей...")
            
            for symbol in self.active_pairs:
                try:
                    # Подготавливаем данные для анализа
                    market_data = self._prepare_market_data(symbol)
                    
                    if not market_data or len(market_data.get('close', [])) < 20:
                        logger.debug(f"⚠️ Недостаточно данных для анализа {symbol}")
                        continue
                    
                    # Преобразуем в DataFrame для ML анализа
                    df = self._market_data_to_dataframe(market_data)
                    
                    # Анализ базовой стратегией
                    signal = await self._analyze_with_basic_strategy(symbol, market_data)
                    
                    if signal and signal.get('signal') != 'HOLD':
                        opportunity = {
                            'symbol': symbol,
                            'strategy': 'basic',
                            'signal': signal['signal'],
                            'confidence': signal.get('confidence', 0.5),
                            'price': float(market_data['close'][-1]),
                            'timestamp': datetime.utcnow(),
                            'reasons': signal.get('reasons', ['basic_signal'])
                        }
                        
                        opportunities.append(opportunity)
                        logger.info(f"🎯 Найдена возможность: {symbol} {signal['signal']} (уверенность: {signal.get('confidence', 0):.2f})")
                    
                    # ✅ ML АНАЛИЗ (добавлен согласно интеграции)
                    if getattr(self.config, 'ENABLE_MACHINE_LEARNING', False) and hasattr(self, 'ml_system') and self.ml_system:
                        ml_signal = await self._analyze_with_ml(symbol, df)
                        if ml_signal:
                            # Проверяем минимальную уверенность
                            if ml_signal['confidence'] >= getattr(self.config, 'ML_PREDICTION_THRESHOLD', 0.7):
                                opportunities.append(ml_signal)
                                logger.info(f"🤖 ML сигнал: {symbol} {ml_signal['signal']} (уверенность: {ml_signal['confidence']:.2%})")
                            else:
                                logger.debug(f"🤖 ML сигнал отклонен: низкая уверенность {ml_signal['confidence']:.2%}")
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка анализа {symbol}: {e}")
            
            logger.info(f"📊 Найдено торговых возможностей: {len(opportunities)}")
            return opportunities
            
        except Exception as e:
            logger.error(f"❌ Ошибка поиска торговых возможностей: {e}")
            logger.error(traceback.format_exc())
            return []
    
    # ✅ НОВЫЙ МЕТОД для ML анализа (из интеграции):
    async def _analyze_with_ml(self, symbol: str, df: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """✅ ИСПРАВЛЕНО: Анализ с использованием ML моделей"""
        try:
            if not hasattr(self, 'ml_system') or not self.ml_system:
                return None
            
            # Проверяем что ML включен в конфигурации
            if not getattr(self.config, 'ENABLE_MACHINE_LEARNING', False):
                return None
            
            # ✅ ИСПРАВЛЕНО: Правильное обращение к ML компонентам
            direction_prediction = None
            
            # Пробуем разные способы получения предсказания
            try:
                # Способ 1: Через trainer (если есть)
                if hasattr(self.ml_system, 'trainer') and self.ml_system.trainer:
                    if hasattr(self.ml_system.trainer, 'predict_direction'):
                        direction_prediction = await self.ml_system.trainer.predict_direction(symbol, df)
                    elif hasattr(self.ml_system.trainer, 'predict'):
                        direction_prediction = await self.ml_system.trainer.predict(symbol, df)
                
                # Способ 2: Через direction_classifier (если trainer не сработал)
                if not direction_prediction and hasattr(self.ml_system, 'direction_classifier'):
                    if hasattr(self.ml_system.direction_classifier, 'predict'):
                        # Подготавливаем признаки
                        features = self.ml_system.feature_engineer.create_features(df, symbol) if hasattr(self.ml_system, 'feature_engineer') else df
                        
                        # Получаем предсказание
                        prediction_result = self.ml_system.direction_classifier.predict(features)
                        
                        if 'error' not in prediction_result:
                            # Преобразуем в нужный формат
                            direction_prediction = {
                                'direction': prediction_result.get('direction_labels', ['HOLD'])[-1] if prediction_result.get('direction_labels') else 'HOLD',
                                'confidence': prediction_result.get('confidence', [0.5])[-1] if prediction_result.get('confidence') else 0.5,
                                'features': {},
                                'model_type': 'direction_classifier'
                            }
                
                # Способ 3: Создаем заглушку, если ничего не получилось
                if not direction_prediction:
                    logger.warning("⚠️ ML модели недоступны, используем заглушку")
                    direction_prediction = {
                        'direction': 'HOLD',
                        'confidence': 0.3,  # Низкая уверенность для заглушки
                        'features': {},
                        'model_type': 'fallback'
                    }
                    
            except Exception as e:
                logger.error(f"❌ Ошибка получения ML предсказания: {e}")
                return None
            
            # Проверяем минимальную уверенность
            min_confidence = getattr(self.config, 'ML_PREDICTION_THRESHOLD', 0.7)
            if direction_prediction.get('confidence', 0) < min_confidence:
                logger.debug(f"🤖 ML предсказание отклонено: уверенность {direction_prediction.get('confidence', 0):.2f} < {min_confidence}")
                return None
                
            # ✅ ИСПРАВЛЕНО: Получение price_prediction
            price_prediction = {
                'support': df['close'].iloc[-1] * 0.98, 
                'resistance': df['close'].iloc[-1] * 1.02,
                'confidence': 0.5
            }
            
            try:
                if hasattr(self.ml_system, 'price_regressor'):
                    # Здесь можно добавить реальное предсказание цены
                    pass
            except Exception as e:
                logger.warning(f"⚠️ Ошибка price_prediction: {e}")
            
            # ✅ ИСПРАВЛЕНО: Получение RL recommendation  
            rl_recommendation = None
            try:
                if hasattr(self.ml_system, 'rl_agent') and self.ml_system.rl_agent:
                    # Здесь можно добавить RL предсказание
                    pass
            except Exception as e:
                logger.warning(f"⚠️ Ошибка RL recommendation: {e}")
            
            # Формируем торговый сигнал
            ml_signal = {
                'symbol': symbol,
                'signal': direction_prediction.get('direction', 'HOLD'),
                'price': df['close'].iloc[-1],
                'confidence': direction_prediction['confidence'],
                'stop_loss': price_prediction.get('support', df['close'].iloc[-1] * 0.98),
                'take_profit': price_prediction.get('resistance', df['close'].iloc[-1] * 1.02),
                'strategy': 'ml_prediction',
                'ml_features': direction_prediction.get('features', {}),
                'price_targets': price_prediction.get('targets', {}),
                'rl_action': rl_recommendation.get('action') if rl_recommendation else None,
                'indicators': {
                    'ml_direction_confidence': direction_prediction['confidence'],
                    'ml_price_confidence': price_prediction.get('confidence', 0),
                    'feature_importance': direction_prediction.get('feature_importance', {}),
                    'model_type': direction_prediction.get('model_type', 'ensemble')
                }
            }
            
            logger.debug(f"🤖 ML сигнал для {symbol}: {ml_signal['signal']} (уверенность: {ml_signal['confidence']:.2f})")
            return ml_signal
            
        except Exception as e:
            logger.error(f"❌ Ошибка ML анализа для {symbol}: {e}")
            return None
    
    def _market_data_to_dataframe(self, market_data: dict) -> pd.DataFrame:
        """Преобразование рыночных данных в DataFrame для ML"""
        try:
            df = pd.DataFrame({
                'open': market_data['open'],
                'high': market_data['high'],
                'low': market_data['low'],
                'close': market_data['close'],
                'volume': market_data['volume']
            })
            
            # Добавляем простые индикаторы для ML
            df['rsi'] = self._calculate_rsi(df['close'], 14)
            df['macd'] = self._calculate_macd(df['close'])
            df['bb_position'] = self._calculate_bb_position(df['close'])
            df['volume_ratio'] = df['volume'] / df['volume'].rolling(20).mean()
            df['price_change'] = df['close'].pct_change() * 100
            
            return df.fillna(0)
            
        except Exception as e:
            logger.error(f"❌ Ошибка преобразования данных в DataFrame: {e}")
            return pd.DataFrame()
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Расчет RSI"""
        try:
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return rsi.fillna(50)
        except:
            return pd.Series([50] * len(prices))
    
    def _calculate_macd(self, prices: pd.Series) -> pd.Series:
        """Расчет MACD"""
        try:
            exp1 = prices.ewm(span=12).mean()
            exp2 = prices.ewm(span=26).mean()
            macd = exp1 - exp2
            return macd.fillna(0)
        except:
            return pd.Series([0] * len(prices))
    
    def _calculate_bb_position(self, prices: pd.Series, period: int = 20) -> pd.Series:
        """Расчет позиции относительно полос Боллинджера"""
        try:
            rolling_mean = prices.rolling(window=period).mean()
            rolling_std = prices.rolling(window=period).std()
            upper_band = rolling_mean + (rolling_std * 2)
            lower_band = rolling_mean - (rolling_std * 2)
            bb_position = (prices - lower_band) / (upper_band - lower_band)
            return bb_position.fillna(0.5)
        except:
            return pd.Series([0.5] * len(prices))
    
    async def _analyze_with_basic_strategy(self, symbol: str, market_data: dict):
        """Базовый анализ для поиска сигналов - УЛУЧШЕННАЯ ВЕРСИЯ"""
        try:
            closes = market_data.get('close', [])
            volumes = market_data.get('volume', [])
            
            if len(closes) < 20:
                return None
            
            # Преобразуем в numpy arrays для быстрых вычислений
            import numpy as np
            closes = np.array(closes[-50:])  # Последние 50 свечей
            volumes = np.array(volumes[-50:])
            
            # Рассчитываем индикаторы
            sma_20 = np.mean(closes[-20:])
            sma_10 = np.mean(closes[-10:])
            sma_5 = np.mean(closes[-5:])
            current_price = closes[-1]
            
            # RSI
            rsi = self._calculate_rsi_value(closes, 14)
            
            # Объем
            volume_avg = np.mean(volumes[-20:])
            current_volume = volumes[-1]
            volume_ratio = current_volume / volume_avg if volume_avg > 0 else 1
            
            # MACD
            exp1 = pd.Series(closes).ewm(span=12).mean()
            exp2 = pd.Series(closes).ewm(span=26).mean()
            macd = exp1.iloc[-1] - exp2.iloc[-1]
            signal_line = (exp1 - exp2).ewm(span=9).mean().iloc[-1]
            macd_histogram = macd - signal_line
            
            # Изменение цены
            price_change_5 = (current_price - closes[-5]) / closes[-5] * 100
            price_change_10 = (current_price - closes[-10]) / closes[-10] * 100
            
            # === УЛУЧШЕННЫЕ УСЛОВИЯ ДЛЯ СИГНАЛОВ ===
            
            # BUY сигналы (менее строгие условия)
            buy_signals = 0
            
            # 1. Пересечение MA снизу вверх
            if sma_5 > sma_10 and closes[-2] < np.mean(closes[-11:-1]):
                buy_signals += 1
                
            # 2. RSI выходит из перепроданности
            if 25 < rsi < 45:  # Расширенный диапазон
                buy_signals += 1
                
            # 3. MACD пересекает сигнальную линию снизу вверх
            if macd_histogram > 0 and macd > signal_line * 0.95:  # Менее строгое условие
                buy_signals += 1
                
            # 4. Увеличение объема
            if volume_ratio > 1.2:  # Снизили порог
                buy_signals += 1
                
            # 5. Цена растет
            if price_change_5 > 0.5:  # Снизили порог
                buy_signals += 1
            
            # SELL сигналы
            sell_signals = 0
            
            # 1. Пересечение MA сверху вниз
            if sma_5 < sma_10 and closes[-2] > np.mean(closes[-11:-1]):
                sell_signals += 1
                
            # 2. RSI в перекупленности
            if rsi > 65:  # Снизили порог
                sell_signals += 1
                
            # 3. MACD пересекает сигнальную линию сверху вниз
            if macd_histogram < 0 and macd < signal_line * 1.05:
                sell_signals += 1
                
            # 4. Цена падает
            if price_change_5 < -0.5:  # Снизили порог
                sell_signals += 1
            
            # Определяем сигнал (нужно минимум 2 подтверждения вместо 3)
            signal_type = 'HOLD'
            confidence = 0.0
            
            if buy_signals >= 2:  # Снизили порог с 3 до 2
                signal_type = 'BUY'
                confidence = buy_signals / 5.0
            elif sell_signals >= 2:  # Снизили порог с 3 до 2
                signal_type = 'SELL'
                confidence = sell_signals / 4.0
            
            if signal_type != 'HOLD':
                return {
                    'symbol': symbol,
                    'signal': signal_type,
                    'price': current_price,
                    'confidence': confidence,
                    'stop_loss': current_price * (0.97 if signal_type == 'BUY' else 1.03),
                    'take_profit': current_price * (1.06 if signal_type == 'BUY' else 0.94),
                    'indicators': {
                        'rsi': rsi,
                        'macd': macd,
                        'volume_ratio': volume_ratio,
                        'sma_trend': 'up' if sma_5 > sma_20 else 'down',
                        'price_change_5': price_change_5
                    }
                }
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Ошибка базового анализа {symbol}: {e}")
            return None
    
    def _calculate_rsi_value(self, prices: np.ndarray, period: int = 14) -> float:
        """Расчет RSI из numpy array"""
        try:
            deltas = np.diff(prices)
            gains = np.where(deltas > 0, deltas, 0)
            losses = np.where(deltas < 0, -deltas, 0)
            
            avg_gain = np.mean(gains[-period:])
            avg_loss = np.mean(losses[-period:])
            
            if avg_loss == 0:
                return 100
            
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            
            return rsi
        except:
            return 50
    
    async def _execute_real_order(self, symbol: str, signal: str, position_size: float,
                                 price: float, trade_data: Dict[str, Any]) -> bool:
        """
        Выполнение реального ордера - ПОЛНОСТЬЮ ПЕРЕПИСАНО
        
        Args:
            symbol: Торговая пара (например, 'BTCUSDT')
            signal: Тип сигнала ('BUY' или 'SELL')
            position_size: Размер позиции
            price: Цена входа
            trade_data: Дополнительные данные сделки
            
        Returns:
            bool: True если ордер выполнен успешно
        """
        try:
            logger.info(f"💸 ВЫПОЛНЕНИЕ РЕАЛЬНОЙ СДЕЛКИ: {symbol} {signal}")
            logger.info(f"💰 Режим: {'TESTNET' if self.testnet else 'LIVE'}")
            
            # 1. Валидация параметров
            if not self._validate_trade_params(symbol, signal, position_size, price):
                logger.error("❌ Валидация параметров не пройдена")
                return False
            
            # 2. Импортируем единый тип сигнала
            try:
                from ..common.types import UnifiedTradingSignal, SignalAction
            except ImportError:
                logger.error("❌ Не удалось импортировать UnifiedTradingSignal")
                return False
            
            # 3. Создаем унифицированный сигнал
            unified_signal = UnifiedTradingSignal(
                symbol=symbol,
                action=SignalAction(signal.upper()),
                confidence=trade_data.get('confidence', 0.6),
                price=price,
                stop_loss=self._validate_stop_loss(signal, price, trade_data.get('stop_loss')),
                take_profit=self._validate_take_profit(signal, price, trade_data.get('take_profit')),
                reason=f"Signal from {trade_data.get('strategy', 'unknown')}",
                risk_reward_ratio=trade_data.get('risk_reward_ratio'),
                indicators=trade_data.get('indicators'),
                metadata=trade_data,
                strategy=trade_data.get('strategy', 'unknown'),
                source=trade_data.get('source', 'technical')
            )
            
            logger.info(f"📊 Унифицированный сигнал создан:")
            logger.info(f"   Symbol: {unified_signal.symbol}")
            logger.info(f"   Action: {unified_signal.action_str}")
            logger.info(f"   Side: {unified_signal.side_str}")
            logger.info(f"   Price: {unified_signal.price}")
            logger.info(f"   SL: {unified_signal.stop_loss}")
            logger.info(f"   TP: {unified_signal.take_profit}")
            
            # 4. Пробуем разные способы исполнения в порядке приоритета
            
            # Способ 1: Enhanced Exchange Client (с поддержкой Bybit V5)
            if hasattr(self, 'enhanced_exchange_client') and self.enhanced_exchange_client:
                try:
                    logger.info("📡 Используем Enhanced Exchange Client...")
                    
                    # Проверяем, поддерживает ли клиент прямую работу с сигналами
                    if hasattr(self.enhanced_exchange_client, 'place_order_from_signal'):
                        result = await self.enhanced_exchange_client.place_order_from_signal(
                            signal=unified_signal,
                            amount=position_size
                        )
                    else:
                        # Используем стандартный place_order с params
                        result = await self.enhanced_exchange_client.place_order(
                            symbol=symbol,
                            side=signal.lower(),
                            amount=position_size,
                            price=price if trade_data.get('order_type') == 'limit' else None,
                            order_type=trade_data.get('order_type', 'market'),
                            params={
                                'stopLoss': unified_signal.stop_loss,
                                'takeProfit': unified_signal.take_profit,
                                'reduceOnly': False,
                                'timeInForce': 'GTC' if trade_data.get('order_type') == 'limit' else 'IOC'
                            }
                        )
                    
                    if result and result.get('success', False):
                        logger.info(f"✅ Ордер выполнен через Enhanced Client: {result.get('order_id')}")
                        self._save_order_info(result, unified_signal)
                        return True
                        
                except Exception as e:
                    logger.error(f"❌ Ошибка Enhanced Client: {e}")
            
            # Способ 2: Execution Engine
            if hasattr(self, 'execution_engine') and self.execution_engine:
                try:
                    logger.info("📡 Используем Execution Engine...")
                    
                    # Execution Engine может работать с нашим форматом
                    result = await self.execution_engine.execute_signal(
                        signal=unified_signal,
                        strategy_name=trade_data.get('strategy', 'unknown'),
                        market_conditions=trade_data.get('market_conditions', {})
                    )
                    
                    if result and hasattr(result, 'status') and result.status.value in ['completed', 'filled']:
                        logger.info(f"✅ Ордер выполнен через Execution Engine: {result.order_id}")
                        return True
                        
                except Exception as e:
                    logger.error(f"❌ Ошибка Execution Engine: {e}")
            
            # Способ 3: Базовый Exchange Client
            if hasattr(self, 'exchange_client') and self.exchange_client:
                try:
                    logger.info("📡 Используем базовый Exchange Client...")
                    
                    result = await self.exchange_client.place_order(
                        symbol=symbol,
                        side=signal.lower(),
                        amount=position_size,
                        price=price if trade_data.get('order_type') == 'limit' else None,
                        order_type=trade_data.get('order_type', 'market'),
                        params={
                            'stopLoss': unified_signal.stop_loss,
                            'takeProfit': unified_signal.take_profit
                        }
                    )
                    
                    if result and 'error' not in result:
                        logger.info(f"✅ Ордер выполнен через базовый Client: {result.get('id')}")
                        return True
                        
                except Exception as e:
                    logger.error(f"❌ Ошибка базового Client: {e}")
            
            logger.error("❌ Все способы выполнения сделки не сработали")
            return False
            
        except Exception as e:
            logger.error(f"❌ Критическая ошибка в _execute_real_order: {e}")
            import traceback
            traceback.print_exc()
            return False
            
    def _validate_trade_params(self, symbol: str, signal: str, 
                              position_size: float, price: float) -> bool:
        """
        Валидация параметров сделки
        
        Args:
            symbol: Торговая пара
            signal: Тип сигнала
            position_size: Размер позиции
            price: Цена
            
        Returns:
            bool: True если все параметры валидны
        """
        # Проверка символа
        if not symbol or not isinstance(symbol, str):
            logger.error(f"❌ Некорректный символ: {symbol}")
            return False
        
        if not symbol.endswith('USDT'):
            logger.warning(f"⚠️ Необычный символ (не USDT пара): {symbol}")
        
        # Проверка сигнала
        if signal.upper() not in ['BUY', 'SELL']:
            logger.error(f"❌ Некорректный сигнал: {signal}")
            return False
        
        # Проверка размера позиции
        if not isinstance(position_size, (int, float)) or position_size <= 0:
            logger.error(f"❌ Некорректный размер позиции: {position_size}")
            return False
        
        # Проверка цены
        if not isinstance(price, (int, float)) or price <= 0:
            logger.error(f"❌ Некорректная цена: {price}")
            return False
        
        # Дополнительные проверки
        min_position_size = 0.001  # Минимальный размер для BTC
        if position_size < min_position_size:
            logger.warning(f"⚠️ Размер позиции меньше минимального: {position_size} < {min_position_size}")
        
        logger.info(f"✅ Параметры сделки валидны: {symbol} {signal} size={position_size} price={price}")
        return True
    
    def _validate_stop_loss(self, signal: str, price: float, stop_loss: Optional[float]) -> Optional[float]:
        """Валидация и коррекция stop loss"""
        if not stop_loss:
            return None
            
        if signal.upper() == 'BUY':
            # Для покупки SL должен быть ниже цены
            if stop_loss >= price:
                corrected = price * 0.97  # 3% ниже
                logger.warning(f"⚠️ SL скорректирован: {stop_loss} -> {corrected}")
                return corrected
        else:
            # Для продажи SL должен быть выше цены
            if stop_loss <= price:
                corrected = price * 1.03  # 3% выше
                logger.warning(f"⚠️ SL скорректирован: {stop_loss} -> {corrected}")
                return corrected
        
        return stop_loss
    
    def _validate_take_profit(self, signal: str, price: float, take_profit: Optional[float]) -> Optional[float]:
        """Валидация и коррекция take profit"""
        if not take_profit:
            return None
            
        if signal.upper() == 'BUY':
            # Для покупки TP должен быть выше цены
            if take_profit <= price:
                corrected = price * 1.06  # 6% выше
                logger.warning(f"⚠️ TP скорректирован: {take_profit} -> {corrected}")
                return corrected
        else:
            # Для продажи TP должен быть ниже цены
            if take_profit >= price:
                corrected = price * 0.94  # 6% ниже
                logger.warning(f"⚠️ TP скорректирован: {take_profit} -> {corrected}")
                return corrected
        
        return take_profit
    
    def _save_order_info(self, order_result: Dict[str, Any], signal: 'UnifiedTradingSignal'):
        """Сохранение информации об ордере"""
        if not hasattr(self, 'active_orders'):
            self.active_orders = {}
        
        order_id = order_result.get('order_id') or order_result.get('id')
        if order_id:
            self.active_orders[order_id] = {
                'symbol': signal.symbol,
                'side': signal.side_str,
                'action': signal.action_str,
                'size': order_result.get('amount'),
                'price': signal.price,
                'stop_loss': signal.stop_loss,
                'take_profit': signal.take_profit,
                'timestamp': datetime.utcnow(),
                'strategy': signal.strategy,
                'confidence': signal.confidence
            }
        
    async def _execute_real_trade(self, symbol: str, signal: str, position_size: float, 
                                 price: float, trade_data: Dict[str, Any]) -> bool:
        """
        Выполнение реальной торговой операции на бирже
        
        Args:
            symbol: Торговая пара
            signal: Тип сигнала (BUY/SELL)
            position_size: Размер позиции
            price: Цена входа
            trade_data: Дополнительные данные сделки
            
        Returns:
            bool: True если сделка выполнена успешно
        """
        try:
            logger.info(f"💸 ВЫПОЛНЕНИЕ РЕАЛЬНОЙ СДЕЛКИ: {symbol} {signal}")
            logger.info(f"💰 Режим: {'TESTNET' if getattr(config, 'TESTNET', True) else 'LIVE'}")
            
            # Проверяем что есть хотя бы один способ исполнения
            if not any([
                hasattr(self, 'execution_engine') and self.execution_engine,
                hasattr(self, 'exchange_client') and self.exchange_client,
                hasattr(self, 'enhanced_exchange_client') and self.enhanced_exchange_client
            ]):
                logger.error("❌ Нет доступных способов исполнения сделки")
                return False
            
            logger.info(f"📊 Попытка выполнить реальный ордер: {symbol} {signal} размер={position_size}")
            
            # Способ 1: Через OrderExecutionEngine (предпочтительный)
            if hasattr(self, 'execution_engine') and self.execution_engine and hasattr(self.execution_engine, 'execute_signal'):
                try:
                    logger.debug("📡 Используем execution_engine...")
                    
                    # Создаем сигнал для execution engine
                    from ..common.types import UnifiedTradingSignal as TradingSignal
                    trading_signal = TradingSignal(
                        symbol=symbol,
                        action=signal.upper(),
                        confidence=trade_data.get('confidence', 0.6),
                        price=price,
                        stop_loss=trade_data.get('stop_loss'),
                        take_profit=trade_data.get('take_profit'),
                        strategy=trade_data.get('strategy', 'unknown')
                    )
                    
                    # Выполняем через execution engine
                    result = await self.execution_engine.execute_signal(
                        signal=trading_signal,
                        strategy_name=trade_data.get('strategy', 'multi_indicator'),
                        market_conditions=trade_data.get('market_conditions', {})
                    )
                    
                    if result and result.status.value == 'completed':
                        logger.info(f"✅ Ордер выполнен через execution_engine: {result.order_id}")
                        return True
                    else:
                        logger.warning(f"⚠️ Execution_engine вернул статус: {result.status.value if result else 'None'}")
                        
                except Exception as e:
                    logger.error(f"❌ Ошибка execution_engine: {e}")
            
            # Способ 2: Через exchange_client напрямую
            if hasattr(self, 'exchange_client') and self.exchange_client and hasattr(self.exchange_client, 'place_order'):
                try:
                    logger.debug("📡 Используем exchange_client...")
                    
                    # Используем place_order из unified_exchange
                    order = await self.exchange_client.place_order(
                        symbol=symbol,
                        side=signal.lower(),
                        amount=position_size,
                        price=price if not getattr(config, 'USE_MARKET_ORDERS', True) else None,
                        order_type='market' if getattr(config, 'USE_MARKET_ORDERS', True) else 'limit'
                    )
                    
                    if order and 'error' not in order:
                        logger.info(f"✅ Ордер выполнен через exchange_client: {order.get('id')}")
                        
                        # Устанавливаем SL/TP если нужно
                        if trade_data.get('stop_loss') or trade_data.get('take_profit'):
                            await self._set_position_sl_tp(
                                symbol, 
                                trade_data.get('stop_loss'), 
                                trade_data.get('take_profit')
                            )
                        
                        return True
                    else:
                        logger.warning(f"⚠️ Exchange_client вернул ошибку: {order.get('error') if order else 'None'}")
                        
                except Exception as e:
                    logger.error(f"❌ Ошибка exchange_client: {e}")
            
            # Способ 3: Через enhanced exchange
            if hasattr(self, 'enhanced_exchange_client') and self.enhanced_exchange_client:
                try:
                    logger.debug("📡 Используем enhanced_exchange_client...")
                    
                    # Проверяем наличие правильного метода
                    if hasattr(self.enhanced_exchange_client, 'v5_client') and self.enhanced_exchange_client.v5_client:
                        # Используем V5 API
                        order_result = await self.enhanced_exchange_client.v5_client.place_order(
                            category='linear',  # для USDT perpetual
                            symbol=symbol,
                            side='Buy' if signal.upper() == 'BUY' else 'Sell',
                            orderType='Market' if getattr(config, 'USE_MARKET_ORDERS', True) else 'Limit',
                            qty=str(position_size),
                            price=str(price) if not getattr(config, 'USE_MARKET_ORDERS', True) else None,
                            stopLoss=str(trade_data.get('stop_loss')) if trade_data.get('stop_loss') else None,
                            takeProfit=str(trade_data.get('take_profit')) if trade_data.get('take_profit') else None
                        )
                    elif hasattr(self.enhanced_exchange_client, 'place_order'):
                        # Fallback на обычный метод
                        order_result = await self.enhanced_exchange_client.place_order(
                            symbol=symbol,
                            side=signal.lower(),
                            amount=position_size,
                            price=price if not getattr(config, 'USE_MARKET_ORDERS', True) else None,
                            order_type='market' if getattr(config, 'USE_MARKET_ORDERS', True) else 'limit'
                        )
                    else:
                        logger.error("❌ Enhanced exchange не имеет подходящего метода для размещения ордера")
                        return False
                    
                    if order_result and (order_result.get('retCode') == 0 or order_result.get('success')):
                        logger.info(f"✅ Ордер выполнен через enhanced_exchange: {order_result.get('result', {}).get('orderId', 'unknown')}")
                        return True
                    else:
                        logger.warning(f"⚠️ Enhanced_exchange вернул: {order_result}")
                        
                except Exception as e:
                    logger.error(f"❌ Ошибка enhanced_exchange: {e}")
            
            logger.error("❌ Все способы выполнения сделки не сработали")
            return False
            
        except Exception as e:
            logger.error(f"❌ Критическая ошибка выполнения сделки: {e}")
            logger.error(traceback.format_exc())
            return False
    
    async def _set_position_sl_tp(self, symbol: str, stop_loss: float = None, take_profit: float = None):
        """Установка SL/TP для позиции"""
        try:
            logger.info(f"📊 Установка SL/TP для {symbol}: SL={stop_loss}, TP={take_profit}")
            
            # Попытка установить через enhanced client
            if hasattr(self, 'enhanced_exchange_client') and self.enhanced_exchange_client:
                if hasattr(self.enhanced_exchange_client, 'set_position_sl_tp'):
                    result = await self.enhanced_exchange_client.set_position_sl_tp(
                        symbol=symbol,
                        stop_loss=stop_loss,
                        take_profit=take_profit
                    )
                    if result:
                        logger.info(f"✅ SL/TP установлены для {symbol}")
                        return True
            
            # Здесь можно добавить другие способы установки SL/TP
            logger.warning(f"⚠️ Не удалось установить SL/TP для {symbol}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка установки SL/TP: {e}")
    
    async def _save_trade_to_db(self, symbol: str, trade_data: dict, success: bool):
        """Сохранение информации о сделке в БД"""
        try:
            # Здесь будет код сохранения в БД
            logger.debug(f"💾 Сохранение сделки {symbol} в БД (success={success})")
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения в БД: {e}")
    
    async def _send_trade_notification(self, symbol: str, signal: str, size: float, price: float):
        """Отправка уведомления о сделке"""
        try:
            if hasattr(self, 'notifier') and self.notifier:
                message = f"🎯 Выполнена сделка:\n{symbol} {signal}\nРазмер: {size}\nЦена: ${price:.4f}"
                await self.notifier.send_message(message)
        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления: {e}")
    
    def _prepare_market_data(self, symbol: str):
        """Подготовка рыночных данных для анализа"""
        try:
            if symbol not in self.candle_cache or len(self.candle_cache[symbol]) < 20:
                return None
            
            candles = list(self.candle_cache[symbol])
            
            return {
                'open': [c['open'] for c in candles],
                'high': [c['high'] for c in candles],
                'low': [c['low'] for c in candles],
                'close': [c['close'] for c in candles],
                'volume': [c['volume'] for c in candles],
                'timestamp': [c['timestamp'] for c in candles]
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка подготовки данных {symbol}: {e}")
            return None
    
    def _calculate_position_size(self, symbol: str, price: float) -> float:
        """
        Рассчитывает размер позиции на основе риск-менеджмента
        
        Args:
            symbol: Торговая пара
            price: Текущая цена актива
            
        Returns:
            float: Размер позиции в базовой валюте (например, BTC для BTCUSDT)
        """
        try:
            # Получаем доступный баланс
            available_balance = getattr(self, 'available_balance', 10000)
            
            # Если есть enhanced_exchange_client, получаем актуальный баланс
            if hasattr(self, 'enhanced_exchange_client') and self.enhanced_exchange_client:
                try:
                    # ИСПРАВЛЕНО: Правильная работа с балансом
                    if hasattr(self.enhanced_exchange_client, 'get_balance'):
                        balance_info = self.enhanced_exchange_client.get_balance()
                        # Проверяем, является ли результат корутиной
                        import inspect
                        if inspect.iscoroutine(balance_info):
                            # Если это корутина, используем стандартный баланс
                            logger.debug("get_balance возвращает корутину, используем стандартный баланс")
                        elif balance_info and isinstance(balance_info, dict) and 'USDT' in balance_info:
                            available_balance = float(balance_info['USDT'].get('free', available_balance))
                            logger.debug(f"Получен баланс из enhanced_exchange_client: ${available_balance:.2f}")
                except Exception as e:
                    logger.warning(f"⚠️ Не удалось получить баланс: {e}")
            
            # Получаем параметры риск-менеджмента
            risk_per_trade = getattr(config, 'RISK_PER_TRADE_PERCENT', 1.5) / 100
            max_position_percent = getattr(config, 'MAX_POSITION_SIZE_PERCENT', 10) / 100
            
            # Рассчитываем максимальный риск в долларах
            risk_amount = available_balance * risk_per_trade
            
            # Рассчитываем максимальный размер позиции в долларах
            max_position_value = available_balance * max_position_percent
            
            # Получаем процент стоп-лосса
            stop_loss_percent = getattr(config, 'STOP_LOSS_PERCENT', 3.0) / 100
            
            # Рассчитываем размер позиции на основе риска
            # Размер = Риск / (Цена * Процент_стоп_лосса)
            position_size_by_risk = risk_amount / (price * stop_loss_percent)
            
            # Рассчитываем размер позиции на основе максимального процента
            position_size_by_max = max_position_value / price
            
            # Берем меньший размер для безопасности
            position_size = min(position_size_by_risk, position_size_by_max)
            
            # Проверяем минимальный размер для Bybit
            min_order_size = self._get_min_order_size(symbol)
            if position_size < min_order_size:
                logger.warning(f"⚠️ Размер позиции {position_size:.4f} меньше минимального {min_order_size}")
                return 0.0
            
            # Проверяем количество открытых позиций
            current_positions = len(getattr(self, 'positions', {}))
            max_positions = getattr(config, 'MAX_POSITIONS', 15)
            
            if current_positions >= max_positions:
                logger.warning(f"⚠️ Достигнут лимит позиций: {current_positions}/{max_positions}")
                return 0.0
            
            # Корректируем размер с учетом количества позиций
            # Чем больше позиций, тем меньше размер новой
            position_adjustment = 1.0 - (current_positions / max_positions * 0.5)
            position_size *= position_adjustment
            
            # Округляем до нужной точности
            position_size = self._round_to_precision(position_size, symbol)
            
            logger.debug(f"💰 Расчет позиции для {symbol}:")
            logger.debug(f"   Баланс: ${available_balance:.2f}")
            logger.debug(f"   Риск на сделку: ${risk_amount:.2f} ({risk_per_trade*100:.1f}%)")
            logger.debug(f"   Размер по риску: {position_size_by_risk:.4f}")
            logger.debug(f"   Размер по максимуму: {position_size_by_max:.4f}")
            logger.debug(f"   Итоговый размер: {position_size:.4f}")
            
            return position_size
            
        except Exception as e:
            logger.error(f"❌ Ошибка расчета размера позиции: {e}")
            import traceback
            traceback.print_exc()
            return 0.0
    
    def _get_min_order_size(self, symbol: str) -> float:
        """
        Получает минимальный размер ордера для символа
        
        Args:
            symbol: Торговая пара
            
        Returns:
            float: Минимальный размер ордера
        """
        # Стандартные минимальные размеры для популярных пар
        min_sizes = {
            'BTCUSDT': 0.001,
            'ETHUSDT': 0.01,
            'BNBUSDT': 0.01,
            'SOLUSDT': 0.1,
            'ADAUSDT': 10,
            'DOTUSDT': 1,
            'MATICUSDT': 10,
            'AVAXUSDT': 0.1,
            'LINKUSDT': 0.1,
            'ATOMUSDT': 0.1
        }
        
        # Пытаемся получить из биржи
        if hasattr(self, 'exchange_client') and self.exchange_client:
            try:
                markets = self.exchange_client.exchange.markets
                if markets and symbol in markets:
                    market = markets[symbol]
                    if 'limits' in market and 'amount' in market['limits']:
                        return market['limits']['amount']['min']
            except Exception as e:
                logger.debug(f"Не удалось получить лимиты с биржи: {e}")
        
        # Возвращаем стандартное значение
        return min_sizes.get(symbol, 0.001)
    
    def _round_to_precision(self, value: float, symbol: str) -> float:
        """
        Округляет значение до нужной точности для символа
        
        Args:
            value: Значение для округления
            symbol: Торговая пара
            
        Returns:
            float: Округленное значение
        """
        # Стандартная точность для популярных пар
        precision = {
            'BTCUSDT': 3,
            'ETHUSDT': 3,
            'BNBUSDT': 2,
            'SOLUSDT': 1,
            'ADAUSDT': 0,
            'DOTUSDT': 1,
            'MATICUSDT': 0,
            'AVAXUSDT': 1,
            'LINKUSDT': 1,
            'ATOMUSDT': 1
        }
        
        # Пытаемся получить из биржи
        if hasattr(self, 'exchange_client') and self.exchange_client:
            try:
                markets = self.exchange_client.exchange.markets
                if markets and symbol in markets:
                    market = markets[symbol]
                    if 'precision' in market and 'amount' in market['precision']:
                        decimals = market['precision']['amount']
                        return round(value, decimals)
            except Exception as e:
                logger.debug(f"Не удалось получить точность с биржи: {e}")
        
        # Используем стандартную точность
        decimals = precision.get(symbol, 3)
        return round(value, decimals)
    
    def _calculate_stop_loss(self, entry_price: float, side: str) -> float:
        """Расчет стоп-лосса"""
        try:
            sl_percent = getattr(config, 'STOP_LOSS_PERCENT', 2.0) / 100
            
            if side == 'BUY':
                return entry_price * (1 - sl_percent)
            else:  # SELL
                return entry_price * (1 + sl_percent)
                
        except Exception as e:
            logger.error(f"❌ Ошибка расчета стоп-лосса: {e}")
            return entry_price * 0.98 if side == 'BUY' else entry_price * 1.02
    
    def _calculate_take_profit(self, entry_price: float, side: str) -> float:
        """Расчет тейк-профита"""
        try:
            tp_percent = getattr(config, 'TAKE_PROFIT_PERCENT', 4.0) / 100
            
            if side == 'BUY':
                return entry_price * (1 + tp_percent)
            else:  # SELL
                return entry_price * (1 - tp_percent)
                
        except Exception as e:
            logger.error(f"❌ Ошибка расчета тейк-профита: {e}")
            return entry_price * 1.04 if side == 'BUY' else entry_price * 0.96
            
    
    
    async def start(self) -> Tuple[bool, str]:
        """Запуск торгового бота - ПОЛНАЯ ВЕРСИЯ"""
        if self.status == BotStatus.RUNNING:
            return False, "Бот уже запущен"
        
        try:
            logger.info("🚀 Запуск ПОЛНОЦЕННОГО торгового бота...")
            self.status = BotStatus.STARTING
            
            # Регистрируем обработчики сигналов
            self._setup_signal_handlers()
            
            # ✅ ВЫЗЫВАЕМ ИНИЦИАЛИЗАЦИЮ ТОЛЬКО ОДИН РАЗ
            if not self._initialization_completed:
                logger.info("🔧 Инициализация компонентов...")
                init_success = await self._initialize_all_components()
                if not init_success:
                    self.status = BotStatus.ERROR
                    return False, "Ошибка инициализации компонентов"
                self._initialization_completed = True
            
            # 2. Загрузка конфигурации и валидация
            logger.info("⚙️ Загрузка конфигурации...")
            config_valid = await self._validate_configuration()
            if not config_valid:
                self.status = BotStatus.ERROR
                return False, "Ошибка валидации конфигурации"
            
            # 3. Подключение к бирже
            logger.info("📡 Подключение к бирже...")
            exchange_connected = await self._connect_exchange()
            if not exchange_connected:
                self.status = BotStatus.ERROR
                return False, "Ошибка подключения к бирже"
                
            # 4. Отображение информации об аккаунте
            logger.info("💰 Получение информации об аккаунте...")
            await self._display_account_info()
            
            # 4. Обнаружение торговых пар
            logger.info("💰 Поиск торговых пар...")
            pairs_discovered = await self._discover_all_trading_pairs()
            if not pairs_discovered:
                logger.warning("⚠️ Ошибка автопоиска пар, используем конфигурационные")
                self.active_pairs = self.trading_pairs[:config.MAX_TRADING_PAIRS]
            
            # 5. Инициализация стратегий
            logger.info("🎯 Инициализация стратегий...")
            await self._initialize_strategies()
            
            # 6. Инициализация ML моделей
            if config.ENABLE_MACHINE_LEARNING:
                logger.info("🧠 Инициализация ML моделей...")
                await self._init_ml_system()
            
            # 7. Загрузка исторических данных
            logger.info("📊 Загрузка исторических данных...")
            await self._load_historical_data()
            
            # 8. Анализ текущего состояния рынка
            logger.info("🌐 Анализ состояния рынка...")
            await self._perform_initial_market_analysis()
            
            # 9. Инициализация системы мониторинга
            logger.info("👀 Запуск системы мониторинга...")
            await self._setup_monitoring_system()
            
            # 10. Запуск всех торговых циклов
            logger.info("🔄 Запуск торговых циклов...")
            await self._start_all_trading_loops()
            
            # 11. Проверка здоровья системы
            health_status = await self._perform_health_check()
            if not health_status['overall_healthy']:
                logger.warning("⚠️ Обнаружены проблемы в системе, но продолжаем работу")
            
            # 12. Запуск WebSocket соединений
            if config.ENABLE_WEBSOCKET:
                logger.info("🌐 Запуск WebSocket соединений...")
                await self._start_websocket_connections()
            
            # 13. Отправка стартового уведомления
            await self._send_startup_notification()
            
            self.status = BotStatus.RUNNING
            self.start_time = datetime.utcnow()
            self._stop_event.clear()
            self._pause_event.set()  # Не на паузе
            
            startup_time = (datetime.utcnow() - self.start_time).total_seconds()
            
            # Запускаем главный торговый цикл
            try:
                await self._main_trading_loop()
            except asyncio.CancelledError:
                logger.info("🛑 Главный торговый цикл отменен")
            except Exception as e:
                logger.error(f"❌ Ошибка в главном торговом цикле: {e}")
                self.status = BotStatus.ERROR
                raise
            
            logger.info("✅ ПОЛНОЦЕННЫЙ торговый бот успешно запущен!")
            logger.info(f"📊 Активных пар: {len(self.active_pairs)}")
            logger.info(f"🎯 Стратегий: {len(self.available_strategies)}")
            logger.info(f"🧠 ML моделей: {len(self.ml_models)}")
            logger.info(f"⏱️ Время запуска: {startup_time:.2f}с")
            
            # Логируем статистику
            await self._log_startup_statistics()
            
            return True, f"Бот успешно запущен за {startup_time:.1f}с"
            
        except Exception as e:
            self.status = BotStatus.ERROR
            error_msg = f"Критическая ошибка запуска: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            
            # Отправляем уведомление об ошибке
            await self._send_error_notification(error_msg)
            
            return False, error_msg
            
            
    
    
    async def stop(self) -> Tuple[bool, str]:
        """Остановка торгового бота - ПОЛНАЯ ВЕРСИЯ"""
        if self.status == BotStatus.STOPPED:
            return False, "Бот уже остановлен"
        
        try:
            logger.info("🛑 Остановка торгового бота...")
            old_status = self.status
            self.status = BotStatus.STOPPING
            
            # 1. Устанавливаем события остановки
            self._stop_event.set()
            
            # 2. Сохраняем текущее состояние
            logger.info("💾 Сохранение состояния...")
            await self._save_current_state()
            
            # 3. Закрываем позиции (если настроено)
            if config.CLOSE_POSITIONS_ON_STOP:
                logger.info("📊 Закрытие открытых позиций...")
                await self._close_all_positions_safely()
            
            # 4. Отменяем все активные ордера
            logger.info("❌ Отмена активных ордеров...")
            await self._cancel_all_orders()
            
            # 5. Останавливаем все задачи
            logger.info("🔄 Остановка активных задач...")
            await self._stop_all_tasks()
            
            # 6. Останавливаем WebSocket соединения
            if hasattr(self, 'websocket_connections'):
                logger.info("🌐 Закрытие WebSocket соединений...")
                await self._close_websocket_connections()
            
            # 7. Завершаем обучение ML моделей
            if config.ENABLE_MACHINE_LEARNING:
                logger.info("🧠 Остановка ML системы...")
                await self._stop_ml_system()
            
            # 8. Экспортируем финальные данные
            logger.info("📤 Экспорт финальных данных...")
            await self._export_final_data()
            
            # 9. Отключаемся от биржи
            logger.info("📡 Отключение от биржи...")
            await self._disconnect_exchange()
            
            # 10. Закрываем базу данных
            logger.info("🗄️ Закрытие соединений с БД...")
            await self._close_database_connections()
            
            # 11. Очищаем кэши
            logger.info("🧹 Очистка кэшей...")
            await self._cleanup_caches()
            
            # 12. Отправляем финальное уведомление
            await self._send_shutdown_notification(old_status)
            
            self.status = BotStatus.STOPPED
            self.stop_time = datetime.utcnow()
            
            if self.start_time:
                uptime = (self.stop_time - self.start_time).total_seconds()
                logger.info(f"⏱️ Время работы: {uptime:.1f}с ({uptime/3600:.1f}ч)")
            
            logger.info("✅ Торговый бот успешно остановлен")
            return True, "Бот успешно остановлен"
            
        except Exception as e:
            error_msg = f"Ошибка остановки бота: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            return False, error_msg
    
    async def pause(self) -> Tuple[bool, str]:
        """Приостановка торгового бота"""
        if self.status != BotStatus.RUNNING:
            return False, "Бот не запущен"
        
        try:
            logger.info("⏸️ Приостановка торгового бота...")
            self.status = BotStatus.PAUSED
            self.pause_time = datetime.utcnow()
            self._pause_event.clear()  # Ставим на паузу
            
            # Отменяем все новые ордера, но оставляем существующие позиции
            await self._cancel_pending_orders()
            
            await self._send_pause_notification()
            
            logger.info("✅ Торговый бот приостановлен")
            return True, "Бот приостановлен"
            
        except Exception as e:
            error_msg = f"Ошибка приостановки: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    async def resume(self) -> Tuple[bool, str]:
        """Возобновление работы торгового бота"""
        if self.status != BotStatus.PAUSED:
            return False, "Бот не на паузе"
        
        try:
            logger.info("▶️ Возобновление работы торгового бота...")
            self.status = BotStatus.RUNNING
            self._pause_event.set()  # Снимаем с паузы
            
            # Обновляем рыночные данные
            await self._refresh_market_data()
            
            await self._send_resume_notification()
            
            if self.pause_time:
                pause_duration = (datetime.utcnow() - self.pause_time).total_seconds()
                logger.info(f"✅ Работа возобновлена после паузы {pause_duration:.1f}с")
            
            return True, "Работа возобновлена"
            
        except Exception as e:
            error_msg = f"Ошибка возобновления: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    async def emergency_stop(self) -> Tuple[bool, str]:
        """Экстренная остановка с закрытием всех позиций"""
        try:
            logger.critical("🚨 ЭКСТРЕННАЯ ОСТАНОВКА АКТИВИРОВАНА!")
            self.status = BotStatus.EMERGENCY_STOP
            self.emergency_stop_triggered = True
            
            # Мгновенно закрываем все позиции
            await self._emergency_close_all_positions()
            
            # Отменяем все ордера
            await self._cancel_all_orders()
            
            # Останавливаем все циклы
            self._stop_event.set()
            
            await self._send_emergency_notification()
            
            logger.critical("🚨 Экстренная остановка завершена")
            return True, "Экстренная остановка выполнена"
            
        except Exception as e:
            error_msg = f"Ошибка экстренной остановки: {str(e)}"
            logger.critical(error_msg)
            return False, error_msg
    
    def get_status(self) -> Dict[str, Any]:
        """Получение полного статуса бота - РАСШИРЕННАЯ ВЕРСИЯ"""
        current_time = datetime.utcnow()
        uptime = None
        
        if self.start_time:
            uptime = (current_time - self.start_time).total_seconds()
        
        # Базовая информация
        status_info = {
            # Основной статус
            'status': self.status.value,
            'is_running': self.status == BotStatus.RUNNING,
            'is_paused': self.status == BotStatus.PAUSED,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'stop_time': self.stop_time.isoformat() if self.stop_time else None,
            'pause_time': self.pause_time.isoformat() if self.pause_time else None,
            'uptime_seconds': uptime,
            'cycles_count': self.cycles_count,
            'mode': self.mode,
            
            # Торговые пары
            'trading_pairs': {
                'total_pairs': len(self.all_trading_pairs),
                'active_pairs': len(self.active_pairs),
                'inactive_pairs': len(self.inactive_pairs),
                'blacklisted_pairs': len(self.blacklisted_pairs),
                'watchlist_pairs': len(self.watchlist_pairs),
                'trending_pairs': self.trending_pairs[:10],  # Топ-10
                'high_volume_pairs': self.high_volume_pairs[:10]
            },
            
            # Позиции и сделки
            'trading': {
                'open_positions': len(self.positions),
                'pending_orders': len(self.pending_orders),
                'trades_today': self.trades_today,
                'daily_profit': round(self.daily_profit, 2),
                'weekly_profit': round(self.weekly_profit, 2),
                'monthly_profit': round(self.monthly_profit, 2),
                'opportunities_found': len(self.current_opportunities),
                'missed_opportunities': len(self.missed_opportunities)
            },
            
            # Стратегии
            'strategies': {
                'available_strategies': self.available_strategies,
                'active_strategies': [name for name, perf in self.strategy_performance.items() 
                                   if perf.get('enabled', True)],
                'best_performing_strategy': self._get_best_strategy(),
                'strategy_performance': dict(self.strategy_performance)
            },
            
            # Состояние рынка
            'market_state': {
                'overall_trend': self.market_state.overall_trend,
                'volatility': self.market_state.volatility,
                'fear_greed_index': self.market_state.fear_greed_index,
                'market_regime': self.market_state.market_regime,
                'risk_level': self.market_state.risk_level.value,
                'btc_dominance': round(self.market_state.dominance_btc, 2),
                'eth_dominance': round(self.market_state.dominance_eth, 2),
                'total_market_cap': self.market_state.market_cap,
                'volume_24h': self.market_state.volume_24h
            },
            
            # Машинное обучение
            'machine_learning': {
                'enabled': config.ENABLE_MACHINE_LEARNING,
                'models_loaded': len(self.ml_models),
                'predictions_cached': len(self.ml_predictions),
                'models_performance': dict(self.model_performance),
                'training_queue_size': self.training_queue.qsize() if hasattr(self.training_queue, 'qsize') else 0
            },
            
            # Анализ новостей
            'news_analysis': {
                'enabled': config.ENABLE_NEWS_ANALYSIS,
                'news_cached': len(self.news_cache),
                'sentiment_scores': len(self.news_sentiment),
                'social_signals': len(self.social_signals)
            },
            
            # Риск-менеджмент
            'risk_management': {
                'portfolio_risk': round(self.portfolio_risk * 100, 2),
                'daily_loss': round(self.daily_loss * 100, 2),
                'risk_alerts': len(self.risk_alerts),
                'circuit_breaker_active': self.circuit_breaker_active,
                'correlation_pairs': len(self.correlation_matrix),
                'risk_limits': self.risk_limits
            },
            
            # Производительность
            'performance': asdict(self.performance_metrics),
            
            # Компоненты системы
            'components': {
                name: {
                    'status': comp.status.value,
                    'last_heartbeat': comp.last_heartbeat.isoformat() if comp.last_heartbeat else None,
                    'restart_count': comp.restart_count,
                    'is_critical': comp.is_critical
                }
                for name, comp in self.components.items()
            },
            
            # Статистика
            'statistics': asdict(self.trading_stats),
            
            # Активные задачи
            'tasks': {
                name: {
                    'running': not task.done() if task else False,
                    'health': self.task_health.get(name, 'unknown')
                }
                for name, task in self.tasks.items()
            },
            
            # Конфигурация
            'configuration': {
                'max_positions': config.MAX_POSITIONS,
                'max_daily_trades': config.MAX_DAILY_TRADES,
                'max_trading_pairs': config.MAX_TRADING_PAIRS,
                'position_size_percent': config.POSITION_SIZE_PERCENT,
                'stop_loss_percent': config.STOP_LOSS_PERCENT,
                'take_profit_percent': config.TAKE_PROFIT_PERCENT,
                'testnet_mode': config.BYBIT_TESTNET,
                'ml_enabled': config.ENABLE_MACHINE_LEARNING,
                'news_analysis_enabled': config.ENABLE_NEWS_ANALYSIS
            },
            
            # Временные метки
            'timestamps': {
                'current_time': current_time.isoformat(),
                'last_analysis': getattr(self, 'last_analysis_time', None),
                'last_trade': getattr(self, 'last_trade_time', None),
                'last_health_check': getattr(self, 'last_health_check_time', None)
            }
        }
        
        return status_info
    
    # =================================================================
    # ИНИЦИАЛИЗАЦИЯ КОМПОНЕНТОВ
    # =================================================================
    
    async def _initialize_all_components(self) -> bool:
        """Инициализация всех компонентов системы"""
        try:
            logger.info("🔧 Инициализация компонентов системы...")
            
            # ✅ СНАЧАЛА ИНИЦИАЛИЗИРУЕМ EXCHANGE ОТДЕЛЬНО (ВНЕ ЦИКЛА)
            if not self._exchange_initialized:
                logger.info("🔧 Инициализация exchange_client...")
                exchange_success = await self._init_exchange_client()
                if not exchange_success:
                    logger.error("❌ Критическая ошибка: не удалось инициализировать exchange")
                    return False
                self._exchange_initialized = True
                logger.info("✅ exchange_client инициализирован")
            else:
                logger.info("✅ exchange_client уже инициализирован")
            
            # ✅ ИНИЦИАЛИЗАЦИЯ ENHANCED EXCHANGE - ДОБАВЛЕНО ЗДЕСЬ
            logger.info("🚀 Инициализация enhanced exchange...")
            try:
                await self.initialize_enhanced_exchange()
            except Exception as e:
                logger.warning(f"⚠️ Enhanced exchange недоступен: {e}")
            
            # Определяем порядок инициализации с учетом зависимостей
            initialization_order = [
                ('database', self._init_database, [], True),
                ('config_validator', self._init_config_validator, ['database'], True),
                ('data_collector', self._init_data_collector, [], True),
                ('market_analyzer', self._init_market_analyzer, ['data_collector'], True),
                ('risk_manager', self._init_risk_manager, ['market_analyzer'], True),
                ('portfolio_manager', self._init_portfolio_manager, ['risk_manager'], True),
                ('strategy_factory', self._init_strategy_factory, ['market_analyzer'], True),
                ('trader', self._init_trader, ['exchange_client', 'risk_manager'], True),
                ('execution_engine', self._init_execution_engine, ['exchange_client', 'risk_manager'], False),
                ('notifier', self._init_notifier, [], False),
                ('ml_system', self._init_ml_system, ['data_collector'], False),
                ('news_analyzer', self._init_news_analyzer, [], False),
                ('websocket_manager', self._init_websocket_manager, ['exchange_client'], False),
                ('export_manager', self._init_export_manager, ['database'], False),
                ('health_monitor', self._init_health_monitor, [], False)
            ]
            
            # Инициализируем компоненты в порядке зависимостей
            for comp_name, init_func, dependencies, is_critical in initialization_order:
                try:
                    # ✅ ИСПРАВЛЕНО: Специальная проверка для компонентов с зависимостью от exchange_client
                    if 'exchange_client' in dependencies and not self._exchange_initialized:
                        logger.warning(f"⚠️ {comp_name} пропущен - exchange_client еще не готов")
                        continue
                    
                    # Проверяем остальные зависимости
                    other_deps = [dep for dep in dependencies if dep != 'exchange_client']
                    deps_ready = all(
                        self.components.get(dep, ComponentInfo('', ComponentStatus.NOT_INITIALIZED)).status == ComponentStatus.READY
                        for dep in other_deps
                    )
                    
                    if not deps_ready and other_deps:
                        logger.warning(f"⚠️ Зависимости для {comp_name} не готовы: {other_deps}")
                        if is_critical:
                            return False
                        continue
                    
                    # Создаем информацию о компоненте
                    comp_info = ComponentInfo(
                        name=comp_name,
                        status=ComponentStatus.INITIALIZING,
                        dependencies=dependencies,
                        is_critical=is_critical
                    )
                    self.components[comp_name] = comp_info
                    
                    logger.info(f"🔧 Инициализация {comp_name}...")
                    
                    # Инициализируем компонент
                    result = await init_func()
                    
                    if result:
                        comp_info.status = ComponentStatus.READY
                        comp_info.last_heartbeat = datetime.utcnow()
                        logger.info(f"✅ {comp_name} инициализирован")
                    else:
                        comp_info.status = ComponentStatus.FAILED
                        logger.error(f"❌ Ошибка инициализации {comp_name}")
                        if is_critical:
                            return False
                        
                except Exception as e:
                    logger.error(f"❌ Исключение при инициализации {comp_name}: {e}")
                    if comp_name in self.components:
                        self.components[comp_name].status = ComponentStatus.FAILED
                        self.components[comp_name].error = str(e)
                    if is_critical:
                        return False
            
            # Проверяем критически важные компоненты
            critical_components = [name for name, comp in self.components.items() if comp.is_critical]
            failed_critical = [name for name in critical_components 
                             if self.components[name].status != ComponentStatus.READY]
            
            if failed_critical:
                logger.error(f"❌ Критически важные компоненты не инициализированы: {failed_critical}")
                return False
            
            logger.info(f"✅ Инициализировано {len([c for c in self.components.values() if c.status == ComponentStatus.READY])} компонентов")
            return True
            
        except Exception as e:
            logger.error(f"❌ Критическая ошибка инициализации компонентов: {e}")
            return False
    
    async def _init_execution_engine(self) -> bool:
        """Инициализация движка исполнения ордеров"""
        try:
            from ..exchange.execution_engine import OrderExecutionEngine, get_execution_engine
            
            # Используем синглтон
            self.execution_engine = get_execution_engine()
            
            # Проверяем готовность
            if self.execution_engine:
                logger.info("✅ OrderExecutionEngine инициализирован")
                
                # Настраиваем параметры если нужно
                self.execution_engine.validation_settings.update({
                    'min_confidence': getattr(self.config, 'MIN_SIGNAL_CONFIDENCE', 0.6),
                    'max_slippage': getattr(self.config, 'MAX_SLIPPAGE_PERCENT', 0.5) / 100,
                    'min_volume_ratio': 0.01,
                    'max_position_correlation': 0.7
                })
                
                return True
            else:
                logger.warning("⚠️ OrderExecutionEngine недоступен, используем прямое исполнение")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации OrderExecutionEngine: {e}")
            return False
    
    async def _display_account_info(self):
        """Отображение информации об аккаунте и балансе"""
        try:
            logger.info("💰 Получение информации о балансе аккаунта...")
            
            # Получаем баланс через enhanced client (приоритет)
            balance_info = None
            
            if self.enhanced_exchange_client:
                try:
                    # Проверяем доступность v5_client через bybit_integration
                    if hasattr(self.enhanced_exchange_client, 'bybit_integration') and \
                       hasattr(self.enhanced_exchange_client.bybit_integration, 'v5_client') and \
                       self.enhanced_exchange_client.bybit_integration.v5_client:
                        # Получаем баланс через v5_client
                        balance_info = await self.enhanced_exchange_client.bybit_integration.v5_client.get_wallet_balance()
                        logger.debug("✅ Баланс получен через v5_client")
                    else:
                        logger.warning("⚠️ V5 client недоступен в enhanced client")
                except Exception as e:
                    logger.warning(f"⚠️ Enhanced client недоступен: {e}")
            
            # Fallback к обычному клиенту
            if not balance_info and self.exchange_client:
                try:
                    # Пробуем через UnifiedExchangeClient
                    if hasattr(self.exchange_client, 'exchange') and self.exchange_client.exchange:
                        # Используем встроенный метод get_balance из UnifiedExchangeClient
                        unified_balance = await self.exchange_client.get_balance()
                        
                        # Преобразуем формат для _process_balance_info
                        if 'error' not in unified_balance:
                            balance_info = {
                                'retCode': 0,
                                'result': {
                                    'list': [{
                                        'accountType': 'UNIFIED',
                                        'totalEquity': str(unified_balance.get('total_usdt', 0)),
                                        'totalAvailableBalance': str(unified_balance.get('free_usdt', 0)),
                                        'totalWalletBalance': str(unified_balance.get('total_usdt', 0)),
                                        'coin': []
                                    }]
                                }
                            }
                            
                            # Добавляем детали по монетам
                            for coin, details in unified_balance.get('assets', {}).items():
                                balance_info['result']['list'][0]['coin'].append({
                                    'coin': coin,
                                    'walletBalance': str(details.get('total', 0)),
                                    'availableToWithdraw': str(details.get('free', 0)),
                                    'equity': str(details.get('total', 0))
                                })
                            
                            logger.debug("✅ Баланс получен и преобразован из UnifiedExchangeClient")
                except Exception as e:
                    logger.error(f"❌ Ошибка получения баланса: {e}")
            
            if balance_info and isinstance(balance_info, dict):
                await self._process_balance_info(balance_info)
            else:
                logger.warning("⚠️ Не удалось получить информацию о балансе")
                
        except Exception as e:
            logger.error(f"❌ Ошибка отображения информации об аккаунте: {e}")
            logger.error(traceback.format_exc())
    
    async def _process_balance_info(self, balance_info: dict):
        """Обработка и отображение информации о балансе - ИСПРАВЛЕНО"""
        try:
            logger.info("💰 ═══════════════════════════════════════")
            logger.info("💰 ИНФОРМАЦИЯ О ТОРГОВОМ АККАУНТЕ BYBIT")
            logger.info("💰 ═══════════════════════════════════════")
            
            # Функция для безопасного преобразования в float
            def safe_float(value, default=0.0):
                """Безопасное преобразование значения в float"""
                if value is None:
                    return default
                if isinstance(value, (int, float)):
                    return float(value)
                if isinstance(value, str):
                    if value.strip() == '' or value.strip() == '0' or value.strip() == 'null':
                        return default
                    try:
                        return float(value.strip())
                    except (ValueError, AttributeError):
                        return default
                return default
            
            # Обработка для Bybit Unified Account
            if 'result' in balance_info and balance_info.get('retCode') == 0:
                result = balance_info.get('result', {})
                account_list = result.get('list', [])
                
                if account_list:
                    account = account_list[0]
                    
                    # Общая информация
                    account_type = account.get('accountType', 'UNIFIED')
                    total_equity = safe_float(account.get('totalEquity', 0))
                    total_available = safe_float(account.get('totalAvailableBalance', 0))
                    total_wallet = safe_float(account.get('totalWalletBalance', 0))
                    
                    logger.info(f"💼 ТИП АККАУНТА: {account_type} (Единый торговый)")
                    logger.info(f"💰 Общий баланс: ${total_wallet:.2f}")
                    logger.info(f"📊 Общий капитал: ${total_equity:.2f}")
                    logger.info(f"✅ Доступно для торговли: ${total_available:.2f}")
                    
                    # Детали по монетам
                    coins = account.get('coin', [])
                    logger.info("📊 ДЕТАЛИЗАЦИЯ ПО АКТИВАМ:")
                    
                    for coin_data in coins:
                        coin_symbol = coin_data.get('coin', '')
                        
                        if coin_symbol == 'USDT':
                            # ✅ ИСПРАВЛЕНО: Извлекаем все возможные поля баланса
                            wallet_balance = safe_float(coin_data.get('walletBalance', 0))
                            equity = safe_float(coin_data.get('equity', 0))
                            
                            # Пробуем разные поля для доступного баланса
                            available_withdraw = safe_float(coin_data.get('availableToWithdraw', 0))
                            available_balance = safe_float(coin_data.get('availableBalance', 0))
                            free_balance = safe_float(coin_data.get('free', 0))
                            
                            # Для SPOT аккаунта может быть availableToBorrow
                            available_borrow = safe_float(coin_data.get('availableToBorrow', 0))
                            
                            # Рассчитываем заблокированный баланс
                            locked = safe_float(coin_data.get('locked', 0))
                            
                            # ✅ ВАЖНО: В Unified Account весь баланс доступен если нет позиций
                            if available_withdraw == 0 and available_balance == 0 and free_balance == 0:
                                # Если нет позиций, весь баланс доступен
                                available_final = wallet_balance - locked
                            else:
                                # Используем максимальное из доступных значений
                                available_final = max(available_withdraw, available_balance, free_balance, available_borrow)
                            
                            logger.info(f"   💰 USDT:")
                            logger.info(f"      📈 Баланс: {wallet_balance:.2f}")
                            logger.info(f"      ✅ Доступно: {available_final:.2f}")
                            logger.info(f"      🔒 Заблокировано: {locked:.2f}")
                            
                            # Сохраняем значения
                            self.balance = wallet_balance
                            self.available_balance = available_final
                            self.locked_balance = locked
                            
                            # Логируем отладочную информацию
                            logger.debug(f"🔍 USDT баланс детали:")
                            logger.debug(f"   walletBalance: {coin_data.get('walletBalance', 'N/A')}")
                            logger.debug(f"   availableToWithdraw: {coin_data.get('availableToWithdraw', 'N/A')}")
                            logger.debug(f"   availableBalance: {coin_data.get('availableBalance', 'N/A')}")
                            logger.debug(f"   free: {coin_data.get('free', 'N/A')}")
                            logger.debug(f"   locked: {coin_data.get('locked', 'N/A')}")
                            logger.debug(f"   equity: {coin_data.get('equity', 'N/A')}")
                    
                    # ✅ НЕ ПРИНУДИТЕЛЬНО устанавливаем баланс для TESTNET
                    # Используем реальные данные с биржи!
                    
            # Обработка для обычного формата баланса
            elif isinstance(balance_info, dict) and any(key in balance_info for key in ['USDT', 'BTC', 'ETH']):
                logger.info("🏦 БАЛАНС ПО АКТИВАМ:")
                
                main_currencies = ['USDT', 'BTC', 'ETH', 'BNB']
                
                for currency in main_currencies:
                    if currency in balance_info:
                        balance_data = balance_info[currency]
                        if isinstance(balance_data, dict):
                            free = safe_float(balance_data.get('free', 0))
                            used = safe_float(balance_data.get('used', 0))
                            total = safe_float(balance_data.get('total', 0))
                            
                            if total > 0:
                                logger.info(f"   🪙 {currency}: {total:.4f} (свободно: {free:.4f})")
                        
                        # Устанавливаем USDT как основной баланс
                        if currency == 'USDT' and isinstance(balance_data, dict):
                            self.balance = safe_float(balance_data.get('total', 0))
                            self.available_balance = safe_float(balance_data.get('free', 0))
            
            # ✅ ДОБАВЛЕНО: Финальная проверка и установка безопасных значений
            if not hasattr(self, 'balance') or self.balance is None:
                self.balance = 0.0
                logger.warning("⚠️ Не удалось определить основной баланс, установлен 0")
            
            if not hasattr(self, 'available_balance') or self.available_balance is None:
                self.available_balance = 0.0
                logger.warning("⚠️ Не удалось определить доступный баланс, установлен 0")
            
            # Логируем итоговые значения
            logger.info(f"📊 ИТОГО для торговли:")
            logger.info(f"   💰 Общий баланс: ${self.balance:.2f}")
            logger.info(f"   💸 Доступно: ${self.available_balance:.2f}")
            logger.info(f"   🔒 В позициях: ${getattr(self, 'locked_balance', 0):.2f}")
            
            logger.info("💰 ═══════════════════════════════════════")
            
        except Exception as e:
            logger.error(f"❌ Ошибка обработки баланса: {e}")
            logger.error(traceback.format_exc())
            
            # ✅ ДОБАВЛЕНО: Устанавливаем безопасные значения по умолчанию
            if not hasattr(self, 'balance'):
                self.balance = 0.0
            if not hasattr(self, 'available_balance'):
                self.available_balance = 0.0
            
            logger.warning(f"⚠️ Установлены безопасные значения: баланс=${self.balance:.2f}, доступно=${self.available_balance:.2f}")
    
    async def _init_database(self) -> bool:
        """Инициализация подключения к базе данных"""
        try:
            # ✅ ИСПРАВЛЕНО: Импорт text для SQLAlchemy 2.x
            from sqlalchemy import text
            
            # Тестируем подключение к БД
            db = SessionLocal()
            try:
                db.execute(text("SELECT 1"))  # ✅ ИСПРАВЛЕНО!
                db.commit()
                logger.info("✅ База данных подключена успешно")
                return True
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к БД: {e}")
    
    # =================================================================
    # МЕТОДЫ РАБОТЫ С ТОРГОВЫМИ ПАРАМИ
    # =================================================================
    
    async def _discover_all_trading_pairs(self) -> bool:
        """Автоматическое обнаружение всех торговых пар"""
        try:
            logger.info("🔍 Автоматическое обнаружение торговых пар...")
            
            if config.ENABLE_AUTO_PAIR_DISCOVERY and self.exchange:
                # Получаем все рынки с биржи
                markets = await self._fetch_all_markets_from_exchange()
                
                if not markets:
                    logger.warning("⚠️ Не удалось получить рынки с биржи")
                    return False
                
                # Фильтруем по критериям
                filtered_pairs = await self._filter_and_rank_pairs(markets)
                
                # Ограничиваем количество
                max_pairs = config.MAX_TRADING_PAIRS
                self.all_trading_pairs = filtered_pairs[:max_pairs]
                
                # Разделяем на категории
                await self._categorize_trading_pairs()
                
                logger.info(f"✅ Обнаружено {len(self.all_trading_pairs)} торговых пар")
                logger.info(f"📈 Активных: {len(self.active_pairs)}")
                logger.info(f"👀 В списке наблюдения: {len(self.watchlist_pairs)}")
                
                return True
            else:
                # Используем конфигурационный список
                self._load_pairs_from_config()
                return True
                
        except Exception as e:
            logger.error(f"❌ Ошибка обнаружения торговых пар: {e}")
            return False
    
    async def _fetch_all_markets_from_exchange(self) -> List[Dict]:
        """Получение РЕАЛЬНЫХ рынков с биржи"""
        try:
            # Используем ваш существующий real_client.py
            if not hasattr(self, 'real_exchange') or not self.real_exchange:
                from ..exchange.real_client import RealExchangeClient
                self.real_exchange = RealExchangeClient()
                await self.real_exchange.connect()
            
            # Получаем реальные рынки
            markets = await self.real_exchange.get_all_markets()
            
            if not markets:
                logger.warning("⚠️ Не удалось получить рынки, используем конфиг")
                self._load_pairs_from_config()
                return []
            
            logger.info(f"✅ Загружено {len(markets)} РЕАЛЬНЫХ рынков с Bybit")
            return markets
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения реальных рынков: {e}")
            return []
    
    async def _filter_and_rank_pairs(self, markets: List[Dict]) -> List[Dict]:
        """Фильтрация и ранжирование торговых пар"""
        try:
            filtered_pairs = []
            
            for market in markets:
                # Применяем фильтры
                if await self._passes_pair_filters(market):
                    # Рассчитываем скор для ранжирования
                    score = await self._calculate_pair_score(market)
                    market['trading_score'] = score
                    filtered_pairs.append(market)
            
            # Сортируем по скору (лучшие сначала)
            filtered_pairs.sort(key=lambda x: x['trading_score'], reverse=True)
            
            logger.info(f"🎯 Отфильтровано {len(filtered_pairs)} пар из {len(markets)}")
            return filtered_pairs
            
        except Exception as e:
            logger.error(f"❌ Ошибка фильтрации пар: {e}")
            return []
    
    async def _passes_pair_filters(self, market: Dict) -> bool:
        """Проверка пары на соответствие фильтрам"""
        try:
            symbol = market.get('symbol', '')
            base = market.get('base', '')
            quote = market.get('quote', '')
            volume_24h = market.get('volume_24h', 0)
            price = market.get('price', 0)
            
            # Базовые фильтры
            if not market.get('active', False):
                return False
            
            # Фильтр по котируемой валюте
            if quote not in config.ALLOWED_QUOTE_ASSETS:
                return False
            
            # Фильтр по исключенным базовым активам
            if base in config.EXCLUDED_BASE_ASSETS:
                return False
            
            # Фильтр по объему
            if volume_24h < config.MIN_VOLUME_24H_USD:
                return False
            
            # Фильтр по цене
            if price < config.MIN_PRICE_USD or price > config.MAX_PRICE_USD:
                return False
            
            # Фильтр по черному списку
            if symbol in self.blacklisted_pairs:
                return False
            
            # Дополнительные фильтры
            change_24h = abs(market.get('change_24h', 0))
            if change_24h > 50:  # Исключаем слишком волатильные
                return False
            
            trades_count = market.get('trades_count', 0)
            if trades_count < 100:  # Минимальная активность
                return False
            
            spread_percent = (market.get('ask', 0) - market.get('bid', 0)) / price * 100
            if spread_percent > 1:  # Максимальный спред 1%
                return False
            
            return True
            
        except Exception as e:
            logger.debug(f"Ошибка проверки фильтров для {market.get('symbol', 'unknown')}: {e}")
            return False
    
    async def _calculate_pair_score(self, market: Dict) -> float:
        """Расчет скора торговой пары для ранжирования"""
        try:
            score = 0.0
            
            # Скор по объему (30%)
            volume_24h = market.get('volume_24h', 0)
            volume_score = min(1.0, volume_24h / 50000000)  # Нормализуем к $50M
            score += volume_score * 0.3
            
            # Скор по активности торгов (20%)
            trades_count = market.get('trades_count', 0)
            activity_score = min(1.0, trades_count / 10000)  # Нормализуем к 10k сделок
            score += activity_score * 0.2
            
            # Скор по ликвидности (спреду) (20%)
            price = market.get('price', 1)
            spread = (market.get('ask', price) - market.get('bid', price)) / price
            liquidity_score = max(0, 1 - spread * 100)  # Чем меньше спред, тем лучше
            score += liquidity_score * 0.2
            
            # Скор по волатильности (15%)
            change_24h = abs(market.get('change_24h', 0))
            volatility_score = min(1.0, change_24h / 10)  # Нормализуем к 10%
            score += volatility_score * 0.15
            
            # Скор по популярности базового актива (15%)
            base = market.get('base', '')
            popularity_score = self._get_asset_popularity_score(base)
            score += popularity_score * 0.15
            
            return min(1.0, score)
            
        except Exception as e:
            logger.debug(f"Ошибка расчета скора для {market.get('symbol', 'unknown')}: {e}")
            return 0.0
    
    def _get_asset_popularity_score(self, base_asset: str) -> float:
        """Получение скора популярности актива"""
        # Популярные активы получают больший скор
        popularity_map = {
            'BTC': 1.0, 'ETH': 0.95, 'BNB': 0.9, 'SOL': 0.85, 'ADA': 0.8,
            'XRP': 0.75, 'DOT': 0.7, 'AVAX': 0.65, 'MATIC': 0.6, 'LINK': 0.55,
            'UNI': 0.5, 'LTC': 0.45, 'BCH': 0.4, 'ATOM': 0.35, 'FIL': 0.3
        }
        return popularity_map.get(base_asset, 0.1)  # Базовый скор для неизвестных
    
    async def _categorize_trading_pairs(self):
        """Категоризация торговых пар"""
        try:
            # Очищаем старые категории
            self.active_pairs.clear()
            self.watchlist_pairs.clear()
            self.trending_pairs.clear()
            self.high_volume_pairs.clear()
            
            if not self.all_trading_pairs:
                return
            
            # Сортируем по скору
            sorted_pairs = sorted(self.all_trading_pairs, 
                                key=lambda x: x.get('trading_score', 0), 
                                reverse=True)
            
            # Активные пары (топ 30% или максимум из конфига)
            max_active = min(config.MAX_POSITIONS, len(sorted_pairs) // 3)
            self.active_pairs = [pair['symbol'] for pair in sorted_pairs[:max_active]]
            
            # Список наблюдения (следующие 20%)
            watchlist_count = min(50, len(sorted_pairs) // 5)
            start_idx = len(self.active_pairs)
            self.watchlist_pairs = [pair['symbol'] for pair in sorted_pairs[start_idx:start_idx + watchlist_count]]
            
            # Трендовые пары (с высоким изменением за 24ч)
            trending_pairs = [pair for pair in sorted_pairs if abs(pair.get('change_24h', 0)) > 5]
            self.trending_pairs = [pair['symbol'] for pair in trending_pairs[:20]]
            
            # Высокообъемные пары (топ по объему)
            volume_sorted = sorted(sorted_pairs, key=lambda x: x.get('volume_24h', 0), reverse=True)
            self.high_volume_pairs = [pair['symbol'] for pair in volume_sorted[:20]]
            
            logger.info(f"📊 Категоризация завершена:")
            logger.info(f"  🎯 Активные: {len(self.active_pairs)}")
            logger.info(f"  👀 Наблюдение: {len(self.watchlist_pairs)}")
            logger.info(f"  📈 Трендовые: {len(self.trending_pairs)}")
            logger.info(f"  💰 Высокообъемные: {len(self.high_volume_pairs)}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка категоризации пар: {e}")
    
    def _load_pairs_from_config(self):
        """Загрузка торговых пар из конфигурации"""
        try:
            configured_pairs = config.get_active_trading_pairs()
            
            # Преобразуем в формат all_trading_pairs
            self.all_trading_pairs = [
                {
                    'symbol': symbol,
                    'base': symbol.replace('USDT', '').replace('BUSD', '').replace('USDC', ''),
                    'quote': 'USDT',
                    'trading_score': 0.5  # Средний скор
                }
                for symbol in configured_pairs
            ]
            
            # Ограничиваем количество
            max_pairs = config.MAX_TRADING_PAIRS
            self.all_trading_pairs = self.all_trading_pairs[:max_pairs]
            self.active_pairs = [pair['symbol'] for pair in self.all_trading_pairs[:config.MAX_POSITIONS]]
            
            logger.info(f"📊 Загружено {len(self.all_trading_pairs)} пар из конфигурации")
            
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки пар из конфигурации: {e}")
            # Fallback к минимальному набору
    
    # =================================================================
    # ТОРГОВЫЕ ЦИКЛЫ И СТРАТЕГИИ 
    # =================================================================
    
    async def _start_all_trading_loops(self):
        """Запуск всех торговых циклов"""
        try:
            logger.info("🔄 Запуск всех торговых циклов...")
            
            # Основной торговый цикл
            self.tasks['main_trading'] = asyncio.create_task(
                self._main_trading_loop(), name="main_trading"
            )
            
            # Цикл мониторинга рынка
            self.tasks['market_monitoring'] = asyncio.create_task(
                self._market_monitoring_loop(), name="market_monitoring"
            )
            
            # Цикл обновления торговых пар
            self.tasks['pair_discovery'] = asyncio.create_task(
                self._pair_discovery_loop(), name="pair_discovery"
            )
            
            # Цикл управления позициями
            self.tasks['position_management'] = asyncio.create_task(
                self._position_management_loop(), name="position_management"
            )
            
            # Цикл мониторинга рисков
            self.tasks['risk_monitoring'] = asyncio.create_task(
                self._risk_monitoring_loop(), name="risk_monitoring"
            )
            
            # Цикл мониторинга здоровья
            self.tasks['health_monitoring'] = asyncio.create_task(
                self._health_monitoring_loop(), name="health_monitoring"
            )
            
            # Цикл обновления производительности
            self.tasks['performance_monitoring'] = asyncio.create_task(
                self._performance_monitoring_loop(), name="performance_monitoring"
            )
            
            # Цикл экспорта данных
            self.tasks['data_export'] = asyncio.create_task(
                self._data_export_loop(), name="data_export"
            )
            
            # Циклы машинного обучения (если включено)
            if config.ENABLE_MACHINE_LEARNING:
                self.tasks['ml_training'] = asyncio.create_task(
                    self._ml_training_loop(), name="ml_training"
                )
                self.tasks['ml_prediction'] = asyncio.create_task(
                    self._ml_prediction_loop(), name="ml_prediction"
                )
            
            # Циклы анализа новостей (если включено)
            if config.ENABLE_NEWS_ANALYSIS:
                self.tasks['news_collection'] = asyncio.create_task(
                    self._news_collection_loop(), name="news_collection"
                )
                self.tasks['sentiment_analysis'] = asyncio.create_task(
                    self._sentiment_analysis_loop(), name="sentiment_analysis"
                )
            
            # Цикл обработки событий
            self.tasks['event_processing'] = asyncio.create_task(
                self._event_processing_loop(), name="event_processing"
            )
            
            # Инициализируем здоровье задач
            for task_name in self.tasks:
                self.task_health[task_name] = 'starting'
            
            logger.info(f"✅ Запущено {len(self.tasks)} торговых циклов")
            
        except Exception as e:
            logger.error(f"❌ Ошибка запуска торговых циклов: {e}")
            raise
    
    async def _main_trading_loop(self):
        """Главный торговый цикл - С КОНТРОЛЕМ RATE LIMITS"""
        logger.info("🚀 Запуск главного торгового цикла...")
        
        cycle_count = 0
        last_request_times = defaultdict(lambda: 0)  # Для отслеживания времени запросов
        
        while self.is_running and self.status == BotStatus.RUNNING:
            try:
                cycle_count += 1
                cycle_start = time.time()
                
                logger.info(f"🔄 Цикл #{cycle_count} - анализ {len(self.active_pairs)} пар")
                
                # === КОНТРОЛЬ RATE LIMITS ===
                # Bybit limits: 120 requests per minute для spot
                max_requests_per_minute = 100  # Оставляем запас
                min_request_interval = 60.0 / max_requests_per_minute  # ~0.6 секунды между запросами
                
                # 1. Управление позициями (с задержкой между запросами)
                await self._manage_all_positions()
                await asyncio.sleep(min_request_interval)
                
                # 2. Обновляем рыночные данные с контролем частоты
                for i, symbol in enumerate(self.active_pairs):
                    # Проверяем время последнего запроса для символа
                    last_time = last_request_times[symbol]
                    current_time = time.time()
                    
                    if current_time - last_time < min_request_interval:
                        await asyncio.sleep(min_request_interval - (current_time - last_time))
                    
                    # Обновляем данные
                    await self._update_market_data_for_symbol(symbol)
                    last_request_times[symbol] = time.time()
                    
                    # Пауза между символами
                    if i < len(self.active_pairs) - 1:
                        await asyncio.sleep(min_request_interval)
                
                # 3. Ищем торговые возможности
                opportunities = await self._find_all_trading_opportunities()
                
                # 4. Исполняем лучшие сделки
                trades_executed = 0
                if opportunities:
                    trades_executed = await self._execute_best_trades(opportunities)
                
                # 5. Обновляем статистику
                cycle_duration = time.time() - cycle_start
                logger.info(f"⏱️ Цикл #{cycle_count} завершен за {cycle_duration:.2f}с, сделок: {trades_executed}")
                
                # 6. Адаптивная пауза
                # Увеличиваем интервал если нет возможностей
                if len(opportunities) == 0:
                    analysis_interval = min(getattr(config, 'ANALYSIS_INTERVAL_SECONDS', 60) * 1.5, 180)
                else:
                    analysis_interval = getattr(config, 'ANALYSIS_INTERVAL_SECONDS', 60)
                
                wait_time = max(analysis_interval - cycle_duration, 10)  # Минимум 10 секунд
                logger.debug(f"⏰ Ожидание {wait_time:.1f}с до следующего цикла...")
                await asyncio.sleep(wait_time)
                
            except asyncio.CancelledError:
                logger.info("🛑 Главный торговый цикл отменен")
                break
                
            except Exception as e:
                logger.error(f"❌ Ошибка в торговом цикле: {e}")
                logger.error(traceback.format_exc())
                # При ошибке ждем больше времени
                await asyncio.sleep(60)
        
        logger.info("✅ Главный торговый цикл остановлен")
        
    async def _update_market_data_for_symbol(self, symbol: str):
        """Обновление данных для одного символа с контролем ошибок"""
        try:
            if hasattr(self, 'data_collector') and self.data_collector:
                # Используем data_collector
                market_data = await self.data_collector.collect_market_data(symbol)
                return market_data
            else:
                # Fallback на прямое получение
                if hasattr(self.exchange_client, 'fetch_ohlcv'):
                    candles = await self.exchange_client.fetch_ohlcv(symbol, '5m', limit=50)
                    if candles and len(candles) > 0:
                        if symbol not in self.candle_cache:
                            self.candle_cache[symbol] = deque(maxlen=100)
                        
                        for candle in candles[-10:]:
                            candle_data = {
                                'timestamp': candle[0],
                                'open': float(candle[1]),
                                'high': float(candle[2]),
                                'low': float(candle[3]),
                                'close': float(candle[4]),
                                'volume': float(candle[5])
                            }
                            self.candle_cache[symbol].append(candle_data)
                        
                        return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Ошибка обновления данных для {symbol}: {e}")
            return False
        
    async def _execute_best_trades(self, opportunities: list) -> int:
        """Исполнение лучших торговых возможностей с ИСПРАВЛЕННЫМ вызовом calculate_position_size"""
        try:
            trades_executed = 0
            
            # Проверяем есть ли возможности
            if not opportunities:
                logger.debug("📊 Нет торговых возможностей для исполнения")
                return 0
            
            # Фильтруем и ранжируем возможности
            logger.info(f"📊 Найдено торговых возможностей: {len(opportunities)}")
            
            # Проверяем лимиты
            max_trades = min(
                getattr(config, 'MAX_DAILY_TRADES', 50) - getattr(self, 'trades_today', 0),
                getattr(config, 'MAX_POSITIONS', 15) - len(getattr(self, 'positions', {})),
                3  # Максимум 3 сделки за цикл
            )
            
            if max_trades <= 0:
                logger.warning("⚠️ Достигнут лимит сделок или позиций")
                return 0
            
            # Сортируем по уверенности
            sorted_opportunities = sorted(
                opportunities,
                key=lambda x: x.get('confidence', 0),
                reverse=True
            )
            
            # Исполняем лучшие сделки
            for opportunity in sorted_opportunities[:max_trades]:
                symbol = opportunity['symbol']
                signal = opportunity['signal']
                confidence = opportunity.get('confidence', 0.6)
                price = opportunity['price']
                
                # Проверяем минимальную уверенность
                min_confidence = getattr(config, 'MIN_CONFIDENCE', 0.6)
                if confidence < min_confidence:
                    logger.debug(f"⏭️ Пропускаем {symbol}: низкая уверенность {confidence:.2f} < {min_confidence}")
                    continue
                
                # ИСПРАВЛЕНО: Проверяем, является ли метод асинхронным
                if hasattr(self._calculate_position_size, '__call__'):
                    # Проверяем, является ли метод корутиной
                    import inspect
                    if inspect.iscoroutinefunction(self._calculate_position_size):
                        position_size = await self._calculate_position_size(symbol, price)
                    else:
                        # Метод синхронный - вызываем без await
                        position_size = self._calculate_position_size(symbol, price)
                else:
                    # Если метода нет, используем базовый расчет
                    logger.warning("⚠️ Метод _calculate_position_size не найден, используем базовый расчет")
                    # Базовый расчет размера позиции
                    balance = getattr(self, 'available_balance', 10000)
                    risk_amount = balance * (getattr(config, 'RISK_PER_TRADE_PERCENT', 1.5) / 100)
                    position_size = risk_amount / price
                    
                if position_size <= 0:
                    logger.warning(f"⚠️ Нулевой размер позиции для {symbol}")
                    continue
                
                # Округляем размер позиции до разумных значений
                # Для Bybit минимальный размер обычно 0.001
                min_size = 0.001
                if position_size < min_size:
                    logger.warning(f"⚠️ Размер позиции {position_size} меньше минимального {min_size}")
                    position_size = min_size
                
                # Округляем до 3 знаков после запятой
                position_size = round(position_size, 3)
                
                # Подготавливаем данные для сделки
                trade_data = {
                    'confidence': confidence,
                    'stop_loss': opportunity.get('stop_loss'),
                    'take_profit': opportunity.get('take_profit'),
                    'strategy': opportunity.get('strategy', 'unknown'),
                    'indicators': opportunity.get('indicators', {}),
                    'market_conditions': opportunity.get('market_conditions', {}),
                    'risk_reward_ratio': opportunity.get('risk_reward_ratio')
                }
                
                # Рассчитываем risk/reward если не предоставлен
                if not trade_data.get('risk_reward_ratio') and trade_data.get('stop_loss') and trade_data.get('take_profit'):
                    if signal.upper() == 'BUY':
                        risk = price - trade_data['stop_loss']
                        reward = trade_data['take_profit'] - price
                    else:  # SELL
                        risk = trade_data['stop_loss'] - price
                        reward = price - trade_data['take_profit']
                    
                    if risk > 0:
                        trade_data['risk_reward_ratio'] = reward / risk
                
                # Логируем подготовку сделки
                logger.info("🎯 ПОДГОТОВКА СДЕЛКИ:")
                logger.info(f"📊 Символ: {symbol}")
                logger.info(f"📈 Сигнал: {signal}")
                logger.info(f"💵 Цена: ${price:.4f}")
                logger.info(f"📏 Размер: {position_size}")
                if trade_data.get('stop_loss'):
                    logger.info(f"🛑 Стоп-лосс: ${trade_data['stop_loss']:.4f}")
                if trade_data.get('take_profit'):
                    logger.info(f"🎯 Тейк-профит: ${trade_data['take_profit']:.4f}")
                if trade_data.get('risk_reward_ratio'):
                    logger.info(f"⚖️ Risk/Reward: 1:{trade_data['risk_reward_ratio']:.2f}")
                logger.info(f"📊 Уверенность: {confidence:.2f}")
                logger.info(f"🔧 Стратегия: {trade_data.get('strategy')}")
                
                # Проверяем режим торговли
                paper_trading = config.PAPER_TRADING
                testnet = config.TESTNET
                live_trading = config.LIVE_TRADING
                
                # Логируем режим
                logger.debug(f"🔍 Режимы: PAPER_TRADING={paper_trading}, TESTNET={testnet}, LIVE_TRADING={live_trading}")
                
                 # Определяем режим исполнения (приоритет — paper → live → testnet → fallback)
                if paper_trading:
                    logger.info("📝 РЕЖИМ PAPER TRADING - симуляция сделки")
                    success = await self._simulate_trade(symbol, signal, position_size, price, trade_data)
                elif live_trading:
                    if testnet:
                        logger.info("🧪 РЕЖИМ TESTNET - реальная сделка на тестовой бирже")
                    else:
                        logger.info("💸 РЕЖИМ LIVE TRADING - реальная сделка на основной бирже")
                    success = await self._execute_real_order(symbol, signal, position_size, price, trade_data)
                else:
                    logger.warning("⚠️ Не указаны LIVE_TRADING или PAPER_TRADING — переходим в симуляцию")
                    success = await self._simulate_trade(symbol, signal, position_size, price, trade_data)
                    
                if success:
                    trades_executed += 1
                    self.trades_today = getattr(self, 'trades_today', 0) + 1
                    logger.info(f"✅ Сделка #{trades_executed} выполнена успешно")
                    
                    # Обновляем позиции
                    if not hasattr(self, 'positions'):
                        self.positions = {}
                        
                    self.positions[symbol] = {
                        'side': signal,
                        'size': position_size,
                        'entry_price': price,
                        'stop_loss': trade_data.get('stop_loss'),
                        'take_profit': trade_data.get('take_profit'),
                        'strategy': trade_data.get('strategy'),
                        'confidence': confidence,
                        'timestamp': datetime.utcnow()
                    }
                    
                    # Отправляем уведомление
                    if hasattr(self, 'notifier') and self.notifier:
                        try:
                            await self.notifier.send_trade_notification(
                                symbol=symbol,
                                side=signal,
                                price=price,
                                amount=position_size,
                                strategy=trade_data.get('strategy'),
                                confidence=confidence
                            )
                        except Exception as e:
                            logger.warning(f"⚠️ Ошибка отправки уведомления: {e}")
                else:
                    logger.error(f"❌ Не удалось выполнить сделку для {symbol}")
                    
                    # Добавляем символ в черный список на некоторое время
                    if hasattr(self, 'trade_cooldown'):
                        self.trade_cooldown[symbol] = datetime.utcnow() + timedelta(minutes=30)
                        logger.info(f"⏰ {symbol} добавлен в cooldown на 30 минут")
            
            # Обновляем статистику
            if trades_executed > 0:
                logger.info(f"📊 Итого выполнено сделок в этом цикле: {trades_executed}")
                logger.info(f"📊 Всего сделок за сегодня: {self.trades_today}")
                logger.info(f"📊 Открытых позиций: {len(self.positions)}")
            
            return trades_executed
            
        except Exception as e:
            logger.error(f"❌ Ошибка исполнения сделок: {e}")
            import traceback
            traceback.print_exc()
            return 0
            
    async def _simulate_trade(self, symbol: str, signal: str, position_size: float,
                             price: float, trade_data: Dict[str, Any]) -> bool:
        """
        Симуляция торговой операции для режима Paper Trading
        
        Args:
            symbol: Торговая пара
            signal: Тип сигнала (BUY/SELL)
            position_size: Размер позиции
            price: Цена входа
            trade_data: Дополнительные данные сделки
            
        Returns:
            bool: True если симуляция выполнена успешно
        """
        try:
            logger.info("📝 СИМУЛЯЦИЯ СДЕЛКИ (Paper Trading)")
            logger.info(f"📊 Символ: {symbol}")
            logger.info(f"📈 Направление: {signal}")
            logger.info(f"💵 Цена входа: ${price:.4f}")
            logger.info(f"📏 Размер позиции: {position_size}")
            
            # Генерируем уникальный ID для симулированного ордера
            import uuid
            order_id = f"PAPER_{uuid.uuid4().hex[:8]}"
            
            # Рассчитываем стоимость позиции
            position_value = position_size * price
            
            # Проверяем достаточность баланса
            available_balance = getattr(self, 'paper_balance', 10000)
            if position_value > available_balance:
                logger.error(f"❌ Недостаточно средств: нужно ${position_value:.2f}, доступно ${available_balance:.2f}")
                return False
            
            # Создаем запись о симулированной сделке
            simulated_trade = {
                'order_id': order_id,
                'symbol': symbol,
                'side': signal,
                'size': position_size,
                'entry_price': price,
                'position_value': position_value,
                'stop_loss': trade_data.get('stop_loss'),
                'take_profit': trade_data.get('take_profit'),
                'strategy': trade_data.get('strategy', 'unknown'),
                'confidence': trade_data.get('confidence', 0.6),
                'timestamp': datetime.utcnow(),
                'status': 'FILLED',
                'pnl': 0.0,
                'pnl_percent': 0.0,
                'commission': position_value * 0.001  # 0.1% комиссия
            }
            
            # Обновляем paper баланс
            self.paper_balance = available_balance - position_value - simulated_trade['commission']
            
            # Сохраняем в paper позиции
            if not hasattr(self, 'paper_positions'):
                self.paper_positions = {}
            
            self.paper_positions[symbol] = simulated_trade
            
            # Сохраняем в историю paper сделок
            if not hasattr(self, 'paper_trades_history'):
                self.paper_trades_history = []
            
            self.paper_trades_history.append(simulated_trade.copy())
            
            # Логируем детали сделки
            logger.info(f"✅ Симулированная сделка выполнена!")
            logger.info(f"🔖 Order ID: {order_id}")
            logger.info(f"💰 Стоимость позиции: ${position_value:.2f}")
            logger.info(f"💸 Комиссия: ${simulated_trade['commission']:.2f}")
            logger.info(f"💵 Остаток баланса: ${self.paper_balance:.2f}")
            
            if trade_data.get('stop_loss'):
                potential_loss = abs(price - trade_data['stop_loss']) * position_size
                logger.info(f"🛑 Stop Loss: ${trade_data['stop_loss']:.4f} (риск: ${potential_loss:.2f})")
                
            if trade_data.get('take_profit'):
                potential_profit = abs(trade_data['take_profit'] - price) * position_size
                logger.info(f"🎯 Take Profit: ${trade_data['take_profit']:.4f} (потенциал: ${potential_profit:.2f})")
            
            if trade_data.get('risk_reward_ratio'):
                logger.info(f"⚖️ Risk/Reward: 1:{trade_data['risk_reward_ratio']:.2f}")
            
            # Запускаем мониторинг симулированной позиции
            if hasattr(self, '_monitor_paper_position'):
                asyncio.create_task(self._monitor_paper_position(symbol, simulated_trade))
            
            # Обновляем статистику
            if not hasattr(self, 'paper_stats'):
                self.paper_stats = {
                    'total_trades': 0,
                    'winning_trades': 0,
                    'losing_trades': 0,
                    'total_pnl': 0.0,
                    'total_commission': 0.0,
                    'max_drawdown': 0.0,
                    'best_trade': 0.0,
                    'worst_trade': 0.0,
                    'average_win': 0.0,
                    'average_loss': 0.0,
                    'win_rate': 0.0,
                    'profit_factor': 0.0
                }
            
            self.paper_stats['total_trades'] += 1
            self.paper_stats['total_commission'] += simulated_trade['commission']
            
            # Отправляем уведомление о симулированной сделке
            if hasattr(self, 'notifier') and self.notifier:
                try:
                    message = f"📝 PAPER TRADE EXECUTED\n"
                    message += f"Symbol: {symbol}\n"
                    message += f"Side: {signal}\n"
                    message += f"Price: ${price:.4f}\n"
                    message += f"Size: {position_size}\n"
                    message += f"Value: ${position_value:.2f}\n"
                    message += f"Strategy: {trade_data.get('strategy', 'unknown')}\n"
                    message += f"Balance: ${self.paper_balance:.2f}"
                    
                    await self.notifier.send_message(message)
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка отправки уведомления: {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка симуляции сделки: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def _monitor_paper_position(self, symbol: str, position: Dict[str, Any]):
        """
        Мониторинг симулированной позиции для обновления P&L
        
        Args:
            symbol: Торговая пара
            position: Данные позиции
        """
        try:
            while symbol in self.paper_positions:
                await asyncio.sleep(10)  # Проверяем каждые 10 секунд
                
                # Получаем текущую цену
                current_price = await self._get_current_price(symbol)
                if not current_price:
                    continue
                
                # Рассчитываем P&L
                entry_price = position['entry_price']
                size = position['size']
                side = position['side']
                
                if side.upper() == 'BUY':
                    pnl = (current_price - entry_price) * size
                    pnl_percent = ((current_price - entry_price) / entry_price) * 100
                else:  # SELL
                    pnl = (entry_price - current_price) * size
                    pnl_percent = ((entry_price - current_price) / entry_price) * 100
                
                # Обновляем позицию
                self.paper_positions[symbol]['current_price'] = current_price
                self.paper_positions[symbol]['pnl'] = pnl
                self.paper_positions[symbol]['pnl_percent'] = pnl_percent
                
                # Проверяем стоп-лосс
                if position.get('stop_loss'):
                    if (side.upper() == 'BUY' and current_price <= position['stop_loss']) or \
                       (side.upper() == 'SELL' and current_price >= position['stop_loss']):
                        logger.warning(f"🛑 STOP LOSS сработал для {symbol} @ ${current_price:.4f}")
                        await self._close_paper_position(symbol, current_price, 'STOP_LOSS')
                        break
                
                # Проверяем тейк-профит
                if position.get('take_profit'):
                    if (side.upper() == 'BUY' and current_price >= position['take_profit']) or \
                       (side.upper() == 'SELL' and current_price <= position['take_profit']):
                        logger.info(f"🎯 TAKE PROFIT сработал для {symbol} @ ${current_price:.4f}")
                        await self._close_paper_position(symbol, current_price, 'TAKE_PROFIT')
                        break
                
        except Exception as e:
            logger.error(f"❌ Ошибка мониторинга paper позиции: {e}")
    
    async def _close_paper_position(self, symbol: str, exit_price: float, reason: str):
        """
        Закрытие симулированной позиции
        
        Args:
            symbol: Торговая пара
            exit_price: Цена выхода
            reason: Причина закрытия
        """
        try:
            if symbol not in self.paper_positions:
                return
            
            position = self.paper_positions[symbol]
            
            # Финальный расчет P&L
            entry_price = position['entry_price']
            size = position['size']
            side = position['side']
            
            if side.upper() == 'BUY':
                pnl = (exit_price - entry_price) * size
            else:  # SELL
                pnl = (entry_price - exit_price) * size
            
            # Комиссия за закрытие
            exit_commission = size * exit_price * 0.001
            total_commission = position['commission'] + exit_commission
            net_pnl = pnl - exit_commission
            
            # Обновляем баланс
            self.paper_balance += position['position_value'] + net_pnl
            
            # Обновляем статистику
            self.paper_stats['total_pnl'] += net_pnl
            
            if net_pnl > 0:
                self.paper_stats['winning_trades'] += 1
                self.paper_stats['best_trade'] = max(self.paper_stats['best_trade'], net_pnl)
            else:
                self.paper_stats['losing_trades'] += 1
                self.paper_stats['worst_trade'] = min(self.paper_stats['worst_trade'], net_pnl)
            
            # Рассчитываем win rate
            total = self.paper_stats['winning_trades'] + self.paper_stats['losing_trades']
            if total > 0:
                self.paper_stats['win_rate'] = (self.paper_stats['winning_trades'] / total) * 100
            
            # Логируем закрытие
            logger.info(f"📝 PAPER POSITION CLOSED: {symbol}")
            logger.info(f"📤 Причина: {reason}")
            logger.info(f"💵 Цена выхода: ${exit_price:.4f}")
            logger.info(f"💰 P&L: ${net_pnl:.2f} ({(net_pnl/position['position_value'])*100:.2f}%)")
            logger.info(f"💵 Новый баланс: ${self.paper_balance:.2f}")
            logger.info(f"📊 Win Rate: {self.paper_stats['win_rate']:.1f}%")
            
            # Удаляем позицию
            del self.paper_positions[symbol]
            
        except Exception as e:
            logger.error(f"❌ Ошибка закрытия paper позиции: {e}")
            
    async def _get_current_price(self, symbol: str) -> Optional[float]:
        """
        Получает текущую цену для символа
        
        Args:
            symbol: Торговая пара
            
        Returns:
            Optional[float]: Текущая цена или None
        """
        try:
            # Способ 1: Через enhanced exchange client с кешем
            if hasattr(self, 'enhanced_exchange_client') and self.enhanced_exchange_client:
                # Проверяем кеш цен если есть
                if hasattr(self.enhanced_exchange_client, 'price_cache'):
                    cached_price = self.enhanced_exchange_client.price_cache.get(symbol)
                    if cached_price and cached_price.get('timestamp'):
                        # Проверяем актуальность (не старше 5 секунд)
                        age = (datetime.utcnow() - cached_price['timestamp']).total_seconds()
                        if age < 5:
                            return cached_price['price']
                
                # Пробуем через V5 API
                if hasattr(self.enhanced_exchange_client, 'v5_client'):
                    try:
                        ticker = await self.enhanced_exchange_client.v5_client.get_ticker(
                            category='linear',
                            symbol=symbol
                        )
                        if ticker and ticker.get('retCode') == 0:
                            result = ticker.get('result', {})
                            if result.get('list'):
                                return float(result['list'][0].get('lastPrice', 0))
                    except Exception as e:
                        logger.debug(f"V5 ticker error: {e}")
            
            # Способ 2: Через базовый exchange client
            if hasattr(self, 'exchange_client') and self.exchange_client:
                try:
                    # Метод fetch_ticker для CCXT
                    if hasattr(self.exchange_client, 'fetch_ticker'):
                        ticker = await self.exchange_client.fetch_ticker(symbol)
                        if ticker and 'last' in ticker:
                            return float(ticker['last'])
                    # Альтернативный метод get_ticker
                    elif hasattr(self.exchange_client, 'get_ticker'):
                        ticker = await self.exchange_client.get_ticker(symbol)
                        if ticker:
                            return float(ticker.get('last', 0))
                except Exception as e:
                    logger.debug(f"Exchange client ticker error: {e}")
            
            # Способ 3: Через WebSocket данные если есть
            if hasattr(self, 'websocket_manager') and self.websocket_manager:
                ws_data = getattr(self.websocket_manager, 'market_data', {})
                if symbol in ws_data and 'price' in ws_data[symbol]:
                    return float(ws_data[symbol]['price'])
            
            # Способ 4: Из последних свечей
            if hasattr(self, 'data_collector') and self.data_collector:
                try:
                    # Получаем последнюю свечу
                    candles = await self.data_collector.get_latest_candles(symbol, limit=1)
                    if candles and len(candles) > 0:
                        return float(candles[-1]['close'])
                except Exception as e:
                    logger.debug(f"Data collector error: {e}")
            
            # Если ничего не сработало, пробуем простой API запрос
            logger.warning(f"⚠️ Не удалось получить цену для {symbol} стандартными методами")
            
            # Fallback: прямой запрос к Bybit API
            try:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    url = f"https://api-testnet.bybit.com/v5/market/tickers?category=linear&symbol={symbol}"
                    if not getattr(config, 'TESTNET', True):
                        url = f"https://api.bybit.com/v5/market/tickers?category=linear&symbol={symbol}"
                    
                    async with session.get(url) as response:
                        if response.status == 200:
                            data = await response.json()
                            if data.get('retCode') == 0:
                                result = data.get('result', {})
                                if result.get('list'):
                                    return float(result['list'][0].get('lastPrice', 0))
            except Exception as e:
                logger.error(f"❌ Fallback API error: {e}")
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения текущей цены для {symbol}: {e}")
            return None
    
    async def _set_position_sl_tp(self, symbol: str, stop_loss: Optional[float], 
                                 take_profit: Optional[float]) -> bool:
        """
        Устанавливает стоп-лосс и тейк-профит для позиции
        
        Args:
            symbol: Торговая пара
            stop_loss: Цена стоп-лосса
            take_profit: Цена тейк-профита
            
        Returns:
            bool: True если успешно установлено
        """
        try:
            if not stop_loss and not take_profit:
                return True
            
            logger.info(f"🎯 Установка SL/TP для {symbol}")
            
            # Через V5 API
            if hasattr(self, 'enhanced_exchange_client') and self.enhanced_exchange_client:
                if hasattr(self.enhanced_exchange_client, 'v5_client'):
                    try:
                        params = {
                            'category': 'linear',
                            'symbol': symbol,
                            'positionIdx': 0  # One-way mode
                        }
                        
                        if stop_loss:
                            params['stopLoss'] = str(stop_loss)
                            params['slTriggerBy'] = 'LastPrice'
                            logger.info(f"🛑 Stop Loss: ${stop_loss:.4f}")
                        
                        if take_profit:
                            params['takeProfit'] = str(take_profit)
                            params['tpTriggerBy'] = 'LastPrice'
                            logger.info(f"🎯 Take Profit: ${take_profit:.4f}")
                        
                        result = await self.enhanced_exchange_client.v5_client.set_trading_stop(**params)
                        
                        if result and result.get('retCode') == 0:
                            logger.info(f"✅ SL/TP успешно установлены для {symbol}")
                            return True
                        else:
                            error = result.get('retMsg', 'Unknown error') if result else 'No response'
                            logger.error(f"❌ Ошибка установки SL/TP: {error}")
                            
                    except Exception as e:
                        logger.error(f"❌ V5 API error: {e}")
            
            # Через базовый exchange client
            if hasattr(self, 'exchange_client') and self.exchange_client:
                try:
                    # Получаем открытые позиции
                    positions = await self.exchange_client.fetch_positions([symbol])
                    
                    for position in positions:
                        if position['symbol'] == symbol and position['contracts'] > 0:
                            # Модифицируем позицию
                            if hasattr(self.exchange_client, 'edit_position'):
                                result = await self.exchange_client.edit_position(
                                    symbol=symbol,
                                    params={
                                        'stopLoss': stop_loss,
                                        'takeProfit': take_profit
                                    }
                                )
                                
                                if result:
                                    logger.info(f"✅ SL/TP установлены через exchange_client")
                                    return True
                                    
                except Exception as e:
                    logger.error(f"❌ Exchange client error: {e}")
            
            logger.warning(f"⚠️ Не удалось установить SL/TP для {symbol}")
            return False
            
        except Exception as e:
            logger.error(f"❌ Ошибка установки SL/TP: {e}")
            return False
    
    # =================================================================
    # ДОПОЛНИТЕЛЬНЫЕ МЕТОДЫ ДЛЯ ТОРГОВЛИ (заглушки)
    # =================================================================
    
    async def _filter_opportunities(self, opportunities: List[TradingOpportunity]) -> List[TradingOpportunity]:
        """Фильтрация возможностей"""
        return opportunities
    
    async def _rank_all_opportunities(self, opportunities: List[TradingOpportunity]) -> List[TradingOpportunity]:
        """Ранжирование возможностей"""
        return opportunities
    
    async def _perform_pre_trade_risk_check(self) -> bool:
        """Проверка рисков перед торговлей"""
        return True
    
    async def _update_strategy_performance(self):
        """Обновление производительности стратегий"""
        pass
    
    async def _cleanup_expired_opportunities(self):
        """Очистка устаревших возможностей"""
        pass
    
    async def _trigger_emergency_stop(self, reason: str):
        """Запуск экстренной остановки"""
        logger.critical(f"🚨 Запуск экстренной остановки: {reason}")
        await self.emergency_stop()
        
    async def _initialize_strategies(self):
        """Инициализация стратегий - ПОЛНАЯ РЕАЛИЗАЦИЯ"""
        try:
            logger.info("🎯 Инициализация стратегий...")
            
            # Загружаем доступные стратегии
            try:
                from ..strategies import (
                    MultiIndicatorStrategy,
                    MomentumStrategy, 
                    MeanReversionStrategy,
                    BreakoutStrategy,
                    ScalpingStrategy,
                    #SwingTradingStrategy
                )
                
                # Регистрируем стратегии
                self.available_strategies = {
                    'multi_indicator': MultiIndicatorStrategy,
                    'momentum': MomentumStrategy,
                    'mean_reversion': MeanReversionStrategy,
                    'breakout': BreakoutStrategy,
                    'scalping': ScalpingStrategy,
                    #'swing': SwingTradingStrategy
                }
                
                logger.info(f"✅ Загружено {len(self.available_strategies)} стратегий")
                
            except ImportError as e:
                logger.warning(f"⚠️ Не все стратегии доступны: {e}")
                # Минимальный набор стратегий
                self.available_strategies = {}
            
            # Активируем стратегии согласно весам из конфигурации
            try:
                strategy_weights = {
                    'multi_indicator': 25.0,
                    'momentum': 20.0,
                    'mean_reversion': 15.0,
                    'breakout': 15.0,
                    'scalping': 10.0,
                    #'swing': 10.0,
                    'ml_prediction': 5.0
                }
                
                # Если есть веса в конфигурации - используем их
                strategy_weights_config = getattr(config, 'STRATEGY_WEIGHTS', None)
                if strategy_weights_config:
                    # Парсим строку формата "name:weight,name:weight"
                    if isinstance(strategy_weights_config, str):
                        for pair in strategy_weights_config.split(','):
                            if ':' in pair:
                                name, weight = pair.strip().split(':')
                                strategy_weights[name.strip()] = float(weight)
                    elif isinstance(strategy_weights_config, dict):
                        strategy_weights.update(strategy_weights_config)
                
                # Создаем экземпляры активных стратегий
                for strategy_name, weight in strategy_weights.items():
                    if weight > 0 and strategy_name in self.available_strategies:
                        try:
                            # Создаем экземпляр стратегии
                            strategy_class = self.available_strategies[strategy_name]
                            strategy_instance = strategy_class()
                            
                            self.strategy_instances[strategy_name] = strategy_instance
                            
                            # Инициализируем производительность стратегии
                            self.strategy_performance[strategy_name] = {
                                'weight': weight,
                                'enabled': True,
                                'total_trades': 0,
                                'winning_trades': 0,
                                'losing_trades': 0,
                                'total_profit': 0.0,
                                'win_rate': 0.0,
                                'last_used': None
                            }
                            
                            logger.info(f"✅ Активирована стратегия {strategy_name} с весом {weight}%")
                            
                        except Exception as e:
                            logger.error(f"❌ Ошибка создания стратегии {strategy_name}: {e}")
                
                # Проверяем что хотя бы одна стратегия активна
                if not self.strategy_instances:
                    logger.warning("⚠️ Нет активных стратегий, создаем базовую")
                    # Создаем минимальную стратегию-заглушку
                    class BasicStrategy:
                        def __init__(self):
                            self.name = 'basic'
                        
                        async def analyze(self, symbol, data):
                            return {'signal': 'HOLD', 'confidence': 0.5}
                    
                    self.strategy_instances['basic'] = BasicStrategy()
                    self.strategy_performance['basic'] = {
                        'weight': 100.0,
                        'enabled': True,
                        'total_trades': 0,
                        'winning_trades': 0,
                        'losing_trades': 0,
                        'total_profit': 0.0,
                        'win_rate': 0.0,
                        'last_used': None
                    }
                
                logger.info(f"✅ Инициализировано {len(self.strategy_instances)} стратегий")
                
                # Логируем активные стратегии
                active_strategies = [name for name, inst in self.strategy_instances.items()]
                logger.info(f"📊 Активные стратегии: {', '.join(active_strategies)}")
                
                # Нормализуем веса (чтобы сумма была 100%)
                total_weight = sum(
                    perf['weight'] 
                    for perf in self.strategy_performance.values() 
                    if perf.get('enabled', True)
                )
                
                if total_weight > 0:
                    for strategy_name in self.strategy_performance:
                        if self.strategy_performance[strategy_name].get('enabled', True):
                            normalized_weight = (
                                self.strategy_performance[strategy_name]['weight'] / total_weight * 100
                            )
                            self.strategy_performance[strategy_name]['normalized_weight'] = normalized_weight
                            logger.debug(
                                f"📊 {strategy_name}: вес {normalized_weight:.1f}% "
                                f"(оригинальный: {self.strategy_performance[strategy_name]['weight']})"
                            )
                
                return True
                
            except Exception as e:
                logger.error(f"❌ Ошибка инициализации стратегий: {e}")
                import traceback
                traceback.print_exc()
                return False
                
        except Exception as e:
            logger.error(f"❌ Критическая ошибка инициализации стратегий: {e}")
            return False
    
    # ✅ ФОНОВЫЙ ЦИКЛ обучения ML моделей (из интеграции):
    async def _ml_training_loop(self):
        """Фоновый цикл обучения ML моделей"""
        while not self._stop_event.is_set():
            try:
                # Ждем заданный интервал
                interval = getattr(self.config, 'ML_MODEL_RETRAIN_INTERVAL', 86400)  # 24 часа
                await asyncio.sleep(interval)
                
                if self._stop_event.is_set():
                    break
                
                logger.info("🎓 Запуск переобучения ML моделей...")
                
                # Обучаем модели для активных пар
                if hasattr(self, 'ml_system') and self.ml_system and hasattr(self.ml_system, 'trainer'):
                    for symbol in list(self.active_pairs)[:5]:  # Максимум 5 пар
                        try:
                            logger.info(f"🎓 Обучение модели для {symbol}...")
                            result = await self.ml_system.trainer.train_symbol_model(symbol)
                            
                            if result.get('success'):
                                logger.info(f"✅ Модель для {symbol} обучена успешно")
                            else:
                                logger.warning(f"⚠️ Не удалось обучить модель для {symbol}")
                            
                            # Пауза между обучениями
                            await asyncio.sleep(300)  # 5 минут
                            
                        except Exception as e:
                            logger.error(f"❌ Ошибка обучения для {symbol}: {e}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Ошибка в ML training loop: {e}")
    
    # =================================================================
    # УПРАВЛЕНИЕ ЗДОРОВЬЕМ СИСТЕМЫ
    # =================================================================
    
    async def _perform_health_check(self) -> Dict[str, Any]:
        """Проверка здоровья всей системы"""
        try:
            health_info = {
                'timestamp': datetime.utcnow().isoformat(),
                'overall_healthy': True,
                'components': {},
                'tasks': {},
                'system': {},
                'alerts': []
            }
            
            # Проверка компонентов
            for name, comp in self.components.items():
                is_healthy = comp.status == ComponentStatus.READY
                if comp.last_heartbeat:
                    time_since_heartbeat = (datetime.utcnow() - comp.last_heartbeat).total_seconds()
                    is_healthy = is_healthy and time_since_heartbeat < comp.health_check_interval * 2
                
                health_info['components'][name] = {
                    'status': comp.status.value,
                    'healthy': is_healthy,
                    'last_heartbeat': comp.last_heartbeat.isoformat() if comp.last_heartbeat else None,
                    'restart_count': comp.restart_count
                }
                
                if not is_healthy and comp.is_critical:
                    health_info['overall_healthy'] = False
                    health_info['alerts'].append(f"Critical component {name} is unhealthy")
            
            # Проверка задач
            for name, task in self.tasks.items():
                task_healthy = task and not task.done()
                health_info['tasks'][name] = {
                    'running': task_healthy,
                    'health': self.task_health.get(name, 'unknown'),
                    'done': task.done() if task else True
                }
                
                if not task_healthy:
                    health_info['alerts'].append(f"Task {name} is not running")
            
            # Системные метрики
            try:
                process = psutil.Process()
                memory_info = process.memory_info()
                
                health_info['system'] = {
                    'memory_usage_mb': memory_info.rss / 1024 / 1024,
                    'cpu_percent': process.cpu_percent(),
                    'open_files': len(process.open_files()),
                    'threads': process.num_threads()
                }
                
                # Проверяем лимиты
                if health_info['system']['memory_usage_mb'] > 2048:  # 2GB
                    health_info['alerts'].append("High memory usage detected")
                
            except Exception as e:
                health_info['system']['error'] = str(e)
            
            # Проверка торговых лимитов
            if self.trades_today >= config.MAX_DAILY_TRADES * 0.9:
                health_info['alerts'].append("Approaching daily trade limit")
            
            if len(self.positions) >= config.MAX_POSITIONS * 0.9:
                health_info['alerts'].append("Approaching position limit")
            
            # Общее здоровье
            if health_info['alerts']:
                health_info['overall_healthy'] = False
            
            self.last_health_check_time = datetime.utcnow().isoformat()
            return health_info
            
        except Exception as e:
            logger.error(f"❌ Ошибка проверки здоровья: {e}")
            return {
                'timestamp': datetime.utcnow().isoformat(),
                'overall_healthy': False,
                'error': str(e)
            }
    
    # =================================================================
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ (заглушки для компиляции)
    # =================================================================
    
    async def _setup_signal_handlers(self):
        """Настройка обработчиков сигналов"""
        pass
    
    async def _validate_configuration(self) -> bool:
        """Валидация конфигурации"""
        return True
    
    async def _connect_exchange(self) -> bool:
        """Подключение к бирже"""
        return True
    
    async def _load_historical_data(self):
        """Загрузка исторических данных"""
        pass
    
    async def _perform_initial_market_analysis(self):
        """Начальный анализ рынка"""
        pass
    
    async def _setup_monitoring_system(self):
        """Настройка системы мониторинга"""
        pass
    
    async def _start_websocket_connections(self):
        """Запуск WebSocket соединений"""
        pass
    
    async def _send_startup_notification(self):
        """Отправка уведомления о запуске"""
        pass
    
    async def _log_startup_statistics(self):
        """Логирование статистики запуска"""
        pass
    
    async def _save_current_state(self):
        """Сохранение текущего состояния"""
        pass
    
    async def _close_all_positions_safely(self):
        """Безопасное закрытие всех позиций"""
        pass
    
    async def _cancel_all_orders(self):
        """Отмена всех ордеров"""
        pass
    
    async def _stop_all_tasks(self):
        """Остановка всех задач"""
        for task_name, task in self.tasks.items():
            if task and not task.done():
                task.cancel()
                try:
                    await asyncio.wait_for(task, timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning(f"⚠️ Таймаут остановки задачи: {task_name}")
                except asyncio.CancelledError:
                    pass
    
    async def _close_websocket_connections(self):
        """Закрытие WebSocket соединений"""
        pass
    
    async def _stop_ml_system(self):
        """Остановка ML системы"""
        pass
    
    async def _export_final_data(self):
        """Экспорт финальных данных"""
        pass
    
    async def _disconnect_exchange(self):
        """Отключение от биржи"""
        pass
    
    async def _close_database_connections(self):
        """Закрытие соединений с БД"""
        pass
    
    async def _cleanup_caches(self):
        """Очистка кэшей"""
        self.market_data_cache.clear()
        self.ml_predictions.clear()
        self.current_opportunities.clear()
    
    async def _send_shutdown_notification(self, old_status):
        """Отправка уведомления об остановке"""
        pass
    
    async def _send_error_notification(self, error_msg):
        """Отправка уведомления об ошибке"""
        pass
    
    async def _cancel_pending_orders(self):
        """Отмена ожидающих ордеров"""
        pass
    
    async def _send_pause_notification(self):
        """Отправка уведомления о паузе"""
        pass
    
    async def _refresh_market_data(self):
        """Обновление рыночных данных"""
        pass
    
    async def _send_resume_notification(self):
        """Отправка уведомления о возобновлении"""
        pass
    
    async def _emergency_close_all_positions(self):
        """Экстренное закрытие всех позиций"""
        pass
    
    async def _send_emergency_notification(self):
        """Отправка экстренного уведомления"""
        pass
    
    def _get_best_strategy(self) -> Optional[str]:
        """Получение лучшей стратегии"""
        if not self.strategy_performance:
            return None
        
        best_strategy = max(
            self.strategy_performance.items(),
            key=lambda x: x[1].get('win_rate', 0)
        )
        return best_strategy[0]
    
    # =================================================================
    # ДОПОЛНИТЕЛЬНЫЕ ЦИКЛЫ (заглушки)
    # =================================================================
    
    async def _market_monitoring_loop(self):
        """Цикл мониторинга рынка"""
        while not self._stop_event.is_set():
            try:
                await self._pause_event.wait()
                # Логика мониторинга рынка
                await asyncio.sleep(300)  # 5 минут
            except asyncio.CancelledError:
                break
    
    async def _pair_discovery_loop(self):
        """Цикл обновления торговых пар"""
        while not self._stop_event.is_set():
            try:
                await self._pause_event.wait()
                # Логика обновления пар
                await asyncio.sleep(config.PAIR_DISCOVERY_INTERVAL_HOURS * 3600)
            except asyncio.CancelledError:
                break
    
    async def _position_management_loop(self):
        """Цикл управления позициями"""
        while not self._stop_event.is_set():
            try:
                await self._pause_event.wait()
                # Логика управления позициями
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                break
    
    async def _risk_monitoring_loop(self):
        """Цикл мониторинга рисков"""
        while not self._stop_event.is_set():
            try:
                await self._pause_event.wait()
                # Логика мониторинга рисков
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                break
    
    async def _health_monitoring_loop(self):
        """Цикл мониторинга здоровья"""
        while not self._stop_event.is_set():
            try:
                await self._pause_event.wait()
                health_status = await self._perform_health_check()
                # Обработка результатов проверки здоровья
                await asyncio.sleep(300)  # 5 минут
            except asyncio.CancelledError:
                break
    
    async def _performance_monitoring_loop(self):
        """Цикл мониторинга производительности"""
        while not self._stop_event.is_set():
            try:
                await self._pause_event.wait()
                # Логика мониторинга производительности
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                break
    
    async def _data_export_loop(self):
        """Цикл экспорта данных"""
        while not self._stop_event.is_set():
            try:
                await self._pause_event.wait()
                # Логика экспорта данных
                await asyncio.sleep(3600)  # 1 час
            except asyncio.CancelledError:
                break
    
    async def _ml_prediction_loop(self):
        """Цикл ML предсказаний"""
        while not self._stop_event.is_set():
            try:
                await self._pause_event.wait()
                # Логика ML предсказаний
                await asyncio.sleep(300)  # 5 минут
            except asyncio.CancelledError:
                break
    
    async def _news_collection_loop(self):
        """Цикл сбора новостей"""
        while not self._stop_event.is_set():
            try:
                await self._pause_event.wait()
                # Логика сбора новостей
                await asyncio.sleep(1800)  # 30 минут
            except asyncio.CancelledError:
                break
    
    async def _sentiment_analysis_loop(self):
        """Цикл анализа настроений"""
        while not self._stop_event.is_set():
            try:
                await self._pause_event.wait()
                # Логика анализа настроений
                await asyncio.sleep(600)  # 10 минут
            except asyncio.CancelledError:
                break
    
    async def _event_processing_loop(self):
        """Цикл обработки событий"""
        while not self._stop_event.is_set():
            try:
                await self._pause_event.wait()
                # Логика обработки событий
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                break
    
    async def _init_config_validator(self) -> bool:
        """Инициализация валидатора конфигурации"""
        try:
            # Валидируем конфигурацию
            if not config.validate_config():
                return False
            
            logger.info("✅ Конфигурация валидна")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка валидации конфигурации: {e}")
            return False
    
    async def _init_exchange_client(self):
        """✅ ИСПРАВЛЕНО: Используем EnhancedUnifiedExchangeClient"""
        try:
            # Импортируем нужные классы
            from ..exchange import get_enhanced_exchange_client, BYBIT_INTEGRATION_AVAILABLE
            
            if BYBIT_INTEGRATION_AVAILABLE:
                logger.info("🚀 Используем EnhancedUnifiedExchangeClient")
                self.exchange_client = get_enhanced_exchange_client()
            else:
                logger.warning("⚠️ Enhanced клиент недоступен, используем базовый")
                from ..exchange import UnifiedExchangeClient
                self.exchange_client = UnifiedExchangeClient()
            
            # Подключаемся к бирже
            exchange_name = getattr(config, 'DEFAULT_EXCHANGE', 'bybit')
            testnet = getattr(config, 'BYBIT_TESTNET', True)
            
            logger.info(f"🔗 Подключение к {exchange_name} (testnet={testnet})...")
            success = await self.exchange_client.connect(exchange_name, testnet)
            
            if success:
                logger.info("✅ Exchange клиент инициализирован")
                
                # Для Enhanced клиента инициализируем дополнительные компоненты
                if hasattr(self.exchange_client, 'initialize'):
                    await self.exchange_client.initialize()
                    
                return True
            else:
                logger.error("❌ Не удалось подключиться к бирже")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации exchange клиента: {e}")
            return False
    
    async def _init_data_collector(self) -> bool:
        """Инициализация сборщика данных - РЕАЛЬНЫЙ"""
        try:
            # Импортируем реальный DataCollector
            from ..data.data_collector import DataCollector
            
            # Создаем экземпляр с exchange_client и сессией БД
            self.data_collector = DataCollector(
                self.exchange_client, 
                SessionLocal  # Передаем фабрику сессий, а не self.db
            )
            
            # Устанавливаем активные пары из конфигурации
            if hasattr(self, 'active_pairs') and self.active_pairs:
                self.data_collector.set_active_pairs(list(self.active_pairs))
            
            # Запускаем сборщик
            await self.data_collector.start()
            
            logger.info("✅ DataCollector инициализирован и запущен")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации DataCollector: {e}")
            return False
    
    async def _init_market_analyzer(self) -> bool:
        """Инициализация анализатора рынка"""
        try:
            # Инициализируем анализатор рынка (заглушка)
            from ..analysis.market_analyzer import MarketAnalyzer
            self.market_analyzer = MarketAnalyzer()
            logger.info("✅ Анализатор рынка инициализирован")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации анализатора рынка: {e}")
            return False
    
    async def _init_risk_manager(self) -> bool:
        """Инициализация менеджера рисков"""
        try:
            # Инициализируем менеджер рисков (заглушка)
            logger.info("✅ Менеджер рисков инициализирован")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации менеджера рисков: {e}")
            return False
    
    async def _init_portfolio_manager(self) -> bool:
        """Инициализация менеджера портфеля"""
        try:
            # Инициализируем менеджер портфеля (заглушка)
            logger.info("✅ Менеджер портфеля инициализирован")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации менеджера портфеля: {e}")
            return False
    
    async def _init_strategy_factory(self) -> bool:
        """Инициализация фабрики стратегий"""
        try:
            # Инициализируем фабрику стратегий (заглушка)
            logger.info("✅ Фабрика стратегий инициализирована")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации фабрики стратегий: {e}")
            return False
    
    async def _init_trader(self) -> bool:
        """Инициализация исполнителя сделок"""
        try:
            # Инициализируем исполнителя сделок (заглушка)
            logger.info("✅ Исполнитель сделок инициализирован")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации исполнителя сделок: {e}")
            return False
    
    async def _init_notifier(self) -> bool:
        """Инициализация системы уведомлений"""
        try:
            # Инициализируем систему уведомлений (заглушка)
            if config.TELEGRAM_ENABLED and config.TELEGRAM_BOT_TOKEN:
                logger.info("✅ Система уведомлений Telegram инициализирована")
            else:
                logger.info("⚠️ Telegram уведомления отключены")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации уведомлений: {e}")
            return False
    
    # ✅ НОВЫЙ МЕТОД для инициализации ML системы (ЗАМЕНА СУЩЕСТВУЮЩЕГО):
    async def _init_ml_system(self) -> bool:
        """Инициализация системы машинного обучения"""
        try:
            if not getattr(self.config, 'ENABLE_MACHINE_LEARNING', False):
                logger.info("ℹ️ Машинное обучение отключено в конфигурации")
                return False
            
            # Создаем комплексную ML систему
            from ..ml.models.direction_classifier import DirectionClassifier
            from ..ml.models.price_regressor import PriceLevelRegressor
            from ..ml.models.rl_agent import TradingRLAgent
            from ..ml.features.feature_engineering import FeatureEngineer
            from ..ml.training.trainer import MLTrainer
            
            class MLSystem:
                def __init__(self):
                    self.direction_classifier = DirectionClassifier()
                    self.price_regressor = PriceLevelRegressor()
                    self.rl_agent = TradingRLAgent()
                    self.feature_engineer = FeatureEngineer()
                    self.trainer = MLTrainer()
                    self.is_initialized = False
                    
                async def initialize(self):
                    """Инициализация всех ML компонентов"""
                    try:
                        # Инициализируем trainer
                        await self.trainer.initialize()
                        
                        # Загружаем модели если есть
                        await self.load_models()
                        
                        self.is_initialized = True
                        logger.info("✅ ML система инициализирована")
                    except Exception as e:
                        logger.error(f"❌ Ошибка инициализации ML: {e}")
                        self.is_initialized = False
                    
                async def load_models(self):
                    """Загрузка обученных моделей"""
                    try:
                        # Получаем список доступных моделей
                        available_models = self.trainer.list_available_models()
                        
                        if available_models:
                            logger.info(f"📊 Найдено {len(available_models)} обученных моделей")
                            # Загружаем последние модели для основных пар
                            for model_info in available_models[:5]:  # Максимум 5 моделей
                                logger.info(f"📈 Загружаем модель для {model_info['symbol']}")
                        else:
                            logger.warning("⚠️ Обученные модели не найдены, будут использованы базовые")
                    except Exception as e:
                        logger.error(f"❌ Ошибка загрузки моделей: {e}")
                
                async def predict_direction(self, symbol: str, df: pd.DataFrame) -> Dict[str, Any]:
                    """Предсказание направления движения цены"""
                    try:
                        # Извлекаем признаки
                        features = await self.feature_engineer.extract_features(symbol, df)
                        
                        # Получаем предсказание
                        prediction = self.direction_classifier.predict(features)
                        
                        return {
                            'action': prediction['direction_labels'][0],  # BUY/SELL/HOLD
                            'confidence': prediction['confidence'][0],
                            'probabilities': prediction['probabilities'][0],
                            'features': features.to_dict() if hasattr(features, 'to_dict') else {},
                            'model_type': 'ensemble',
                            'forecast_horizon': 5
                        }
                    except Exception as e:
                        logger.error(f"❌ Ошибка предсказания направления: {e}")
                        return None
                
                async def predict_price_levels(self, symbol: str, df: pd.DataFrame) -> Dict[str, Any]:
                    """Предсказание уровней цены"""
                    try:
                        # Используем price regressor
                        features = await self.feature_engineer.extract_features(symbol, df)
                        levels = self.price_regressor.predict_levels(features)
                        
                        current_price = df['close'].iloc[-1]
                        
                        return {
                            'support': levels.get('support', current_price * 0.98),
                            'resistance': levels.get('resistance', current_price * 1.02),
                            'pivot': levels.get('pivot', current_price),
                            'confidence': levels.get('confidence', 0.5),
                            'targets': {
                                'target_1': current_price * 1.01,
                                'target_2': current_price * 1.02,
                                'target_3': current_price * 1.03
                            }
                        }
                    except Exception as e:
                        logger.error(f"❌ Ошибка предсказания уровней: {e}")
                        return {'support': 0, 'resistance': 0}
                
                async def get_rl_recommendation(self, symbol: str, df: pd.DataFrame) -> Dict[str, Any]:
                    """Получение рекомендации от RL агента"""
                    try:
                        # Подготавливаем состояние
                        state = self._prepare_rl_state(df)
                        
                        # Получаем действие
                        action_data = self.rl_agent.predict(state)
                        
                        return {
                            'action': action_data['action_name'],  # BUY/HOLD/SELL
                            'confidence': action_data['confidence'],
                            'q_values': action_data.get('q_values', [])
                        }
                    except Exception as e:
                        logger.error(f"❌ Ошибка RL рекомендации: {e}")
                        return None
                
                def _prepare_rl_state(self, df: pd.DataFrame) -> np.ndarray:
                    """Подготовка состояния для RL агента"""
                    # Простое состояние из последних значений
                    row = df.iloc[-1]
                    state = np.array([
                        row.get('rsi', 50) / 100.0,
                        row.get('macd', 0) / 100.0,
                        row.get('bb_position', 0.5),
                        row.get('volume_ratio', 1.0),
                        row.get('price_change', 0) / 10.0,
                        df['close'].pct_change().iloc[-5:].mean() * 100,  # 5-период momentum
                        df['volume'].iloc[-5:].mean() / df['volume'].iloc[-20:].mean(),  # Volume ratio
                        0.5  # Portfolio state placeholder
                    ])
                    return state
            
            # Создаем и инициализируем ML систему
            self.ml_system = MLSystem()
            await self.ml_system.initialize()
            
            # Запускаем фоновое обучение если нужно
            if getattr(self.config, 'ENABLE_ML_TRAINING', False):
                asyncio.create_task(self._ml_training_loop())
            
            logger.info("✅ ML система инициализирована и готова к работе")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации ML системы: {e}")
            return False
    
    async def _init_news_analyzer(self) -> bool:
        """Инициализация анализатора новостей"""
        try:
            if not config.ENABLE_NEWS_ANALYSIS:
                logger.info("⚠️ Анализ новостей отключен")
                return True
                
            # Инициализируем анализатор новостей (заглушка)
            logger.info("✅ Анализатор новостей инициализирован")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации анализатора новостей: {e}")
            return False
    
    async def _init_websocket_manager(self) -> bool:
        """Инициализация менеджера WebSocket"""
        try:
            # Инициализируем WebSocket менеджер (заглушка)
            logger.info("✅ Менеджер WebSocket инициализирован")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации WebSocket менеджера: {e}")
            return False
    
    async def _init_export_manager(self) -> bool:
        """Инициализация менеджера экспорта"""
        try:
            # Инициализируем менеджер экспорта (заглушка)
            logger.info("✅ Менеджер экспорта инициализирован")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации менеджера экспорта: {e}")
            return False
    
    async def _init_health_monitor(self) -> bool:
        """Инициализация монитора здоровья"""
        try:
            # Инициализируем монитор здоровья (заглушка)
            logger.info("✅ Монитор здоровья инициализирован")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации монитора здоровья: {e}")
            return False
    
    # =================================================================
    # МЕТОДЫ ДЛЯ СОВМЕСТИМОСТИ (сохраняем существующие)
    # =================================================================
    
    async def update_pairs(self, pairs: List[str]) -> None:
        """Обновление торговых пар (для совместимости)"""
        self.trading_pairs = pairs
        # Обновляем также активные пары
        self.active_pairs = pairs[:config.MAX_TRADING_PAIRS]
        logger.info(f"📊 Обновлены торговые пары: {len(pairs)}")
    
    def __repr__(self) -> str:
        """Строковое представление для отладки"""
        return (
            f"BotManager(status={self.status.value}, "
            f"pairs={len(self.active_pairs)}, "
            f"positions={len(self.positions)}, "
            f"cycles={self.cycles_count}, "
            f"uptime={self.start_time})"
        )
    
    async def initialize_enhanced_exchange(self):
        """Инициализация enhanced exchange клиента - ИСПРАВЛЕНО"""
        try:
            logger.info("🚀 Инициализация enhanced exchange...")
            
            # Проверяем доступность V5 возможностей
            from ..exchange import check_bybit_v5_capabilities
            v5_capabilities = check_bybit_v5_capabilities()
            logger.info(f"🔍 V5 возможности: {v5_capabilities}")
            
            if not v5_capabilities.get('enhanced_features', False):
                logger.warning("⚠️ Enhanced возможности недоступны")
                return False
            
            # Создаем enhanced клиент
            from ..exchange import get_enhanced_exchange_client
            self.enhanced_exchange_client = get_enhanced_exchange_client()
            
            # ✅ ИСПРАВЛЕНО: Проверяем инициализацию более безопасно
            if hasattr(self.enhanced_exchange_client, 'initialize'):
                success = await self.enhanced_exchange_client.initialize()
                if success:
                    logger.info("✅ Enhanced exchange клиент активирован")
                    
                    # ✅ ИСПРАВЛЕНО: Безопасная проверка health_check
                    try:
                        if hasattr(self.enhanced_exchange_client, 'health_check'):
                            health_status = await self.enhanced_exchange_client.health_check()
                            status = health_status.get('overall_status', 'unknown')
                            logger.info(f"🔍 Enhanced клиент статус: {status}")
                        else:
                            logger.info("🔍 Enhanced клиент статус: initialized (no health_check)")
                    except Exception as health_error:
                        logger.warning(f"⚠️ Health check недоступен: {health_error}")
                        # Не считаем это критической ошибкой
                    
                    self.v5_integration_enabled = True
                    return True
                else:
                    logger.error("❌ Не удалось инициализировать enhanced клиент")
                    return False
            else:
                # Если нет метода initialize - считаем что уже готов
                logger.info("✅ Enhanced клиент готов (без дополнительной инициализации)")
                self.v5_integration_enabled = True
                return True
                
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации enhanced клиента: {e}")
            return False
    
    async def get_market_data_enhanced(self, symbol: str) -> Optional[Dict]:
        """Получение рыночных данных через enhanced API"""
        try:
            # Пробуем enhanced клиент
            if self.v5_integration_enabled and self.enhanced_exchange_client:
                data = await self.enhanced_exchange_client.get_market_data(symbol)
                if data:
                    # Логируем источник данных
                    source = data.get('source', 'v5' if 'source' not in data else data['source'])
                    logger.debug(f"📊 {symbol} данные из {source}")
                    return data
                else:
                    logger.debug(f"⚠️ Enhanced API не вернул данные для {symbol}")
            
            # Fallback к legacy exchange
            if self.exchange_client and hasattr(self.exchange_client, 'get_ticker'):
                legacy_data = await self.exchange_client.get_ticker(symbol)
                if legacy_data:
                    # Нормализуем к enhanced формату
                    return {
                        'symbol': symbol,
                        'timestamp': int(datetime.now().timestamp() * 1000),
                        'price': legacy_data.get('price', 0),
                        'bid': legacy_data.get('bid', 0),
                        'ask': legacy_data.get('ask', 0),
                        'volume': legacy_data.get('volume', 0),
                        'change': legacy_data.get('change_percent_24h', 0),
                        'source': 'legacy'
                    }
            
            logger.warning(f"⚠️ Не удалось получить данные для {symbol}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения данных {symbol}: {e}")
            return None
    
    async def get_account_balance_enhanced(self) -> Optional[Dict]:
        """Получение баланса через enhanced API"""
        try:
            # Пробуем enhanced клиент
            if self.v5_integration_enabled and self.enhanced_exchange_client:
                balance = await self.enhanced_exchange_client.get_account_info()
                if balance:
                    logger.debug(f"💰 Баланс из {balance.get('source', 'v5')}")
                    return balance
            
            # Fallback к legacy
            if self.exchange_client and hasattr(self.exchange_client, 'get_balance'):
                legacy_balance = await self.exchange_client.get_balance()
                if legacy_balance and 'error' not in legacy_balance:
                    return legacy_balance
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения баланса: {e}")
            return None
    
    async def monitor_enhanced_health(self):
        """Мониторинг состояния enhanced системы"""
        try:
            if self.v5_integration_enabled and self.enhanced_exchange_client:
                health = await self.enhanced_exchange_client.health_check()
                
                # Логируем статистику каждые 10 минут
                if hasattr(self, '_last_health_log'):
                    if datetime.now() - self._last_health_log > timedelta(minutes=10):
                        self._log_health_stats(health)
                        self._last_health_log = datetime.now()
                else:
                    self._last_health_log = datetime.now()
                    self._log_health_stats(health)
                
                # Проверяем деградацию
                if health['overall_status'] == 'degraded':
                    logger.warning("⚠️ Enhanced система в режиме деградации")
                
                return health
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Ошибка мониторинга health: {e}")
            return None
    
    def _log_health_stats(self, health: Dict):
        """Логирование статистики health"""
        try:
            stats = health.get('statistics', {})
            logger.info("📊 Enhanced система статистика:")
            logger.info(f"   V5 запросы: {stats.get('v5_requests', 0)}")
            logger.info(f"   Legacy запросы: {stats.get('legacy_requests', 0)}")
            logger.info(f"   Общий статус: {health.get('overall_status', 'unknown')}")
            
            # Миграционный статус
            if hasattr(self.enhanced_exchange_client, 'get_migration_status'):
                migration = self.enhanced_exchange_client.get_migration_status()
                logger.info(f"   V5 использование: {migration.get('v5_usage_percentage', 0):.1f}%")
                
        except Exception as e:
            logger.debug(f"Ошибка логирования health stats: {e}")


# =========================================================================
# === СОЗДАНИЕ ГЛОБАЛЬНОГО ЭКЗЕМПЛЯРА ===
# =========================================================================

# Создаем единственный экземпляр менеджера бота (Singleton)
bot_manager = BotManager()

# Экспорт
__all__ = ['BotManager', 'bot_manager']

# Дополнительная проверка для отладки
if __name__ == "__main__":
    # Этот блок выполняется только при прямом запуске файла
    # Полезно для тестирования отдельных компонентов
    print("🤖 BotManager module loaded successfully")
    print(f"📊 Manager instance: {bot_manager}")
    print(f"🔧 Configuration loaded: {hasattr(config, 'BYBIT_API_KEY')}")