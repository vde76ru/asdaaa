#!/usr/bin/env python3
"""
УСОВЕРШЕНСТВОВАННЫЙ ТОРГОВЫЙ БОТ
==================================

Цель: Создать максимально автономный и прибыльный торговый бот

Особенности:
✅ Анализ ВСЕХ доступных валют на бирже
✅ Множественные стратегии с автоматическим выбором
✅ Умное управление рисками и позициями
✅ Машинное обучение для прогнозов
✅ Анализ новостей и социальных сетей
✅ Непрерывное самообучение
✅ Полная автоматизация без участия человека

Файл: src/bot/advanced_manager.py
"""

import asyncio
import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import json
import pickle
from collections import defaultdict, deque
import aiohttp
import ccxt.async_support as ccxt

# Импорты проекта
from ..core.database import SessionLocal
from ..core.models import *
from ..core.unified_config import unified_config as config
from ..exchange.client import ExchangeClient

from ..analysis.market_analyzer import MarketAnalyzer
from ..ml.models.price_predictor import PricePredictor
from ..ml.models.sentiment_analyzer import SentimentAnalyzer
from ..notifications.telegram import telegram_notifier

logger = logging.getLogger(__name__)

class MarketPhase(Enum):
    """Фазы рынка"""
    ACCUMULATION = "accumulation"    # Накопление
    MARKUP = "markup"                # Рост
    DISTRIBUTION = "distribution"    # Распределение  
    MARKDOWN = "markdown"            # Падение
    UNKNOWN = "unknown"              # Неопределенная

@dataclass
class TradingOpportunity:
    """Торговая возможность"""
    symbol: str
    strategy: str
    signal: TradingSignal
    score: float                    # Общий скор возможности
    risk_level: str                 # low, medium, high
    expected_profit: float          # Ожидаемая прибыль %
    max_loss: float                 # Максимальный убыток %
    market_phase: MarketPhase
    confidence: float               # Уверенность 0-1
    volume_score: float             # Скор объема
    news_sentiment: float           # Настроение новостей
    technical_score: float          # Технический анализ
    timestamp: datetime = field(default_factory=datetime.utcnow)

@dataclass
class MarketState:
    """Состояние рынка"""
    overall_trend: str              # BULLISH, BEARISH, SIDEWAYS
    volatility: str                 # LOW, MEDIUM, HIGH
    fear_greed_index: int          # 0-100
    btc_dominance: float           # Доминирование BTC
    total_market_cap: float        # Общая капитализация
    volume_24h: float              # Объем за 24ч
    active_coins: int              # Количество активных монет
    timestamp: datetime = field(default_factory=datetime.utcnow)

class AdvancedTradingBot:
    """
    Усовершенствованный торговый бот
    
    Функции:
    1. Автоматический поиск и анализ всех торговых пар
    2. Множественные стратегии с автоматическим выбором
    3. Машинное обучение и предиктивная аналитика
    4. Интеллектуальное управление рисками
    5. Анализ новостей и социальных сетей
    6. Адаптивные параметры на основе рыночных условий
    7. Непрерывное обучение и улучшение
    """

    def __init__(self):
        # Основные компоненты
        self.exchange = None
        self.market_analyzer = MarketAnalyzer()
        self.price_predictor = PricePredictor()
        self.sentiment_analyzer = SentimentAnalyzer()
        
        # Состояние системы
        self.is_running = False
        self.start_time = None
        self.total_cycles = 0
        
        # Торговые пары и возможности
        self.all_trading_pairs = []          # Все доступные пары
        self.active_pairs = []               # Активные для торговли
        self.blacklisted_pairs = set()       # Заблокированные пары
        self.opportunities = {}              # Текущие возможности
        self.positions = {}                  # Открытые позиции
        
        # Стратегии и модели
        self.available_strategies = [
            'multi_indicator',
            'momentum', 
            'mean_reversion',
            'breakout',
            'scalping',
            'swing',
            'ml_prediction',
            'sentiment_based',
            'arbitrage'
        ]
        self.strategy_performance = defaultdict(lambda: {
            'total_trades': 0,
            'winning_trades': 0,
            'total_profit': 0.0,
            'win_rate': 0.0,
            'avg_profit': 0.0,
            'max_drawdown': 0.0,
            'sharpe_ratio': 0.0
        })
        
        # Рыночные данные
        self.market_state = MarketState(
            overall_trend="UNKNOWN",
            volatility="MEDIUM", 
            fear_greed_index=50,
            btc_dominance=0.0,
            total_market_cap=0.0,
            volume_24h=0.0,
            active_coins=0
        )
        
        # Машинное обучение
        self.ml_models = {}
        self.feature_cache = {}
        self.prediction_cache = {}
        
        # Новости и социальные сети
        self.news_cache = deque(maxlen=1000)
        self.social_signals = deque(maxlen=500)
        
        # Конфигурация
        self.config = {
            # Торговые настройки
            'max_positions': 20,              # Увеличено с 1 до 20
            'max_daily_trades': 100,          # Увеличено с 10 до 100
            'position_size_percent': 2.0,     # 2% от баланса на позицию
            'max_risk_per_trade': 1.0,        # Максимальный риск 1%
            'min_profit_target': 1.5,         # Минимальная цель прибыли 1.5%
            
            # Селекция валют
            'min_volume_24h': 1000000,        # Минимальный объем $1M
            'min_market_cap': 10000000,       # Минимальная капитализация $10M
            'max_pairs_to_analyze': 200,      # Анализировать до 200 пар
            'pair_update_interval': 3600,     # Обновлять список пар каждый час
            
            # Стратегии
            'strategy_selection_method': 'adaptive',  # adaptive, best_performer, ensemble
            'min_strategy_confidence': 0.6,   # Минимальная уверенность 60%
            'ensemble_min_strategies': 3,     # Минимум стратегий для ансамбля
            
            # Риск-менеджмент
            'max_correlation': 0.7,           # Максимальная корреляция позиций
            'portfolio_risk_limit': 10.0,     # Максимальный риск портфеля 10%
            'stop_loss_atr_multiplier': 2.0,  # Стоп-лосс = 2 * ATR
            'take_profit_atr_multiplier': 4.0,# Тейк-профит = 4 * ATR
            'trailing_stop_enabled': True,    # Трейлинг стоп
            'dynamic_position_sizing': True,  # Динамическое изменение позиций
            
            # Машинное обучение
            'enable_ml_predictions': True,
            'ml_prediction_weight': 0.3,      # Вес ML предсказаний
            'retrain_interval_hours': 24,     # Переобучение каждые 24 часа
            'min_training_samples': 1000,     # Минимум данных для обучения
            
            # Анализ новостей
            'enable_news_analysis': True,
            'news_impact_weight': 0.2,        # Вес новостного анализа
            'sentiment_threshold': 0.1,       # Порог для реакции на новости
            
            # Производительность
            'analysis_interval': 60,          # Анализ каждые 60 сек
            'data_update_interval': 30,       # Обновление данных каждые 30 сек
            'health_check_interval': 300,     # Проверка здоровья каждые 5 мин
        }

    async def initialize(self) -> bool:
        """Инициализация всех компонентов системы"""
        logger.info("🚀 Инициализация усовершенствованного торгового бота...")
        
        try:
            # 1. Инициализация биржи
            logger.info("📡 Подключение к бирже...")
            self.exchange = ExchangeClient()
            await self.exchange.initialize()
            logger.info("✅ Биржа подключена")
            
            # 2. Загрузка всех торговых пар
            logger.info("💰 Загрузка торговых пар...")
            await self._load_all_trading_pairs()
            logger.info(f"✅ Загружено {len(self.all_trading_pairs)} торговых пар")
            
            # 3. Инициализация ML моделей
            logger.info("🧠 Инициализация ML моделей...")
            await self._initialize_ml_models()
            logger.info("✅ ML модели готовы")
            
            # 4. Загрузка исторических данных
            logger.info("📊 Загрузка исторических данных...")
            await self._load_historical_data()
            logger.info("✅ Исторические данные загружены")
            
            # 5. Анализ текущего состояния рынка
            logger.info("🌐 Анализ состояния рынка...")
            await self._analyze_market_state()
            logger.info("✅ Состояние рынка проанализировано")
            
            logger.info("🎯 Инициализация завершена успешно!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации: {e}")
            return False

    async def _load_all_trading_pairs(self):
        """Загрузка всех доступных торговых пар с биржи"""
        try:
            # Получаем все рынки с биржи
            markets = await self.exchange.fetch_markets()
            
            # Фильтруем по критериям
            filtered_pairs = []
            for market in markets:
                symbol = market['symbol']
                
                # Проверяем базовые требования
                if (market['quote'] == 'USDT' and 
                    market['active'] and 
                    not market.get('spot', True) == False):
                    
                    try:
                        # Получаем статистику 24ч
                        ticker = await self.exchange.fetch_ticker(symbol)
                        volume_24h = float(ticker.get('quoteVolume', 0))
                        
                        # Фильтр по объему
                        if volume_24h >= self.config['min_volume_24h']:
                            filtered_pairs.append({
                                'symbol': symbol,
                                'base': market['base'],
                                'quote': market['quote'],
                                'volume_24h': volume_24h,
                                'price': float(ticker.get('last', 0)),
                                'change_24h': float(ticker.get('percentage', 0))
                            })
                            
                    except Exception as e:
                        logger.debug(f"Ошибка получения данных для {symbol}: {e}")
                        continue
            
            # Сортируем по объему (больший объем = больше ликвидности)
            filtered_pairs.sort(key=lambda x: x['volume_24h'], reverse=True)
            
            # Ограничиваем количество
            max_pairs = self.config['max_pairs_to_analyze']
            self.all_trading_pairs = filtered_pairs[:max_pairs]
            
            # Выбираем активные пары для торговли (топ 50% по объему)
            active_count = min(50, len(self.all_trading_pairs) // 2)
            self.active_pairs = [pair['symbol'] for pair in self.all_trading_pairs[:active_count]]
            
            logger.info(f"📈 Отфильтровано {len(self.all_trading_pairs)} пар из {len(markets)}")
            logger.info(f"🎯 Активных для торговли: {len(self.active_pairs)}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки торговых пар: {e}")
            # Fallback к стандартным парам
            self.active_pairs = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT']

    async def _initialize_ml_models(self):
        """Инициализация машинного обучения"""
        try:
            # Модель предсказания цен
            self.ml_models['price_predictor'] = PricePredictor()
            
            # Модель анализа настроений
            self.ml_models['sentiment_analyzer'] = SentimentAnalyzer()
            
            # Модель классификации рыночных режимов
            from ..ml.models.regime_classifier import RegimeClassifier
            self.ml_models['regime_classifier'] = RegimeClassifier()
            
            # Модель оптимизации портфеля
            from ..ml.models.portfolio_optimizer import PortfolioOptimizer
            self.ml_models['portfolio_optimizer'] = PortfolioOptimizer()
            
            logger.info("🧠 ML модели инициализированы")
            
        except Exception as e:
            logger.warning(f"⚠️ Ошибка инициализации ML: {e}")
            self.config['enable_ml_predictions'] = False

    async def _load_historical_data(self):
        """Загрузка исторических данных для обучения"""
        try:
            # Загружаем данные для топ-20 пар
            top_pairs = self.active_pairs[:20]
            
            for symbol in top_pairs:
                try:
                    # Загружаем свечи за последние 30 дней
                    candles = await self.exchange.fetch_ohlcv(
                        symbol, '1h', limit=720  # 30 дней * 24 часа
                    )
                    
                    if candles:
                        df = pd.DataFrame(candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                        
                        # Сохраняем в кэш
                        self.feature_cache[symbol] = df
                        
                except Exception as e:
                    logger.debug(f"Ошибка загрузки данных для {symbol}: {e}")
                    continue
            
            logger.info(f"📊 Загружены исторические данные для {len(self.feature_cache)} пар")
            
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки исторических данных: {e}")

    async def _analyze_market_state(self):
        """Анализ общего состояния рынка"""
        try:
            # Анализируем топ-10 криптовалют
            top_symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'ADAUSDT', 
                          'XRPUSDT', 'DOTUSDT', 'AVAXUSDT', 'MATICUSDT', 'LINKUSDT']
            
            trends = []
            volumes = []
            changes_24h = []
            
            for symbol in top_symbols:
                try:
                    ticker = await self.exchange.fetch_ticker(symbol)
                    change_24h = float(ticker.get('percentage', 0))
                    volume_24h = float(ticker.get('quoteVolume', 0))
                    
                    changes_24h.append(change_24h)
                    volumes.append(volume_24h)
                    
                    # Определяем тренд
                    if change_24h > 2:
                        trends.append('BULLISH')
                    elif change_24h < -2:
                        trends.append('BEARISH')
                    else:
                        trends.append('SIDEWAYS')
                        
                except Exception:
                    continue
            
            # Определяем общий тренд
            bullish_count = trends.count('BULLISH')
            bearish_count = trends.count('BEARISH')
            
            if bullish_count > bearish_count * 1.5:
                overall_trend = 'BULLISH'
            elif bearish_count > bullish_count * 1.5:
                overall_trend = 'BEARISH'  
            else:
                overall_trend = 'SIDEWAYS'
            
            # Определяем волатильность
            avg_change = np.mean(np.abs(changes_24h)) if changes_24h else 0
            if avg_change > 5:
                volatility = 'HIGH'
            elif avg_change > 2:
                volatility = 'MEDIUM'
            else:
                volatility = 'LOW'
            
            # Обновляем состояние рынка
            self.market_state = MarketState(
                overall_trend=overall_trend,
                volatility=volatility,
                fear_greed_index=50,  # TODO: получать из API
                btc_dominance=0.0,    # TODO: рассчитывать
                total_market_cap=sum(volumes),
                volume_24h=sum(volumes),
                active_coins=len(self.active_pairs)
            )
            
            logger.info(f"🌐 Состояние рынка: {overall_trend}, волатильность: {volatility}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка анализа рынка: {e}")

    async def start(self) -> bool:
        """Запуск торгового бота"""
        if self.is_running:
            logger.warning("⚠️ Бот уже запущен")
            return False
        
        logger.info("🚀 Запуск усовершенствованного торгового бота...")
        
        # Инициализация
        if not await self.initialize():
            return False
        
        self.is_running = True
        self.start_time = datetime.utcnow()
        
        try:
            # Запускаем основные циклы
            await asyncio.gather(
                self._main_trading_loop(),
                self._market_monitoring_loop(),
                self._ml_training_loop(),
                self._risk_monitoring_loop(),
                self._news_monitoring_loop()
            )
        except Exception as e:
            logger.error(f"❌ Критическая ошибка в основном цикле: {e}")
            self.is_running = False
            return False

    async def _main_trading_loop(self):
        """Основной торговый цикл"""
        logger.info("🔄 Запуск основного торгового цикла...")
        
        while self.is_running:
            try:
                cycle_start = datetime.utcnow()
                self.total_cycles += 1
                
                logger.info(f"📊 Цикл #{self.total_cycles} - анализ {len(self.active_pairs)} пар")
                
                # 1. Поиск торговых возможностей
                opportunities = await self._find_trading_opportunities()
                
                # 2. Оценка и ранжирование
                ranked_opportunities = await self._rank_opportunities(opportunities)
                
                # 3. Управление позициями
                await self._manage_existing_positions()
                
                # 4. Открытие новых позиций
                await self._execute_new_trades(ranked_opportunities)
                
                # 5. Обновление статистики
                await self._update_performance_stats()
                
                # Расчет времени выполнения цикла
                cycle_time = (datetime.utcnow() - cycle_start).total_seconds()
                logger.info(f"⏱️ Цикл #{self.total_cycles} завершен за {cycle_time:.2f}с")
                
                # Пауза до следующего цикла
                await asyncio.sleep(max(0, self.config['analysis_interval'] - cycle_time))
                
            except Exception as e:
                logger.error(f"❌ Ошибка в торговом цикле: {e}")
                await asyncio.sleep(30)

    async def _find_trading_opportunities(self) -> List[TradingOpportunity]:
        """Поиск торговых возможностей по всем активным парам"""
        opportunities = []
        
        # Параллельный анализ всех пар
        tasks = []
        for symbol in self.active_pairs:
            if symbol not in self.blacklisted_pairs:
                task = self._analyze_trading_pair(symbol)
                tasks.append(task)
        
        # Выполняем анализ параллельно пачками по 10
        batch_size = 10
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i:i + batch_size]
            results = await asyncio.gather(*batch, return_exceptions=True)
            
            for result in results:
                if isinstance(result, TradingOpportunity):
                    opportunities.append(result)
                elif isinstance(result, Exception):
                    logger.debug(f"Ошибка анализа пары: {result}")
        
        logger.info(f"🎯 Найдено {len(opportunities)} торговых возможностей")
        return opportunities

    async def _analyze_trading_pair(self, symbol: str) -> Optional[TradingOpportunity]:
        """Анализ конкретной торговой пары"""
        try:
            # 1. Получаем рыночные данные
            market_data = await self._get_market_data(symbol)
            if not market_data:
                return None
            
            # 2. Технический анализ через множественные стратегии
            strategy_signals = await self._get_strategy_signals(symbol, market_data)
            
            # 3. ML предсказания (если включены)
            ml_prediction = None
            if self.config['enable_ml_predictions']:
                ml_prediction = await self._get_ml_prediction(symbol, market_data)
            
            # 4. Анализ новостей и настроений
            news_sentiment = 0.0
            if self.config['enable_news_analysis']:
                news_sentiment = await self._get_news_sentiment(symbol)
            
            # 5. Комбинируем все сигналы
            combined_signal = await self._combine_signals(
                strategy_signals, ml_prediction, news_sentiment
            )
            
            if combined_signal and combined_signal.confidence >= self.config['min_strategy_confidence']:
                # 6. Рассчитываем финальный скор
                opportunity = TradingOpportunity(
                    symbol=symbol,
                    strategy=combined_signal.reason.split(':')[0] if ':' in combined_signal.reason else 'combined',
                    signal=combined_signal,
                    score=combined_signal.confidence,
                    risk_level=self._assess_risk_level(market_data),
                    expected_profit=abs(combined_signal.take_profit - combined_signal.price) / combined_signal.price * 100,
                    max_loss=abs(combined_signal.stop_loss - combined_signal.price) / combined_signal.price * 100,
                    market_phase=self._determine_market_phase(market_data),
                    confidence=combined_signal.confidence,
                    volume_score=market_data.get('volume_score', 0.5),
                    news_sentiment=news_sentiment,
                    technical_score=np.mean([s.confidence for s in strategy_signals])
                )
                
                return opportunity
            
        except Exception as e:
            logger.debug(f"Ошибка анализа {symbol}: {e}")
            
        return None

    async def _get_market_data(self, symbol: str) -> Optional[Dict]:
        """Получение рыночных данных для символа"""
        try:
            # Получаем OHLCV данные
            candles = await self.exchange.fetch_ohlcv(symbol, '1h', limit=100)
            if not candles:
                return None
            
            df = pd.DataFrame(candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            # Текущая цена и объем
            ticker = await self.exchange.fetch_ticker(symbol)
            current_price = float(ticker['last'])
            volume_24h = float(ticker.get('quoteVolume', 0))
            
            # Рассчитываем индикаторы
            indicators = self._calculate_technical_indicators(df)
            
            # Оценка объема
            avg_volume = df['volume'].tail(20).mean()
            volume_score = min(1.0, df['volume'].iloc[-1] / avg_volume) if avg_volume > 0 else 0.5
            
            return {
                'symbol': symbol,
                'df': df,
                'current_price': current_price,
                'volume_24h': volume_24h,
                'volume_score': volume_score,
                'indicators': indicators,
                'ticker': ticker
            }
            
        except Exception as e:
            logger.debug(f"Ошибка получения данных {symbol}: {e}")
            return None

    def _calculate_technical_indicators(self, df: pd.DataFrame) -> Dict:
        """Расчет технических индикаторов"""
        try:
            from ta import add_all_ta_features
            
            # Добавляем все технические индикаторы
            df_with_indicators = add_all_ta_features(
                df, open="open", high="high", low="low", close="close", volume="volume"
            )
            
            # Извлекаем ключевые индикаторы
            last_row = df_with_indicators.iloc[-1]
            
            return {
                'rsi': last_row.get('momentum_rsi', 50),
                'macd': last_row.get('trend_macd', 0),
                'macd_signal': last_row.get('trend_macd_signal', 0),
                'bb_upper': last_row.get('volatility_bbh', 0),
                'bb_lower': last_row.get('volatility_bbl', 0),
                'sma_20': last_row.get('trend_sma_20', 0),
                'ema_12': last_row.get('trend_ema_12', 0),
                'ema_26': last_row.get('trend_ema_26', 0),
                'atr': last_row.get('volatility_atr', 0),
                'volume_adi': last_row.get('volume_adi', 0),
                'stoch_k': last_row.get('momentum_stoch', 50),
                'williams_r': last_row.get('momentum_wr', -50)
            }
            
        except Exception as e:
            logger.debug(f"Ошибка расчета индикаторов: {e}")
            return {}

    async def _get_strategy_signals(self, symbol: str, market_data: Dict) -> List[TradingSignal]:
        """Получение сигналов от всех стратегий"""
        signals = []
        
        # Импортируем и тестируем все доступные стратегии
        strategy_classes = {
            'multi_indicator': 'MultiIndicatorStrategy',
            'momentum': 'MomentumStrategy', 
            'mean_reversion': 'MeanReversionStrategy',
            'breakout': 'BreakoutStrategy',
            'scalping': 'ScalpingStrategy'
        }
        
        for strategy_name, strategy_class in strategy_classes.items():
            try:
                # Динамический импорт стратегии
                module = __import__(f'src.strategies.{strategy_name}', fromlist=[strategy_class])
                StrategyClass = getattr(module, strategy_class)
                
                # Создаем экземпляр стратегии
                strategy = StrategyClass()
                
                # Получаем сигнал
                signal = await strategy.analyze(symbol, market_data['df'])
                
                if signal and signal.action != 'WAIT':
                    # Добавляем информацию о стратегии
                    signal.reason = f"{strategy_name}: {signal.reason}"
                    signals.append(signal)
                    
            except Exception as e:
                logger.debug(f"Ошибка стратегии {strategy_name}: {e}")
                continue
        
        return signals

    async def _get_ml_prediction(self, symbol: str, market_data: Dict) -> Optional[Dict]:
        """Получение ML предсказания"""
        try:
            if 'price_predictor' not in self.ml_models:
                return None
            
            # Подготавливаем признаки
            features = self._prepare_ml_features(market_data)
            
            # Получаем предсказание
            prediction = await self.ml_models['price_predictor'].predict(
                symbol, features
            )
            
            return prediction
            
        except Exception as e:
            logger.debug(f"Ошибка ML предсказания для {symbol}: {e}")
            return None

    def _prepare_ml_features(self, market_data: Dict) -> Dict:
        """Подготовка признаков для ML"""
        try:
            df = market_data['df']
            indicators = market_data['indicators']
            
            # Ценовые признаки
            returns = df['close'].pct_change().fillna(0)
            volatility = returns.rolling(20).std()
            
            features = {
                # Базовые
                'price': market_data['current_price'],
                'volume': df['volume'].iloc[-1],
                'volume_score': market_data['volume_score'],
                
                # Технические индикаторы
                **indicators,
                
                # Статистические
                'return_1h': returns.iloc[-1],
                'return_24h': returns.tail(24).mean(),
                'volatility_20': volatility.iloc[-1] if not volatility.empty else 0,
                'price_position': (market_data['current_price'] - df['low'].tail(20).min()) / (df['high'].tail(20).max() - df['low'].tail(20).min()),
                
                # Рыночные
                'market_trend': 1 if self.market_state.overall_trend == 'BULLISH' else -1 if self.market_state.overall_trend == 'BEARISH' else 0,
                'market_volatility': 2 if self.market_state.volatility == 'HIGH' else 1 if self.market_state.volatility == 'MEDIUM' else 0,
            }
            
            return features
            
        except Exception as e:
            logger.debug(f"Ошибка подготовки признаков: {e}")
            return {}

    async def _get_news_sentiment(self, symbol: str) -> float:
        """Получение настроения новостей для символа"""
        try:
            if 'sentiment_analyzer' not in self.ml_models:
                return 0.0
            
            # Извлекаем базовый актив из символа
            base_asset = symbol.replace('USDT', '').replace('BUSD', '').replace('USDC', '')
            
            # Ищем новости в кэше
            relevant_news = []
            for news in self.news_cache:
                if any(keyword in news.get('title', '').lower() 
                      for keyword in [base_asset.lower(), 'crypto', 'bitcoin', 'ethereum']):
                    relevant_news.append(news)
            
            if not relevant_news:
                return 0.0
            
            # Анализируем настроение
            sentiment_scores = []
            for news in relevant_news[-10]:  # Последние 10 новостей
                score = await self.ml_models['sentiment_analyzer'].analyze(
                    news.get('title', '') + ' ' + news.get('content', '')
                )
                sentiment_scores.append(score)
            
            return np.mean(sentiment_scores) if sentiment_scores else 0.0
            
        except Exception as e:
            logger.debug(f"Ошибка анализа новостей для {symbol}: {e}")
            return 0.0

    async def _combine_signals(self, strategy_signals: List[TradingSignal], 
                             ml_prediction: Optional[Dict], 
                             news_sentiment: float) -> Optional[TradingSignal]:
        """Комбинирование всех сигналов в итоговый"""
        try:
            if not strategy_signals:
                return None
            
            # Разделяем сигналы по действиям
            buy_signals = [s for s in strategy_signals if s.action == 'BUY']
            sell_signals = [s for s in strategy_signals if s.action == 'SELL']
            
            # Определяем преобладающее направление
            if len(buy_signals) > len(sell_signals):
                dominant_signals = buy_signals
                action = 'BUY'
            elif len(sell_signals) > len(buy_signals):
                dominant_signals = sell_signals
                action = 'SELL'
            else:
                # Равное количество - выбираем по уверенности
                all_signals = buy_signals + sell_signals
                best_signal = max(all_signals, key=lambda x: x.confidence)
                dominant_signals = [best_signal]
                action = best_signal.action
            
            # Рассчитываем средние значения
            avg_confidence = np.mean([s.confidence for s in dominant_signals])
            avg_price = np.mean([s.price for s in dominant_signals])
            
            # Учитываем ML предсказание
            if ml_prediction and self.config['enable_ml_predictions']:
                ml_weight = self.config['ml_prediction_weight']
                ml_direction = ml_prediction.get('direction', 0)  # -1, 0, 1
                ml_confidence = ml_prediction.get('confidence', 0.5)
                
                # Корректируем уверенность на основе ML
                if (action == 'BUY' and ml_direction > 0) or (action == 'SELL' and ml_direction < 0):
                    avg_confidence = avg_confidence * (1 + ml_weight * ml_confidence)
                else:
                    avg_confidence = avg_confidence * (1 - ml_weight * ml_confidence)
            
            # Учитываем новостной фон
            if self.config['enable_news_analysis'] and abs(news_sentiment) > self.config['sentiment_threshold']:
                news_weight = self.config['news_impact_weight']
                
                if (action == 'BUY' and news_sentiment > 0) or (action == 'SELL' and news_sentiment < 0):
                    avg_confidence = avg_confidence * (1 + news_weight * abs(news_sentiment))
                else:
                    avg_confidence = avg_confidence * (1 - news_weight * abs(news_sentiment))
            
            # Ограничиваем уверенность
            avg_confidence = min(0.95, max(0.05, avg_confidence))
            
            # Рассчитываем стоп-лосс и тейк-профит
            atr = np.mean([s.indicators.get('atr', 0) for s in dominant_signals if s.indicators])
            if atr == 0:
                atr = avg_price * 0.02  # 2% как fallback
            
            if action == 'BUY':
                stop_loss = avg_price - (atr * self.config['stop_loss_atr_multiplier'])
                take_profit = avg_price + (atr * self.config['take_profit_atr_multiplier'])
            else:
                stop_loss = avg_price + (atr * self.config['stop_loss_atr_multiplier'])
                take_profit = avg_price - (atr * self.config['take_profit_atr_multiplier'])
            
            # Создаем комбинированный сигнал
            combined_signal = TradingSignal(
                action=action,
                confidence=avg_confidence,
                price=avg_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                reason=f"Combined({len(dominant_signals)} strategies, ML: {bool(ml_prediction)}, News: {news_sentiment:.2f})",
                risk_reward_ratio=abs(take_profit - avg_price) / abs(stop_loss - avg_price)
            )
            
            return combined_signal
            
        except Exception as e:
            logger.debug(f"Ошибка комбинирования сигналов: {e}")
            return None

    async def _rank_opportunities(self, opportunities: List[TradingOpportunity]) -> List[TradingOpportunity]:
        """Ранжирование торговых возможностей"""
        try:
            # Рассчитываем составной скор для каждой возможности
            for opp in opportunities:
                # Базовый скор
                score = opp.confidence * 0.4
                
                # Технический скор
                score += opp.technical_score * 0.25
                
                # Risk/Reward ratio
                if opp.signal.risk_reward_ratio and opp.signal.risk_reward_ratio > 0:
                    rr_score = min(1.0, opp.signal.risk_reward_ratio / 3.0)  # Нормализуем к 3.0
                    score += rr_score * 0.15
                
                # Объем
                score += opp.volume_score * 0.1
                
                # Настроение новостей
                if abs(opp.news_sentiment) > 0.1:
                    score += abs(opp.news_sentiment) * 0.05
                
                # Фаза рынка
                if opp.market_phase in [MarketPhase.MARKUP, MarketPhase.ACCUMULATION]:
                    score += 0.05
                
                opp.score = score
            
            # Сортируем по убыванию скора
            ranked = sorted(opportunities, key=lambda x: x.score, reverse=True)
            
            logger.info(f"🏆 Топ-5 возможностей:")
            for i, opp in enumerate(ranked[:5]):
                logger.info(f"  {i+1}. {opp.symbol}: {opp.score:.3f} ({opp.signal.action}, RR: {opp.signal.risk_reward_ratio:.2f})")
            
            return ranked
            
        except Exception as e:
            logger.error(f"❌ Ошибка ранжирования: {e}")
            return opportunities

    async def _manage_existing_positions(self):
        """Управление существующими позициями"""
        try:
            db = SessionLocal()
            
            # Получаем открытые позиции
            open_trades = db.query(Trade).filter(Trade.status == TradeStatus.OPEN).all()
            
            for trade in open_trades:
                try:
                    # Получаем текущую цену
                    ticker = await self.exchange.fetch_ticker(trade.symbol)
                    current_price = float(ticker['last'])
                    
                    # Рассчитываем текущую прибыль/убыток
                    if trade.side == OrderSide.BUY:
                        pnl_percent = (current_price - trade.entry_price) / trade.entry_price * 100
                    else:
                        pnl_percent = (trade.entry_price - current_price) / trade.entry_price * 100
                    
                    # Проверяем стоп-лосс
                    should_close_sl = False
                    if trade.stop_loss:
                        if trade.side == OrderSide.BUY and current_price <= trade.stop_loss:
                            should_close_sl = True
                        elif trade.side == OrderSide.SELL and current_price >= trade.stop_loss:
                            should_close_sl = True
                    
                    # Проверяем тейк-профит
                    should_close_tp = False
                    if trade.take_profit:
                        if trade.side == OrderSide.BUY and current_price >= trade.take_profit:
                            should_close_tp = True
                        elif trade.side == OrderSide.SELL and current_price <= trade.take_profit:
                            should_close_tp = True
                    
                    # Трейлинг стоп
                    if self.config['trailing_stop_enabled'] and pnl_percent > 2.0:
                        await self._update_trailing_stop(trade, current_price)
                    
                    # Закрываем позицию если нужно
                    if should_close_sl:
                        await self._close_position(trade, current_price, 'stop_loss')
                        logger.info(f"🛑 Закрыта позиция {trade.symbol} по стоп-лоссу: {pnl_percent:.2f}%")
                    elif should_close_tp:
                        await self._close_position(trade, current_price, 'take_profit')
                        logger.info(f"🎯 Закрыта позиция {trade.symbol} по тейк-профиту: {pnl_percent:.2f}%")
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка управления позицией {trade.symbol}: {e}")
                    continue
            
            db.close()
            
        except Exception as e:
            logger.error(f"❌ Ошибка управления позициями: {e}")

    async def _execute_new_trades(self, opportunities: List[TradingOpportunity]):
        """Выполнение новых сделок"""
        try:
            # Проверяем лимиты
            current_positions = len(self.positions)
            max_new_trades = min(
                self.config['max_positions'] - current_positions,
                self.config['max_daily_trades']  # TODO: учитывать дневной лимит
            )
            
            if max_new_trades <= 0:
                logger.info("⏸️ Лимиты позиций достигнуты")
                return
            
            # Выбираем лучшие возможности
            selected_opportunities = opportunities[:max_new_trades]
            
            for opp in selected_opportunities:
                try:
                    # Проверяем, не открыта ли уже позиция по этому символу
                    if opp.symbol in self.positions:
                        continue
                    
                    # Рассчитываем размер позиции
                    position_size = await self._calculate_position_size(opp)
                    
                    if position_size <= 0:
                        continue
                    
                    # Открываем позицию
                    success = await self._open_position(opp, position_size)
                    
                    if success:
                        logger.info(f"✅ Открыта позиция {opp.symbol}: {opp.signal.action}, размер: {position_size:.4f}")
                        
                        # Отправляем уведомление
                        if telegram_notifier.enabled:
                            await telegram_notifier.send_message(
                                f"🚀 <b>Новая сделка</b>\n"
                                f"📊 Пара: {opp.symbol}\n"
                                f"📈 Действие: {opp.signal.action}\n"
                                f"💰 Размер: {position_size:.4f}\n"
                                f"🎯 Уверенность: {opp.confidence:.1%}\n"
                                f"📋 Стратегия: {opp.strategy}"
                            )
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка открытия позиции {opp.symbol}: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"❌ Ошибка выполнения сделок: {e}")

    async def _calculate_position_size(self, opportunity: TradingOpportunity) -> float:
        """Расчет размера позиции с учетом риск-менеджмента"""
        try:
            # Получаем текущий баланс
            balance = await self.exchange.fetch_balance()
            usdt_balance = float(balance.get('USDT', {}).get('free', 0))
            
            if usdt_balance < 10:  # Минимальный баланс
                return 0
            
            # Базовый размер позиции
            base_position_size = usdt_balance * (self.config['position_size_percent'] / 100)
            
            # Корректировка на основе уверенности
            confidence_multiplier = opportunity.confidence
            
            # Корректировка на основе волатильности
            volatility_multiplier = 1.0
            if self.market_state.volatility == 'HIGH':
                volatility_multiplier = 0.7
            elif self.market_state.volatility == 'LOW':
                volatility_multiplier = 1.2
            
            # Корректировка на основе риска
            risk_multiplier = 1.0
            if opportunity.risk_level == 'high':
                risk_multiplier = 0.6
            elif opportunity.risk_level == 'low':
                risk_multiplier = 1.3
            
            # Итоговый размер
            final_size = base_position_size * confidence_multiplier * volatility_multiplier * risk_multiplier
            
            # Конвертируем в количество базового актива
            quantity = final_size / opportunity.signal.price
            
            # Проверяем минимальные лимиты биржи
            # TODO: получать из exchange.markets
            min_quantity = 0.001  # Примерное значение
            
            return max(min_quantity, quantity) if quantity >= min_quantity else 0
            
        except Exception as e:
            logger.error(f"❌ Ошибка расчета размера позиции: {e}")
            return 0

    async def _open_position(self, opportunity: TradingOpportunity, quantity: float) -> bool:
        """Открытие торговой позиции"""
        try:
            # Размещаем рыночный ордер
            order_type = 'market'
            side = 'buy' if opportunity.signal.action == 'BUY' else 'sell'
            
            order = await self.exchange.create_order(
                symbol=opportunity.symbol,
                type=order_type,
                side=side,
                amount=quantity,
                price=None  # Рыночная цена
            )
            
            if order and order.get('status') in ['closed', 'filled']:
                # Сохраняем сделку в базу данных
                db = SessionLocal()
                try:
                    trade = Trade(
                        symbol=opportunity.symbol,
                        side=OrderSide.BUY if side == 'buy' else OrderSide.SELL,
                        quantity=quantity,
                        entry_price=float(order.get('average', opportunity.signal.price)),
                        stop_loss=opportunity.signal.stop_loss,
                        take_profit=opportunity.signal.take_profit,
                        strategy=opportunity.strategy,
                        status=TradeStatus.OPEN,
                        confidence=opportunity.confidence,
                        created_at=datetime.utcnow()
                    )
                    
                    db.add(trade)
                    db.commit()
                    
                    # Добавляем в локальный кэш
                    self.positions[opportunity.symbol] = trade
                    
                    return True
                    
                finally:
                    db.close()
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Ошибка открытия позиции {opportunity.symbol}: {e}")
            return False

    async def _close_position(self, trade: Trade, current_price: float, reason: str):
        """Закрытие торговой позиции"""
        try:
            # Размещаем ордер на закрытие
            side = 'sell' if trade.side == OrderSide.BUY else 'buy'
            
            order = await self.exchange.create_order(
                symbol=trade.symbol,
                type='market',
                side=side,
                amount=trade.quantity,
                price=None
            )
            
            if order and order.get('status') in ['closed', 'filled']:
                # Обновляем сделку в базе данных
                db = SessionLocal()
                try:
                    exit_price = float(order.get('average', current_price))
                    
                    # Рассчитываем прибыль/убыток
                    if trade.side == OrderSide.BUY:
                        profit_percent = (exit_price - trade.entry_price) / trade.entry_price * 100
                        profit_usdt = (exit_price - trade.entry_price) * trade.quantity
                    else:
                        profit_percent = (trade.entry_price - exit_price) / trade.entry_price * 100
                        profit_usdt = (trade.entry_price - exit_price) * trade.quantity
                    
                    # Обновляем запись
                    trade.exit_price = exit_price
                    trade.profit = profit_usdt
                    trade.profit_percent = profit_percent
                    trade.status = TradeStatus.CLOSED
                    trade.exit_reason = reason
                    trade.closed_at = datetime.utcnow()
                    
                    db.commit()
                    
                    # Удаляем из локального кэша
                    if trade.symbol in self.positions:
                        del self.positions[trade.symbol]
                    
                    # Обновляем статистику стратегии
                    strategy_stats = self.strategy_performance[trade.strategy]
                    strategy_stats['total_trades'] += 1
                    strategy_stats['total_profit'] += profit_usdt
                    
                    if profit_usdt > 0:
                        strategy_stats['winning_trades'] += 1
                    
                    strategy_stats['win_rate'] = strategy_stats['winning_trades'] / strategy_stats['total_trades'] * 100
                    strategy_stats['avg_profit'] = strategy_stats['total_profit'] / strategy_stats['total_trades']
                    
                finally:
                    db.close()
            
        except Exception as e:
            logger.error(f"❌ Ошибка закрытия позиции {trade.symbol}: {e}")

    # Дополнительные методы мониторинга и машинного обучения...
    
    async def _market_monitoring_loop(self):
        """Цикл мониторинга рынка"""
        while self.is_running:
            try:
                await self._analyze_market_state()
                await self._update_trading_pairs()
                await asyncio.sleep(self.config['pair_update_interval'])
            except Exception as e:
                logger.error(f"❌ Ошибка мониторинга рынка: {e}")
                await asyncio.sleep(300)

    async def _ml_training_loop(self):
        """Цикл обучения ML моделей"""
        while self.is_running:
            try:
                if self.config['enable_ml_predictions']:
                    await self._retrain_ml_models()
                await asyncio.sleep(self.config['retrain_interval_hours'] * 3600)
            except Exception as e:
                logger.error(f"❌ Ошибка обучения ML: {e}")
                await asyncio.sleep(3600)

    async def _risk_monitoring_loop(self):
        """Цикл мониторинга рисков"""
        while self.is_running:
            try:
                await self._check_portfolio_risk()
                await self._check_correlation_risk()
                await self._check_drawdown_limits()
                await asyncio.sleep(self.config['health_check_interval'])
            except Exception as e:
                logger.error(f"❌ Ошибка мониторинга рисков: {e}")
                await asyncio.sleep(300)

    async def _news_monitoring_loop(self):
        """Цикл мониторинга новостей"""
        while self.is_running:
            try:
                if self.config['enable_news_analysis']:
                    await self._fetch_crypto_news()
                    await self._analyze_social_sentiment()
                await asyncio.sleep(1800)  # Каждые 30 минут
            except Exception as e:
                logger.error(f"❌ Ошибка мониторинга новостей: {e}")
                await asyncio.sleep(1800)

    # Дополнительные вспомогательные методы...
    
    def _assess_risk_level(self, market_data: Dict) -> str:
        """Оценка уровня риска"""
        # Простая логика оценки риска
        volatility = market_data.get('indicators', {}).get('atr', 0)
        volume_score = market_data.get('volume_score', 0.5)
        
        if volatility > 0.05 or volume_score < 0.3:
            return 'high'
        elif volatility < 0.02 and volume_score > 0.7:
            return 'low'
        else:
            return 'medium'

    def _determine_market_phase(self, market_data: Dict) -> MarketPhase:
        """Определение фазы рынка"""
        # Упрощенная логика определения фазы
        indicators = market_data.get('indicators', {})
        rsi = indicators.get('rsi', 50)
        volume_score = market_data.get('volume_score', 0.5)
        
        if rsi > 70 and volume_score > 0.8:
            return MarketPhase.DISTRIBUTION
        elif rsi < 30 and volume_score > 0.8:
            return MarketPhase.ACCUMULATION
        elif 30 <= rsi <= 70 and volume_score > 0.6:
            return MarketPhase.MARKUP if rsi > 50 else MarketPhase.MARKDOWN
        else:
            return MarketPhase.UNKNOWN

    async def get_status(self) -> Dict[str, Any]:
        """Получение полного статуса бота"""
        return {
            'is_running': self.is_running,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'total_cycles': self.total_cycles,
            'active_pairs': len(self.active_pairs),
            'all_pairs': len(self.all_trading_pairs),
            'open_positions': len(self.positions),
            'market_state': {
                'trend': self.market_state.overall_trend,
                'volatility': self.market_state.volatility,
                'active_coins': self.market_state.active_coins
            },
            'strategy_performance': dict(self.strategy_performance),
            'config': self.config
        }

    async def stop(self):
        """Остановка бота"""
        logger.info("🛑 Остановка усовершенствованного торгового бота...")
        self.is_running = False
        
        # Закрываем все открытые позиции (опционально)
        # await self._close_all_positions()

# Экспорт
__all__ = ['AdvancedTradingBot']