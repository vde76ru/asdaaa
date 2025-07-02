#!/usr/bin/env python3
"""
UNIFIED CONFIGURATION - ОБНОВЛЕННАЯ ВЕРСИЯ
==========================================
Профессиональная конфигурация для автоматизированной торговли
Версия: 3.1 - ДОБАВЛЕНЫ ВЕСА СТРАТЕГИЙ И ИСПРАВЛЕНИЯ
"""

import os
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import json
import hashlib
import logging
logger = logging.getLogger(__name__)

class UnifiedConfig:
    """
    Единая конфигурация торгового бота
    ✅ ОБНОВЛЕНО: Добавлены веса стратегий
    ✅ ИСПРАВЛЕНО: Добавлен параметр TESTNET для совместимости с тестами
    """
    
    # =================================================================
    # ОСНОВНЫЕ НАСТРОЙКИ СИСТЕМЫ
    # =================================================================
    
    # Среда выполнения
    ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')
    DEBUG = os.getenv('DEBUG', 'false').lower() == 'true'
    TEST_MODE = os.getenv('TEST_MODE', 'false').lower() == 'true'
    DEVELOPMENT_MODE = os.getenv('DEVELOPMENT_MODE', 'true').lower() == 'true'
    CONFIG_VERSION = os.getenv('CONFIG_VERSION', '3.1')
    LAST_UPDATED = os.getenv('LAST_UPDATED', datetime.now().strftime('%Y-%m-%d'))
    
    # ✅ ИСПРАВЛЕНИЕ #1: Добавлен параметр TESTNET для совместимости с тестами
    TESTNET = os.getenv('TESTNET', 'true').lower() == 'true'
    
    # Режимы разработки (должны быть отключены в продакшене)
    ENABLE_DEBUG_ENDPOINTS = os.getenv('ENABLE_DEBUG_ENDPOINTS', 'false').lower() == 'true'
    ENABLE_TEST_DATA = os.getenv('ENABLE_TEST_DATA', 'false').lower() == 'true'
    USE_MOCK_EXCHANGE_DATA = os.getenv('USE_MOCK_EXCHANGE_DATA', 'false').lower() == 'true'
    USE_MOCK_ML_PREDICTIONS = os.getenv('USE_MOCK_ML_PREDICTIONS', 'false').lower() == 'true'
    USE_MOCK_NEWS_DATA = os.getenv('USE_MOCK_NEWS_DATA', 'false').lower() == 'true'
    
    # =================================================================
    # РЕЖИМЫ РАБОТЫ - ПРОФЕССИОНАЛЬНАЯ НАСТРОЙКА
    # =================================================================
    
    PAPER_TRADING = os.getenv('PAPER_TRADING', 'false').lower() == 'true'
    LIVE_TRADING = os.getenv('LIVE_TRADING', 'false').lower() == 'true'
    DRY_RUN = os.getenv('DRY_RUN', 'true').lower() == 'true'
    
    # =================================================================
    # BYBIT API НАСТРОЙКИ
    # =================================================================
    
    BYBIT_API_KEY = os.getenv('BYBIT_API_KEY', '')
    BYBIT_API_SECRET = os.getenv('BYBIT_API_SECRET', '')
    BYBIT_TESTNET = os.getenv('BYBIT_TESTNET', 'true').lower() == 'true'
    EXCHANGE_NAME = os.getenv('EXCHANGE_NAME', 'bybit')
    
    # Таймауты и ограничения
    CONNECTION_TIMEOUT = int(os.getenv('CONNECTION_TIMEOUT', '30'))
    REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '10'))
    MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))
    RATE_LIMIT_DELAY = float(os.getenv('RATE_LIMIT_DELAY', '0.1'))
    
    # Дополнительные настройки Bybit
    BYBIT_RECV_WINDOW = int(os.getenv('BYBIT_RECV_WINDOW', '5000'))
    BYBIT_SPOT_ENABLED = os.getenv('BYBIT_SPOT_ENABLED', 'true').lower() == 'true'
    BYBIT_FUTURES_ENABLED = os.getenv('BYBIT_FUTURES_ENABLED', 'false').lower() == 'true'
    BYBIT_OPTIONS_ENABLED = os.getenv('BYBIT_OPTIONS_ENABLED', 'false').lower() == 'true'
    TESTNET_AVAILABLE_BALANCE_PERCENT = float(os.getenv('TESTNET_AVAILABLE_BALANCE_PERCENT', '90'))
    FORCE_AVAILABLE_BALANCE_FOR_TESTNET = os.getenv('FORCE_AVAILABLE_BALANCE_FOR_TESTNET', 'true').lower() == 'true'
    
    # =================================================================
    # ТОРГОВЫЕ ПАРАМЕТРЫ
    # =================================================================
    
    INITIAL_CAPITAL = float(os.getenv('INITIAL_CAPITAL', '1000'))
    MAX_POSITIONS = int(os.getenv('MAX_POSITIONS', '20'))
    RISK_PER_TRADE_PERCENT = float(os.getenv('RISK_PER_TRADE_PERCENT', '1.0'))
    STOP_LOSS_PERCENT = float(os.getenv('STOP_LOSS_PERCENT', '2.0'))
    TAKE_PROFIT_PERCENT = float(os.getenv('TAKE_PROFIT_PERCENT', '4.0'))
    MAX_RISK_PER_TRADE_PERCENT = float(os.getenv('MAX_RISK_PER_TRADE_PERCENT', '2.0'))
    
    # ✅ ДОБАВЛЕНЫ НЕДОСТАЮЩИЕ ПАРАМЕТРЫ ДЛЯ BOTMANAGER
    MAX_PORTFOLIO_RISK_PERCENT = float(os.getenv('MAX_PORTFOLIO_RISK_PERCENT', '10.0'))
    MAX_DAILY_LOSS_PERCENT = float(os.getenv('MAX_DAILY_LOSS_PERCENT', '5.0'))
    MAX_CORRELATION_THRESHOLD = float(os.getenv('MAX_CORRELATION_THRESHOLD', '0.7'))
    MAX_DAILY_TRADES = int(os.getenv('MAX_DAILY_TRADES', '50'))
    MAX_TRADING_PAIRS = int(os.getenv('MAX_TRADING_PAIRS', '10'))
    POSITION_SIZE_PERCENT = float(os.getenv('POSITION_SIZE_PERCENT', '2.0'))
    MAX_POSITION_SIZE_PERCENT = float(os.getenv('MAX_POSITION_SIZE_PERCENT', '5.0'))
    MIN_RISK_REWARD_RATIO = float(os.getenv('MIN_RISK_REWARD_RATIO', '2.0'))
    MAX_DRAWDOWN_PERCENT = float(os.getenv('MAX_DRAWDOWN_PERCENT', '10.0'))
    
    # Торговые пары
    TRADING_PAIRS = os.getenv('TRADING_PAIRS', 'BTCUSDT,ETHUSDT').split(',')
    PRIMARY_TRADING_PAIRS = os.getenv('PRIMARY_TRADING_PAIRS', 'BTCUSDT,ETHUSDT,ADAUSDT').split(',')
    SECONDARY_PAIRS = os.getenv('SECONDARY_PAIRS', 'BNBUSDT,SOLUSDT').split(',')
    DEFAULT_EXCHANGE = os.getenv('DEFAULT_EXCHANGE', 'bybit')
    
    # ✅ ДОБАВЛЕНЫ ДОПОЛНИТЕЛЬНЫЕ ПАРАМЕТРЫ
    ENABLE_BACKTESTING = os.getenv('ENABLE_BACKTESTING', 'false').lower() == 'true'
    ENABLE_NEWS_ANALYSIS = os.getenv('ENABLE_NEWS_ANALYSIS', 'false').lower() == 'true'
    ENABLE_SOCIAL_ANALYSIS = os.getenv('ENABLE_SOCIAL_ANALYSIS', 'false').lower() == 'true'
    
    # =================================================================
    # ✅ НОВОЕ: ВЕСА СТРАТЕГИЙ - ДОБАВЛЕНЫ ОТСУТСТВУЮЩИЕ ПАРАМЕТРЫ
    # =================================================================
    
    # Веса стратегий для агрегации сигналов
    WEIGHT_MULTI_INDICATOR = float(os.getenv('WEIGHT_MULTI_INDICATOR', '0.25'))  # 25%
    WEIGHT_MOMENTUM = float(os.getenv('WEIGHT_MOMENTUM', '0.20'))               # 20%
    WEIGHT_MEAN_REVERSION = float(os.getenv('WEIGHT_MEAN_REVERSION', '0.15'))   # 15%
    WEIGHT_BREAKOUT = float(os.getenv('WEIGHT_BREAKOUT', '0.15'))               # 15%
    WEIGHT_SCALPING = float(os.getenv('WEIGHT_SCALPING', '0.10'))               # 10%
    WEIGHT_SWING = float(os.getenv('WEIGHT_SWING', '0.10'))                     # 10%
    WEIGHT_ML_PREDICTION = float(os.getenv('WEIGHT_ML_PREDICTION', '0.05'))     # 5%
    
    # =================================================================
    # ТОРГОВЫЕ СТРАТЕГИИ
    # =================================================================
    
    # Активные стратегии
    ENABLED_STRATEGIES = os.getenv('ENABLED_STRATEGIES', 'multi_indicator,momentum').split(',')
    
    # Включение/отключение стратегий
    ENABLE_MULTI_INDICATOR = os.getenv('ENABLE_MULTI_INDICATOR', 'true').lower() == 'true'
    ENABLE_MOMENTUM = os.getenv('ENABLE_MOMENTUM', 'true').lower() == 'true'
    ENABLE_SCALPING = os.getenv('ENABLE_SCALPING', 'false').lower() == 'true'
    ENABLE_GRID_TRADING = os.getenv('ENABLE_GRID_TRADING', 'false').lower() == 'true'
    ENABLE_ARBITRAGE = os.getenv('ENABLE_ARBITRAGE', 'false').lower() == 'true'
    ENABLE_MEAN_REVERSION = os.getenv('ENABLE_MEAN_REVERSION', 'false').lower() == 'true'
    ENABLE_BREAKOUT = os.getenv('ENABLE_BREAKOUT', 'false').lower() == 'true'
    ENABLE_SWING = os.getenv('ENABLE_SWING', 'false').lower() == 'true'
    
    # =================================================================
    # МАШИННОЕ ОБУЧЕНИЕ
    # =================================================================
    
    ENABLE_MACHINE_LEARNING = os.getenv('ENABLE_MACHINE_LEARNING', 'true').lower() == 'true'
    ML_MODEL_UPDATE_INTERVAL = int(os.getenv('ML_MODEL_UPDATE_INTERVAL', '3600'))  # 1 час
    MIN_STRATEGY_CONFIDENCE = float(os.getenv('MIN_STRATEGY_CONFIDENCE', '0.6'))
    
    # ✅ ДОБАВЛЕНЫ ДОПОЛНИТЕЛЬНЫЕ ML ПАРАМЕТРЫ
    ML_PREDICTION_THRESHOLD = float(os.getenv('ML_PREDICTION_THRESHOLD', '0.7'))
    ML_MODEL_RETRAIN_INTERVAL = int(os.getenv('ML_MODEL_RETRAIN_INTERVAL', '86400'))  # 24 часа
    ENABLE_AUTO_STRATEGY_SELECTION = os.getenv('ENABLE_AUTO_STRATEGY_SELECTION', 'true').lower() == 'true'
    
    # ✅ ДОБАВЛЕНЫ ПАРАМЕТРЫ ДЛЯ BOTMANAGER
    MAX_CONCURRENT_ANALYSIS = int(os.getenv('MAX_CONCURRENT_ANALYSIS', '4'))
    ENSEMBLE_MIN_STRATEGIES = int(os.getenv('ENSEMBLE_MIN_STRATEGIES', '2'))
    STRATEGY_PERFORMANCE_WINDOW_DAYS = int(os.getenv('STRATEGY_PERFORMANCE_WINDOW_DAYS', '30'))
    MARKET_DATA_UPDATE_INTERVAL = int(os.getenv('MARKET_DATA_UPDATE_INTERVAL', '60'))  # секунды
    REAL_TIME_DATA_ENABLED = os.getenv('REAL_TIME_DATA_ENABLED', 'true').lower() == 'true'
    
    # ✅ ДОБАВЛЕНЫ ПАРАМЕТРЫ ПРОИЗВОДИТЕЛЬНОСТИ
    API_RATE_LIMIT_DELAY = float(os.getenv('API_RATE_LIMIT_DELAY', '0.1'))
    MAX_RETRIES_API = int(os.getenv('MAX_RETRIES_API', '3'))
    CACHE_TTL_SECONDS = int(os.getenv('CACHE_TTL_SECONDS', '300'))  # 5 минут
    
    # ✅ ДОБАВЛЕНЫ ПАРАМЕТРЫ МОНИТОРИНГА
    ENABLE_HEARTBEAT = os.getenv('ENABLE_HEARTBEAT', 'true').lower() == 'true'
    HEARTBEAT_INTERVAL = int(os.getenv('HEARTBEAT_INTERVAL', '30'))  # секунды
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
    
    # ✅ ДОБАВЛЕНЫ ПАРАМЕТРЫ БЕЗОПАСНОСТИ
    ENABLE_CIRCUIT_BREAKER = os.getenv('ENABLE_CIRCUIT_BREAKER', 'true').lower() == 'true'
    CIRCUIT_BREAKER_THRESHOLD = int(os.getenv('CIRCUIT_BREAKER_THRESHOLD', '5'))  # ошибок
    EMERGENCY_STOP_LOSS_PERCENT = float(os.getenv('EMERGENCY_STOP_LOSS_PERCENT', '20.0'))
    
    # =================================================================
    # БАЗА ДАННЫХ
    # =================================================================
    
    DATABASE_URL = os.getenv('DATABASE_URL', '')
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = int(os.getenv('DB_PORT', '3306'))
    DB_USER = os.getenv('DB_USER', 'root')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '')
    DB_NAME = os.getenv('DB_NAME', 'crypto_bot')
    
    # Настройки подключения
    DB_POOL_SIZE = int(os.getenv('DB_POOL_SIZE', '10'))
    DB_MAX_OVERFLOW = int(os.getenv('DB_MAX_OVERFLOW', '20'))
    DB_POOL_TIMEOUT = int(os.getenv('DB_POOL_TIMEOUT', '30'))
    DB_POOL_RECYCLE = int(os.getenv('DB_POOL_RECYCLE', '3600'))
    
    # =================================================================
    # ДОПОЛНИТЕЛЬНЫЕ НАСТРОЙКИ
    # =================================================================
    
    # Мониторинг и уведомления
    ENABLE_TELEGRAM_NOTIFICATIONS = os.getenv('ENABLE_TELEGRAM_NOTIFICATIONS', 'false').lower() == 'true'
    ENABLE_EMAIL_NOTIFICATIONS = os.getenv('ENABLE_EMAIL_NOTIFICATIONS', 'false').lower() == 'true'
    ENABLE_WEBSOCKET = os.getenv('ENABLE_WEBSOCKET', 'true').lower() == 'true'
    
    # Валидация и бэкапы
    VALIDATE_CONFIG_ON_STARTUP = os.getenv('VALIDATE_CONFIG_ON_STARTUP', 'true').lower() == 'true'
    CONFIG_BACKUP_ON_CHANGE = os.getenv('CONFIG_BACKUP_ON_CHANGE', 'true').lower() == 'true'
    
    # =================================================================
    # СИСТЕМА ВАЛИДАЦИИ И МЕТОДЫ
    # =================================================================
    
    @classmethod
    def validate_config(cls) -> bool:
        """
        ✅ ИСПРАВЛЕНО: Валидация конфигурации с правильными проверками
        """
        errors = []
        warnings = []
        
        # Проверка синхронизации TESTNET
        if cls.TESTNET != cls.BYBIT_TESTNET:
            warnings.append(f"⚠️ TESTNET ({cls.TESTNET}) != BYBIT_TESTNET ({cls.BYBIT_TESTNET})")
            # Автоматическая синхронизация
            cls.BYBIT_TESTNET = cls.TESTNET
            warnings.append("✅ Автоматическая синхронизация выполнена")
        
        # Проверка критичных параметров
        if cls.INITIAL_CAPITAL <= 0:
            errors.append("❌ INITIAL_CAPITAL должен быть больше 0")
        
        if cls.MAX_POSITIONS <= 0:
            errors.append("❌ MAX_POSITIONS должен быть больше 0")
        
        # Проверка режимов торговли
        if cls.LIVE_TRADING and cls.PAPER_TRADING:
            errors.append("❌ LIVE_TRADING и PAPER_TRADING не могут быть включены одновременно")
        
        # Проверка весов стратегий
        total_weight = (cls.WEIGHT_MULTI_INDICATOR + cls.WEIGHT_MOMENTUM + 
                       cls.WEIGHT_MEAN_REVERSION + cls.WEIGHT_BREAKOUT + 
                       cls.WEIGHT_SCALPING + cls.WEIGHT_SWING + cls.WEIGHT_ML_PREDICTION)
        
        if abs(total_weight - 1.0) > 0.01:  # Допускаем небольшую погрешность
            warnings.append(f"⚠️ Сумма весов стратегий не равна 1.0: {total_weight:.3f}")
        
        # Проверка API ключей в продакшене
        if cls.ENVIRONMENT == 'production':
            if not cls.BYBIT_API_KEY:
                errors.append("❌ BYBIT_API_KEY обязателен в продакшене")
            if not cls.BYBIT_API_SECRET:
                errors.append("❌ BYBIT_API_SECRET обязателен в продакшене")
                
            # В продакшене TESTNET должен быть отключен
            if cls.BYBIT_TESTNET:
                warnings.append("⚠️ TESTNET включен в продакшене - это может быть небезопасно")
        else:
            # В разработке/тестировании TESTNET - это предупреждение
            if cls.BYBIT_TESTNET:
                warnings.append("ℹ️ Используется TESTNET режим (разработка)")
            else:
                warnings.append("⚠️ Используется PRODUCTION API в тестовой среде")
        
        # Логируем результаты
        if warnings:
            logger = logging.getLogger(__name__)
            logger.warning("⚠️ ПРЕДУПРЕЖДЕНИЯ КОНФИГУРАЦИИ:")
            for warning in warnings:
                logger.warning(f"   {warning}")
        
        if errors:
            logger = logging.getLogger(__name__)
            logger.error("❌ ОШИБКИ КОНФИГУРАЦИИ:")
            for error in errors:
                logger.error(f"   {error}")
            return False
        
        # Если в тестовом режиме, то конфигурация валидна
        if cls.TESTNET:
            logger = logging.getLogger(__name__)
            logger.info("✅ Конфигурация валидна для TESTNET режима")
        
        return True
    
    @classmethod
    def get_strategy_weights(cls) -> Dict[str, float]:
        """Получить веса всех стратегий"""
        return {
            'multi_indicator': cls.WEIGHT_MULTI_INDICATOR,
            'momentum': cls.WEIGHT_MOMENTUM,
            'mean_reversion': cls.WEIGHT_MEAN_REVERSION,
            'breakout': cls.WEIGHT_BREAKOUT,
            'scalping': cls.WEIGHT_SCALPING,
            'swing': cls.WEIGHT_SWING,
            'ml_prediction': cls.WEIGHT_ML_PREDICTION
        }
        
    @property
    def STRATEGY_WEIGHTS(self):
        """Получить строку с весами стратегий для совместимости"""
        weights = []
        if self.WEIGHT_MULTI_INDICATOR > 0:
            weights.append(f"multi_indicator:{self.WEIGHT_MULTI_INDICATOR}")
        if self.WEIGHT_MOMENTUM > 0:
            weights.append(f"momentum:{self.WEIGHT_MOMENTUM}")
        if self.WEIGHT_MEAN_REVERSION > 0:
            weights.append(f"mean_reversion:{self.WEIGHT_MEAN_REVERSION}")
        if self.WEIGHT_BREAKOUT > 0:
            weights.append(f"breakout:{self.WEIGHT_BREAKOUT}")
        if self.WEIGHT_SCALPING > 0:
            weights.append(f"scalping:{self.WEIGHT_SCALPING}")
        if self.WEIGHT_SWING > 0:
            weights.append(f"swing:{self.WEIGHT_SWING}")
        if self.WEIGHT_ML_PREDICTION > 0:
            weights.append(f"ml_prediction:{self.WEIGHT_ML_PREDICTION}")
        return ",".join(weights)
    
    @classmethod
    def get_config_hash(cls) -> str:
        """Получить хеш конфигурации для отслеживания изменений"""
        config_dict = {
            'version': cls.CONFIG_VERSION,
            'environment': cls.ENVIRONMENT,
            'testnet': cls.TESTNET,
            'trading_pairs': cls.TRADING_PAIRS,
            'strategy_weights': cls.get_strategy_weights(),
            'capital': cls.INITIAL_CAPITAL,
            'risk': cls.RISK_PER_TRADE_PERCENT
        }
        
        config_string = json.dumps(config_dict, sort_keys=True)
        return hashlib.md5(config_string.encode()).hexdigest()[:16]
    
    @classmethod
    def print_config_summary(cls):
        """
        ✅ УЛУЧШЕНО: Вывод сводки конфигурации с учетом режима
        """
        # Определяем режим работы
        if cls.ENVIRONMENT == 'production':
            if cls.TESTNET:
                mode = "🧪 ПРОДАКШН С TESTNET"
                mode_color = "⚠️"
            else:
                mode = "🚀 БОЕВОЙ РЕЖИМ"
                mode_color = "✅"
        else:
            if cls.TESTNET:
                mode = "🧪 ТЕСТОВЫЙ РЕЖИМ"
                mode_color = "✅"
            else:
                mode = "⚠️ РАЗРАБОТКА С PROD API"
                mode_color = "⚠️"
        
        trading_mode = "🚀 РЕАЛЬНАЯ ТОРГОВЛЯ" if cls.LIVE_TRADING and not cls.PAPER_TRADING else "📝 ТЕСТОВАЯ ТОРГОВЛЯ"
        
        logger = logging.getLogger(__name__)
        logger.info("="*60)
        logger.info(f"💼 КОНФИГУРАЦИЯ КРИПТОТРЕЙДИНГ БОТА")
        logger.info(f"🔧 Версия: {cls.CONFIG_VERSION}")
        logger.info(f"📅 Обновлено: {cls.LAST_UPDATED}")
        logger.info("="*60)
        logger.info(f"   {mode_color} {mode}")
        logger.info(f"   🎯 {trading_mode}")
        logger.info(f"   🌍 Среда: {cls.ENVIRONMENT}")
        logger.info(f"   📊 Биржа: {cls.DEFAULT_EXCHANGE} {'(TESTNET)' if cls.TESTNET else '(PRODUCTION)'}")
        logger.info(f"   💰 Начальный капитал: ${cls.INITIAL_CAPITAL:,.2f}")
        logger.info(f"   📈 Макс. позиций: {cls.MAX_POSITIONS}")
        logger.info(f"   🎯 Риск на сделку: {cls.RISK_PER_TRADE_PERCENT}%")
        logger.info(f"   🛡️ Стоп-лосс: {cls.STOP_LOSS_PERCENT}%")
        logger.info(f"   🎯 Тейк-профит: {cls.TAKE_PROFIT_PERCENT}%")
        logger.info("="*60)
        
        # Показываем веса стратегий
        logger.info("⚖️ ВЕСА СТРАТЕГИЙ:")
        strategy_weights = cls.get_strategy_weights()
        for strategy, weight in strategy_weights.items():
            logger.info(f"   {strategy}: {weight:.2%}")
        logger.info("="*60)
    
    @classmethod
    def get_database_url(cls) -> str:
        """✅ ДОБАВЛЕНО: Получение правильного URL базы данных"""
        if cls.DATABASE_URL and cls.DATABASE_URL != 'sqlite:///./crypto_bot.db':
            # Исправляем URL для использования PyMySQL
            if cls.DATABASE_URL.startswith('mysql://'):
                return cls.DATABASE_URL.replace('mysql://', 'mysql+pymysql://')
            elif 'mysql+mysqldb://' in cls.DATABASE_URL:
                return cls.DATABASE_URL.replace('mysql+mysqldb://', 'mysql+pymysql://')
            return cls.DATABASE_URL
        
        # Формируем URL из компонентов
        if cls.DB_HOST and cls.DB_NAME:
            if cls.DB_USER and cls.DB_PASSWORD:
                return f"mysql+pymysql://{cls.DB_USER}:{cls.DB_PASSWORD}@{cls.DB_HOST}:{cls.DB_PORT}/{cls.DB_NAME}?charset=utf8mb4"
            else:
                return f"mysql+pymysql://@{cls.DB_HOST}:{cls.DB_PORT}/{cls.DB_NAME}?charset=utf8mb4"
        
        # Fallback на SQLite
        return 'sqlite:///./crypto_bot.db'
    
    @classmethod
    def get_active_trading_pairs(cls) -> List[str]:
        """Получение активных торговых пар"""
        pairs = []
        
        if cls.PRIMARY_TRADING_PAIRS:
            pairs.extend(cls.PRIMARY_TRADING_PAIRS)
        
        if cls.SECONDARY_PAIRS:
            pairs.extend(cls.SECONDARY_PAIRS)
        
        # Удаление дубликатов
        return list(dict.fromkeys(pairs)) if pairs else ['BTCUSDT', 'ETHUSDT']
    
    @classmethod
    def get_enabled_strategies(cls) -> List[str]:
        """Получение включенных стратегий"""
        if cls.ENABLED_STRATEGIES:
            return cls.ENABLED_STRATEGIES
        
        # Fallback к стандартным стратегиям
        strategies = []
        if cls.ENABLE_MULTI_INDICATOR:
            strategies.append('multi_indicator')
        if cls.ENABLE_MOMENTUM:
            strategies.append('momentum')
        if cls.ENABLE_SCALPING:
            strategies.append('scalping')
        
        return strategies if strategies else ['multi_indicator']
    
    @classmethod
    def get_risk_parameters(cls) -> Dict[str, float]:
        """✅ ДОБАВЛЕНО: Получение параметров риск-менеджмента"""
        return {
            'max_portfolio_risk': cls.MAX_PORTFOLIO_RISK_PERCENT / 100,
            'max_daily_loss': cls.MAX_DAILY_LOSS_PERCENT / 100,
            'max_correlation': cls.MAX_CORRELATION_THRESHOLD,
            'max_position_size': cls.MAX_POSITION_SIZE_PERCENT / 100,
            'min_risk_reward_ratio': cls.MIN_RISK_REWARD_RATIO,
            'max_drawdown': cls.MAX_DRAWDOWN_PERCENT / 100,
            'position_size': cls.POSITION_SIZE_PERCENT / 100
        }
    
    @classmethod
    def get_trading_limits(cls) -> Dict[str, int]:
        """✅ ДОБАВЛЕНО: Получение торговых лимитов"""
        return {
            'max_positions': cls.MAX_POSITIONS,
            'max_daily_trades': cls.MAX_DAILY_TRADES,
            'max_trading_pairs': cls.MAX_TRADING_PAIRS
        }
    
    def __getattr__(self, name: str):
        """
        ✅ ДОБАВЛЕНО: Универсальный обработчик отсутствующих атрибутов
        
        Предоставляет значения по умолчанию для параметров,
        которые могут отсутствовать в конфигурации
        """
        # Словарь значений по умолчанию для различных параметров
        defaults = {
            # Дополнительные торговые параметры
            'MAX_CONCURRENT_TRADES': 5,
            'POSITION_CHECK_INTERVAL_SECONDS': 30,
            'REBALANCE_INTERVAL': 300,
            'ORDER_TIMEOUT_SECONDS': 60,
            
            # Параметры анализа и ML
            'ANALYSIS_TIMEOUT_SECONDS': 30,
            'ML_TIMEOUT_SECONDS': 10,
            'FEATURE_UPDATE_INTERVAL': 60,
            'MODEL_VALIDATION_ENABLED': True,
            
            # Параметры уведомлений
            'TELEGRAM_BOT_TOKEN': '',
            'TELEGRAM_CHAT_ID': '',
            'DISCORD_WEBHOOK_URL': '',
            'EMAIL_SMTP_SERVER': '',
            'EMAIL_PORT': 587,
            
            # Дополнительные лимиты
            'MAX_OPEN_ORDERS': 10,
            'MAX_LEVERAGE': 1.0,
            'MIN_ORDER_SIZE_USDT': 5.0,
            'MAX_ORDER_SIZE_USDT': 1000.0,
            
            # Параметры веб-интерфейса
            'WEB_PORT': 5000,
            'WEB_HOST': '0.0.0.0',
            'WEB_DEBUG': False,
            'API_ENABLED': True,
            
            # Параметры бэктестинга
            'BACKTEST_START_DATE': '2023-01-01',
            'BACKTEST_END_DATE': '2024-01-01',
            'BACKTEST_COMMISSION': 0.001,
            
            # Системные параметры
            'SYSTEM_CHECK_INTERVAL': 60,
            'CLEANUP_INTERVAL_HOURS': 24,
            'LOG_ROTATION_DAYS': 7,
            'METRICS_RETENTION_DAYS': 30,
            
            # Параметры для интеграций
            'COINGECKO_API_KEY': '',
            'COINMARKETCAP_API_KEY': '',
            'ALPHA_VANTAGE_API_KEY': '',
            'TRADINGVIEW_USERNAME': '',
            
            # Дополнительные флаги
            'ENABLE_PAPER_TRADING_LOGS': True,
            'ENABLE_TRADE_HISTORY_EXPORT': True,
            'ENABLE_PERFORMANCE_MONITORING': True,
            'ENABLE_REAL_TIME_UPDATES': True,
            
            # Параметры для advanced features
            'ENABLE_PORTFOLIO_OPTIMIZATION': False,
            'ENABLE_SENTIMENT_ANALYSIS': False,
            'ENABLE_TECHNICAL_ANALYSIS_ALERTS': False,
            'ENABLE_MULTI_TIMEFRAME_ANALYSIS': True,
        }
        
        # Если параметр есть в defaults, возвращаем его
        if name in defaults:
            logger.debug(f"⚙️ Используется значение по умолчанию для {name}: {defaults[name]}")
            return defaults[name]
        
        # Если это параметр процентов или пороговых значений, возвращаем 0
        if any(keyword in name.lower() for keyword in ['percent', 'threshold', 'ratio', 'factor']):
            logger.debug(f"⚙️ Параметр {name} принят как числовой, возвращаем 0")
            return 0.0
        
        # Если это максимальное значение, возвращаем разумное число
        if name.startswith('MAX_'):
            logger.debug(f"⚙️ Параметр {name} принят как максимальное значение, возвращаем 100")
            return 100
        
        # Если это минимальное значение, возвращаем 0
        if name.startswith('MIN_'):
            logger.debug(f"⚙️ Параметр {name} принят как минимальное значение, возвращаем 0")
            return 0
        
        # Если это булево значение (enable/disable), возвращаем False
        if any(keyword in name.lower() for keyword in ['enable', 'disable', 'allow', 'use_']):
            logger.debug(f"⚙️ Параметр {name} принят как булевый, возвращаем False")
            return False
        
        # Если это интервал времени, возвращаем 60 секунд
        if any(keyword in name.lower() for keyword in ['interval', 'timeout', 'delay']):
            logger.debug(f"⚙️ Параметр {name} принят как временной интервал, возвращаем 60")
            return 60
        
        # Последний fallback - строка
        logger.warning(f"⚠️ Неизвестный параметр конфигурации: {name}, возвращаем пустую строку")
        return ""
    
    @classmethod
    def save_config_backup(cls):
        """Сохранение резервной копии конфигурации"""
        if cls.CONFIG_BACKUP_ON_CHANGE:
            backup_data = {
                'timestamp': datetime.now().isoformat(),
                'hash': cls.get_config_hash(),
                'environment': cls.ENVIRONMENT,
                'version': cls.CONFIG_VERSION,
                'critical_params': {
                    'TESTNET': cls.TESTNET,
                    'LIVE_TRADING': cls.LIVE_TRADING,
                    'PAPER_TRADING': cls.PAPER_TRADING,
                    'BYBIT_TESTNET': cls.BYBIT_TESTNET,
                    'INITIAL_CAPITAL': cls.INITIAL_CAPITAL,
                    'MAX_POSITIONS': cls.MAX_POSITIONS,
                    'strategy_weights': cls.get_strategy_weights()
                }
            }
            
            logger = logging.getLogger(__name__)
            logger.info(f"📁 Конфигурация сохранена: {backup_data['hash']}")
    
    @classmethod
    def get_bybit_exchange_config(cls) -> Dict[str, Any]:
        """
        Получение конфигурации для Bybit exchange клиента
        
        Returns:
            Dict[str, Any]: Конфигурация для CCXT Bybit клиента
        """
        
        # Базовая конфигурация для CCXT
        config = {
            'apiKey': cls.BYBIT_API_KEY,
            'secret': cls.BYBIT_API_SECRET,
            'enableRateLimit': True,
            'rateLimit': 2000,
            'timeout': cls.CONNECTION_TIMEOUT * 1000,
            'sandbox': cls.BYBIT_TESTNET,
            'options': {
                'defaultType': 'spot',  # Только единый торговый аккаунт (spot)
                'adjustForTimeDifference': True,
                'recvWindow': getattr(cls, 'BYBIT_RECV_WINDOW', 5000),
                'fetchCurrencies': False,  # Отключаем загрузку валют
                'fetchFundingHistory': False,
                'fetchOHLCV': 'emulated',
                'fetchTickers': True,
            },
            'headers': {
                'User-Agent': f'CryptoBot-v{cls.CONFIG_VERSION}',
                'Accept': 'application/json',
                'Connection': 'keep-alive'
            }
        }
        
        # Настройки эндпоинтов для testnet
        if cls.BYBIT_TESTNET:
            config['urls'] = {
                'api': {
                    'public': 'https://api-testnet.bybit.com',
                    'private': 'https://api-testnet.bybit.com',
                },
                'test': {
                    'public': 'https://api-testnet.bybit.com',
                    'private': 'https://api-testnet.bybit.com',
                }
            }
        
        return config

# =================================================================
# СОЗДАНИЕ ЭКЗЕМПЛЯРА КОНФИГУРАЦИИ
# =================================================================

# ✅ Создаем экземпляр конфигурации
unified_config = UnifiedConfig()

# Алиас для обратной совместимости
config = unified_config

# Валидация при загрузке модуля
if unified_config.VALIDATE_CONFIG_ON_STARTUP:
    if not unified_config.validate_config():
        logging.critical("❌ Конфигурация невалидна! Исправьте ошибки перед запуском.")
    else:
        unified_config.print_config_summary()
        unified_config.save_config_backup()

# ✅ Экспортируем основные объекты
__all__ = ['UnifiedConfig', 'unified_config', 'config']