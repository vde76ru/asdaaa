"""
TRADING BOT INTEGRATION - Интеграция реальной торговли с основным ботом
Файл: src/bot/trading_integration.py

🎯 ПОЛНАЯ АВТОМАТИЗАЦИЯ ТОРГОВЛИ:
✅ Объединяет все компоненты: стратегии → исполнение → мониторинг
✅ Автоматический поиск торговых возможностей 24/7
✅ Интеллектуальный выбор стратегий для рыночных условий
✅ Управление несколькими позициями одновременно
✅ Экстренные остановки и безопасность
"""
import pandas as pd
import numpy as np
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging



from ..core.database import SessionLocal
try:
    from ..strategies.strategy_selector import get_strategy_selector
except ImportError:
    get_strategy_selector = None

try:
    from ..bot.signal_processor import SignalProcessor
except ImportError:
    SignalProcessor = None

try:
    from ..logging.smart_logger import get_logger
    logger = get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

try:
    from ..exchange.unified_exchange import get_real_exchange_client
except ImportError:
    get_real_exchange_client = None

try:
    from ..exchange.position_manager import get_position_manager
except ImportError:
    get_position_manager = None

try:
    from ..exchange.execution_engine import get_execution_engine
except ImportError:
    get_execution_engine = None

logger = get_logger(__name__)

class TradingBotWithRealTrading:
    """
    🔥 ОСНОВНОЙ ТОРГОВЫЙ БОТ С РЕАЛЬНОЙ ТОРГОВЛЕЙ
    
    Полная архитектура автоматизированной торговли:
    
    ┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
    │   СТРАТЕГИИ     │───▶│  РИСК-МЕНЕДЖМЕНТ │───▶│   ИСПОЛНЕНИЕ    │
    │   - Technical   │    │  - Position Size │    │   - Real Orders │
    │   - ML Models   │    │  - Correlation   │    │   - Stop/Loss   │
    │   - Market      │    │  - Drawdown      │    │   - Monitoring  │
    └─────────────────┘    └──────────────────┘    └─────────────────┘
             │                        │                        │
             ▼                        ▼                        ▼
    ┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
    │   DATA FEED     │    │   DATABASE       │    │   REPORTING     │
    │   - Price Data  │    │   - Trades       │    │   - Analytics   │
    │   - News/Social │    │   - Signals      │    │   - WebSocket   │
    │   - Sentiment   │    │   - Performance  │    │   - Telegram    │
    └─────────────────┘    └──────────────────┘    └─────────────────┘
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Инициализация торгового бота
        
        Args:
            config: Конфигурация бота
        """
        self.config = config
        
        # Компоненты торговой системы
        try:
            from ..exchange.unified_exchange import get_real_exchange_client
            self.exchange = get_real_exchange_client()
            logger.info("✅ Exchange клиент инициализирован")
        except ImportError as e:
            logger.error(f"❌ Ошибка импорта exchange клиента: {e}")
            self.exchange = None
        
        try:
            from ..exchange.execution_engine import get_execution_engine
            self.execution_engine = get_execution_engine()
            logger.info("✅ Execution Engine инициализирован")
        except ImportError as e:
            logger.error(f"❌ Ошибка импорта execution engine: {e}")
            self.execution_engine = None
        
        try:
            from ..exchange.position_manager import get_position_manager
            self.position_manager = get_position_manager()
            logger.info("✅ Position Manager инициализирован")
        except ImportError as e:
            logger.error(f"❌ Ошибка импорта position manager: {e}")
            self.position_manager = None
        
        try:
            from ..bot.signal_processor import SignalProcessor
            self.signal_processor = SignalProcessor()
            logger.info("✅ Signal Processor инициализирован")
        except ImportError as e:
            logger.warning(f"⚠️ Signal Processor недоступен: {e}")
            self.signal_processor = None
        
        # Инициализируем автоматический селектор стратегий
        self.strategy_selector = None
        try:
            from ..strategies.auto_strategy_selector import AutoStrategySelector
            self.strategy_selector = AutoStrategySelector()
            logger.info("✅ AutoStrategySelector инициализирован")
        except ImportError as e:
            logger.warning(f"⚠️ AutoStrategySelector недоступен: {e}")
            # Fallback на базовый селектор
            try:
                from ..strategies.strategy_selector import get_strategy_selector
                self.strategy_selector = get_strategy_selector()
                logger.info("✅ Базовый StrategySelector инициализирован")
            except ImportError as e2:
                logger.error(f"❌ Ни один селектор стратегий недоступен: {e2}")
                self.strategy_selector = None
        
        # Состояние бота
        self.is_running = False
        self.is_trading_enabled = config.get('trading_enabled', False)
        self.emergency_stop = False
        
        # Параметры торговли из конфигурации
        self.max_positions = config.get('max_positions', 5)
        self.risk_per_trade = config.get('risk_per_trade', 0.01)  # 1%
        self.analysis_interval = config.get('analysis_interval', 60)  # 60 секунд
        self.rebalance_interval = config.get('rebalance_interval', 300)  # 5 минут
        self.position_check_interval = config.get('position_check_interval_seconds', 30)
        
        # Торговые параметры
        self.trading_pairs = config.get('trading_pairs', ['BTCUSDT', 'ETHUSDT', 'ADAUSDT'])
        self.max_concurrent_trades = config.get('max_concurrent_trades', 3)
        
        # Статистика
        self.cycle_count = 0
        self.signals_generated = 0
        self.trades_executed = 0
        self.last_activity = datetime.utcnow()
        
        logger.info(
            "🚀 TradingBot с реальной торговлей инициализирован",
            category='bot',
            trading_enabled=self.is_trading_enabled,
            pairs_count=len(self.trading_pairs),
            analysis_interval=self.analysis_interval,
            max_positions=self.max_positions,
            risk_per_trade=f"{self.risk_per_trade*100}%"
        )
    
    # =================================================================
    # ОСНОВНЫЕ МЕТОДЫ БОТА
    # =================================================================
    
    async def start(self):
        """Запуск торгового бота"""
        if self.is_running:
            logger.warning("Бот уже запущен")
            return
        
        try:
            # Проверяем подключения
            await self._validate_connections()
            
            self.is_running = True
            
            logger.info(
                "🟢 Торговый бот запущен",
                category='bot',
                trading_enabled=self.is_trading_enabled
            )
            
            # Запускаем основные циклы
            tasks = [
                asyncio.create_task(self._main_trading_loop()),
                asyncio.create_task(self._position_monitoring_loop()),
                asyncio.create_task(self._health_check_loop())
            ]
            
            # Запускаем Position Manager если торговля включена
            if self.is_trading_enabled:
                tasks.append(asyncio.create_task(self.position_manager.start_monitoring()))
            
            # Ждем завершения всех задач
            await asyncio.gather(*tasks, return_exceptions=True)
            
        except Exception as e:
            logger.error(f"❌ Ошибка запуска бота: {e}")
            self.is_running = False
            raise
    
    async def stop(self):
        """Остановка торгового бота"""
        logger.info("⏹️ Остановка торгового бота", category='bot')
        
        self.is_running = False
        
        # Останавливаем Position Manager
        if hasattr(self.position_manager, 'stop_monitoring'):
            self.position_manager.stop_monitoring()
        
        logger.info("✅ Торговый бот остановлен", category='bot')
    
    async def emergency_stop_all(self):
        """Экстренная остановка всех операций"""
        logger.critical("🚨 ЭКСТРЕННАЯ ОСТАНОВКА ВСЕХ ОПЕРАЦИЙ", category='bot')
        
        self.emergency_stop = True
        self.is_trading_enabled = False
        
        # Активируем экстренную остановку в движке исполнения
        self.execution_engine.activate_emergency_stop("Bot emergency stop")
        
        # Закрываем все позиции
        try:
            closed_count = await self.execution_engine.close_all_positions_emergency()
            
            logger.critical(
                f"🚨 Экстренно закрыто позиций: {closed_count}",
                category='bot'
            )
            
        except Exception as e:
            logger.critical(f"🚨 ОШИБКА ЭКСТРЕННОГО ЗАКРЫТИЯ: {e}")
    
    # =================================================================
    # ОСНОВНЫЕ ЦИКЛЫ
    # =================================================================
    
    async def _main_trading_loop(self):
        """Основной торговый цикл с полной интеграцией"""
        logger.info("🔄 Запуск основного торгового цикла с автоматическим выбором стратегий")
        
        while self.is_running:
            try:
                loop_start = datetime.utcnow()
                self.cycle_count += 1
                
                logger.info(f"📊 Цикл #{self.cycle_count} - анализ {len(self.trading_pairs)} торговых пар")
                
                # Проверяем что все компоненты доступны
                if not self.exchange:
                    logger.error("❌ Exchange недоступен, пропускаем цикл")
                    await asyncio.sleep(60)
                    continue
                
                # 1. Обновляем рыночные данные для всех пар
                market_data = {}
                for symbol in self.trading_pairs:
                    try:
                        ticker = await self.exchange.get_ticker(symbol)
                        if ticker and ticker.get('last'):
                            market_data[symbol] = {
                                'price': ticker.get('last', 0),
                                'volume': ticker.get('quoteVolume', 0),
                                'change': ticker.get('percentage', 0),
                                'symbol': symbol,
                                'bid': ticker.get('bid', 0),
                                'ask': ticker.get('ask', 0)
                            }
                            logger.debug(f"📈 {symbol}: ${ticker.get('last', 0):.4f}")
                        else:
                            logger.warning(f"⚠️ Нет данных тикера для {symbol}")
                            
                    except Exception as e:
                        logger.warning(f"⚠️ Ошибка получения данных для {symbol}: {e}")
                        continue
                
                if not market_data:
                    logger.warning("⚠️ Нет рыночных данных, пропускаем цикл")
                    await asyncio.sleep(30)
                    continue
                
                logger.info(f"📊 Получены данные для {len(market_data)} торговых пар")
                
                # 2. Автоматический выбор стратегий для каждой пары
                strategy_selections = {}
                if self.strategy_selector:
                    try:
                        logger.info("🎯 Автоматический выбор стратегий...")
                        for symbol in market_data.keys():
                            strategy, confidence = await self.strategy_selector.select_best_strategy(symbol)
                            strategy_selections[symbol] = {
                                'strategy': strategy,
                                'confidence': confidence
                            }
                            logger.info(f"🎯 {symbol}: {strategy} (уверенность: {confidence:.2f})")
                            
                    except Exception as e:
                        logger.error(f"❌ Ошибка выбора стратегий: {e}")
                        # Используем дефолтную стратегию для всех пар
                        for symbol in market_data.keys():
                            strategy_selections[symbol] = {
                                'strategy': 'safe_multi_indicator',
                                'confidence': 0.5
                            }
                else:
                    logger.warning("⚠️ Strategy Selector недоступен, используем дефолтную стратегию")
                    for symbol in market_data.keys():
                        strategy_selections[symbol] = {
                            'strategy': 'safe_multi_indicator', 
                            'confidence': 0.5
                        }
                
                # 3. Генерируем сигналы для каждой пары
                signals = {}
                for symbol, data in market_data.items():
                    try:
                        strategy_info = strategy_selections.get(symbol, {'strategy': 'safe_multi_indicator', 'confidence': 0.5})
                        strategy_name = strategy_info['strategy']
                        
                        # Получаем исторические данные для анализа
                        historical_data = await self.exchange.get_historical_data(symbol, '5m', 100)
                        if historical_data is not None and len(historical_data) >= 20:
                            # Генерируем сигнал с выбранной стратегией
                            signal = await self._generate_trading_signal(symbol, historical_data, strategy_name)
                            if signal and signal.action in ['BUY', 'SELL']:
                                signals[symbol] = {
                                    'signal': signal,
                                    'strategy': strategy_name,
                                    'confidence': strategy_info['confidence'],
                                    'market_data': data
                                }
                                logger.info(f"🔔 {symbol}: {signal.action} по стратегии {strategy_name} "
                                           f"(conf: {signal.confidence:.2f}, цена: ${signal.price:.4f})")
                        else:
                            logger.debug(f"ℹ️ Недостаточно исторических данных для {symbol}")
                            
                    except Exception as e:
                        logger.error(f"❌ Ошибка генерации сигнала для {symbol}: {e}")
                        import traceback
                        traceback.print_exc()
                        continue
                
                logger.info(f"🔔 Сгенерировано сигналов: {len(signals)}")
                
                # 4. Обрабатываем сигналы и открываем сделки
                if signals and self.is_trading_enabled and not self.emergency_stop:
                    executed_trades = 0
                    for symbol, signal_info in signals.items():
                        try:
                            signal = signal_info['signal']
                            strategy = signal_info['strategy']
                            
                            # Проверяем риск-менеджмент
                            if await self._validate_risk_management(symbol, signal):
                                # Выполняем сделку
                                success = await self._execute_trade(symbol, signal, strategy)
                                if success:
                                    executed_trades += 1
                                    self.trades_executed += 1
                                    logger.info(f"✅ Сделка выполнена: {symbol} {signal.action}")
                                else:
                                    logger.warning(f"⚠️ Не удалось выполнить сделку {symbol}")
                            else:
                                logger.warning(f"⚠️ Сделка {symbol} отклонена риск-менеджментом")
                        
                        except Exception as e:
                            logger.error(f"❌ Ошибка выполнения сделки {symbol}: {e}")
                            continue
                    
                    if executed_trades > 0:
                        logger.info(f"📈 Выполнено сделок в цикле: {executed_trades}")
                elif self.emergency_stop:
                    logger.warning("🚨 Экстренная остановка активна - торговля приостановлена")
                elif not self.is_trading_enabled:
                    logger.debug("ℹ️ Торговля отключена")
                
                # 5. Мониторинг существующих позиций
                try:
                    await self._monitor_existing_positions()
                except Exception as e:
                    logger.error(f"❌ Ошибка мониторинга позиций: {e}")
                
                # 6. Обновляем статистику
                self.last_activity = datetime.utcnow()
                self.signals_generated += len(signals)
                
                # 7. Логируем статистику цикла
                cycle_duration = (datetime.utcnow() - loop_start).total_seconds()
                logger.info(f"⏱️ Цикл #{self.cycle_count} завершен за {cycle_duration:.1f}с, "
                           f"сигналов: {len(signals)}, всего сделок: {self.trades_executed}")
                
                # Пауза между циклами
                await asyncio.sleep(self.analysis_interval)
                
            except Exception as e:
                logger.error(f"❌ Критическая ошибка в основном цикле: {e}")
                import traceback
                traceback.print_exc()
                await asyncio.sleep(60)  # Пауза при ошибке

    
    async def _trading_cycle(self):
        """Один цикл анализа и торговли"""
        start_time = datetime.utcnow()
        self.cycle_count += 1
        
        try:
            # 1. Анализ рынка для всех пар
            market_analysis_results = {}
            
            for symbol in self.trading_pairs:
                try:
                    analysis = await self._analyze_market_for_symbol(symbol)
                    market_analysis_results[symbol] = analysis
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка анализа {symbol}: {e}")
                    continue
            
            # 2. Генерация сигналов
            trading_signals = []
            
            for symbol, analysis in market_analysis_results.items():
                try:
                    signals = await self._generate_signals_for_symbol(symbol, analysis)
                    trading_signals.extend(signals)
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка генерации сигналов {symbol}: {e}")
                    continue
            
            # 3. Обработка и исполнение сигналов
            if trading_signals and self.is_trading_enabled:
                await self._process_trading_signals(trading_signals)
            
            # 4. Обновление статистики
            cycle_time = (datetime.utcnow() - start_time).total_seconds()
            self.last_activity = datetime.utcnow()
            
            logger.debug(
                f"✅ Торговый цикл завершен",
                category='bot',
                cycle_count=self.cycle_count,
                cycle_time=cycle_time,
                symbols_analyzed=len(market_analysis_results),
                signals_generated=len(trading_signals)
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка в торговом цикле: {e}")
    
    async def _position_monitoring_loop(self):
        """Цикл мониторинга позиций"""
        logger.info("👁️ Запуск цикла мониторинга позиций", category='bot')
        
        while self.is_running:
            try:
                if not self.emergency_stop:
                    await self._check_positions_health()
                
                await asyncio.sleep(self.position_check_interval)
                
            except Exception as e:
                logger.error(f"❌ Ошибка мониторинга позиций: {e}")
                await asyncio.sleep(5)
    
    async def _health_check_loop(self):
        """Цикл проверки здоровья системы"""
        while self.is_running:
            try:
                await self._system_health_check()
                await asyncio.sleep(300)  # Каждые 5 минут
                
            except Exception as e:
                logger.error(f"❌ Ошибка проверки здоровья: {e}")
                await asyncio.sleep(60)
    
    # =================================================================
    # МЕТОДЫ АНАЛИЗА И ТОРГОВЛИ
    # =================================================================
    
    async def _analyze_market_for_symbol(self, symbol: str) -> Dict[str, Any]:
        """Анализ рынка для конкретного символа"""
        try:
            # Получаем рыночные данные
            candles = await self.exchange.get_candles(symbol, '5m', limit=200)
            ticker = await self.exchange.fetch_ticker(symbol)
            order_book = await self.exchange.fetch_order_book(symbol)
            
            # Текущие условия рынка
            market_conditions = {
                'symbol': symbol,
                'current_price': ticker['last'],
                'volume_24h': ticker['quoteVolume'],
                'price_change_24h': ticker['percentage'],
                'bid_ask_spread': (ticker['ask'] - ticker['bid']) / ticker['last'] * 100,
                'candles': candles,
                'order_book': order_book,
                'timestamp': datetime.utcnow()
            }
            
            return market_conditions
            
        except Exception as e:
            logger.error(f"❌ Ошибка анализа рынка {symbol}: {e}")
            return {}
    
    async def _generate_signals_for_symbol(self, symbol: str, 
                                         market_analysis: Dict[str, Any]) -> List:
        """Генерация торговых сигналов для символа"""
        try:
            if not market_analysis:
                return []
            
            # Получаем оптимальную стратегию
            recommended_strategy = await self.strategy_selector.select_optimal_strategy(
                symbol=symbol,
                market_conditions=market_analysis
            )
            
            if not recommended_strategy:
                return []
            
            strategy_name = recommended_strategy['strategy']
            strategy = self.strategy_selector.get_strategy(strategy_name)
            
            if not strategy:
                return []
            
            # Генерируем сигнал
            signal = await strategy.analyze(market_analysis['candles'])
            
            if signal and signal.action != 'HOLD':
                self.signals_generated += 1
                
                logger.info(
                    f"📈 Сигнал сгенерирован",
                    category='bot',
                    symbol=symbol,
                    action=signal.action,
                    strategy=strategy_name,
                    confidence=recommended_strategy.get('confidence', 0),
                    price=signal.price
                )
                
                return [{
                    'signal': signal,
                    'strategy_name': strategy_name,
                    'confidence': recommended_strategy.get('confidence', 0),
                    'market_conditions': market_analysis
                }]
            
            return []
            
        except Exception as e:
            logger.error(f"❌ Ошибка генерации сигналов {symbol}: {e}")
            return []
    
    async def _process_trading_signals(self, signals: List[Dict]) -> None:
        """Обработка торговых сигналов"""
        try:
            # Проверяем лимит одновременных сделок
            current_positions = await self.position_manager.get_positions_summary()
            active_trades = current_positions['total_positions']
            
            if active_trades >= self.max_concurrent_trades:
                logger.info(
                    f"⚠️ Лимит одновременных сделок достигнут: {active_trades}/{self.max_concurrent_trades}",
                    category='bot'
                )
                return
            
            # Сортируем сигналы по уверенности
            signals.sort(key=lambda x: x['confidence'], reverse=True)
            
            # Исполняем сигналы
            executed_count = 0
            
            for signal_data in signals:
                if executed_count >= (self.max_concurrent_trades - active_trades):
                    break
                
                try:
                    # Исполняем через Execution Engine
                    result = await self.execution_engine.execute_signal(
                        signal=signal_data['signal'],
                        strategy_name=signal_data['strategy_name'],
                        confidence=signal_data['confidence'],
                        market_conditions=signal_data['market_conditions']
                    )
                    
                    if result.status.value == 'completed':
                        executed_count += 1
                        self.trades_executed += 1
                        
                        logger.info(
                            f"✅ Сделка исполнена",
                            category='bot',
                            symbol=signal_data['signal'].symbol,
                            trade_id=result.trade_id,
                            order_id=result.order_id
                        )
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка исполнения сигнала: {e}")
            
            if executed_count > 0:
                logger.info(
                    f"📊 Исполнено сделок в цикле: {executed_count}",
                    category='bot'
                )
                
        except Exception as e:
            logger.error(f"❌ Ошибка обработки сигналов: {e}")
    
    async def _check_positions_health(self):
        """Проверка здоровья позиций"""
        try:
            positions_summary = await self.position_manager.get_positions_summary()
            
            if positions_summary['total_positions'] > 0:
                total_pnl = positions_summary['total_pnl']
                total_pnl_percent = positions_summary['total_pnl_percent']
                
                # Проверяем критические условия
                if total_pnl_percent < -10:  # -10% общий PnL
                    logger.warning(
                        f"⚠️ Критический PnL: {total_pnl_percent:.1f}%",
                        category='bot',
                        total_pnl=total_pnl
                    )
                
                # Логируем статус позиций
                logger.debug(
                    f"📊 Позиции: {positions_summary['total_positions']} | PnL: {total_pnl:.2f} USDT ({total_pnl_percent:.1f}%)",
                    category='bot'
                )
                
        except Exception as e:
            logger.error(f"❌ Ошибка проверки позиций: {e}")
    
    async def _system_health_check(self):
        """Проверка здоровья системы"""
        try:
            # Проверяем подключение к бирже
            if not self.exchange.is_connected:
                logger.error("❌ Потеряно подключение к бирже", category='bot')
                return
            
            # Проверяем статистику исполнений
            exec_stats = self.execution_engine.get_execution_stats()
            success_rate = exec_stats['success_rate_percent']
            
            if success_rate < 80 and exec_stats['total_executions'] > 10:
                logger.warning(
                    f"⚠️ Низкий успех исполнений: {success_rate:.1f}%",
                    category='bot'
                )
            
            # Проверяем активность
            time_since_activity = (datetime.utcnow() - self.last_activity).total_seconds()
            if time_since_activity > 600:  # 10 минут без активности
                logger.warning(
                    f"⚠️ Нет активности {time_since_activity:.0f} секунд",
                    category='bot'
                )
            
            logger.debug(
                "💓 Проверка здоровья системы пройдена",
                category='bot',
                cycles=self.cycle_count,
                signals=self.signals_generated,
                trades=self.trades_executed
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка проверки здоровья: {e}")
    
    # =================================================================
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # =================================================================
    
    async def _validate_connections(self):
        """Валидация всех подключений"""
        try:
            # Проверяем подключение к бирже
            if not self.exchange.is_connected:
                raise Exception("Нет подключения к бирже")
            
            # Проверяем баланс
            balance = await self.exchange.fetch_balance()
            usdt_balance = balance.get('USDT', {}).get('free', 0)
            
            if usdt_balance < 10:
                logger.warning(
                    f"⚠️ Низкий баланс: {usdt_balance:.2f} USDT",
                    category='bot'
                )
            
            logger.info(
                "✅ Все подключения проверены",
                category='bot',
                balance_usdt=usdt_balance
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка валидации подключений: {e}")
            raise
    
    def get_bot_status(self) -> Dict[str, Any]:
        """Получение статуса бота"""
        exec_stats = self.execution_engine.get_execution_stats()
        
        return {
            'is_running': self.is_running,
            'is_trading_enabled': self.is_trading_enabled,
            'emergency_stop': self.emergency_stop,
            'cycle_count': self.cycle_count,
            'signals_generated': self.signals_generated,
            'trades_executed': self.trades_executed,
            'last_activity': self.last_activity,
            'trading_pairs_count': len(self.trading_pairs),
            'execution_stats': exec_stats
        }
    
    def enable_trading(self):
        """Включение торговли"""
        self.is_trading_enabled = True
        self.execution_engine.deactivate_emergency_stop()
        
        logger.info("✅ Торговля включена", category='bot')
        
    async def _generate_trading_signal(self, symbol: str, historical_data, strategy_name: str):
        """Генерация торгового сигнала с указанной стратегией"""
        try:
            # Импортируем стратегию динамически
            strategy = None
            
            if strategy_name == 'momentum':
                try:
                    from ..strategies.momentum import MomentumStrategy
                    strategy = MomentumStrategy()
                except ImportError:
                    logger.warning(f"⚠️ MomentumStrategy недоступна для {symbol}")
                    
            elif strategy_name == 'scalping':
                try:
                    from ..strategies.scalping import ScalpingStrategy  
                    strategy = ScalpingStrategy()
                except ImportError:
                    logger.warning(f"⚠️ ScalpingStrategy недоступна для {symbol}")
                    
            elif strategy_name == 'safe_multi_indicator':
                try:
                    from ..strategies.safe_multi_indicator import SafeMultiIndicatorStrategy
                    strategy = SafeMultiIndicatorStrategy()
                except ImportError:
                    logger.warning(f"⚠️ SafeMultiIndicatorStrategy недоступна для {symbol}")
                    
            elif strategy_name == 'multi_indicator':
                try:
                    from ..strategies.multi_indicator import MultiIndicatorStrategy
                    strategy = MultiIndicatorStrategy()
                except ImportError:
                    logger.warning(f"⚠️ MultiIndicatorStrategy недоступна для {symbol}")
            
            # Если конкретная стратегия недоступна, пробуем дефолтную
            if not strategy:
                try:
                    from ..strategies.multi_indicator import MultiIndicatorStrategy
                    strategy = MultiIndicatorStrategy()
                    logger.info(f"ℹ️ Используем дефолтную MultiIndicatorStrategy для {symbol}")
                except ImportError:
                    logger.error(f"❌ Ни одна стратегия недоступна для {symbol}")
                    return None
            
            # Генерируем сигнал
            if hasattr(strategy, 'generate_signal'):
                signal = await strategy.generate_signal(historical_data, symbol)
            elif hasattr(strategy, 'analyze'):
                signal = await strategy.analyze(historical_data, symbol)
            else:
                logger.error(f"❌ Стратегия {strategy_name} не имеет метода generate_signal или analyze")
                return None
                
            return signal
            
        except Exception as e:
            logger.error(f"❌ Ошибка генерации сигнала {strategy_name} для {symbol}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def _validate_risk_management(self, symbol: str, signal) -> bool:
        """Валидация риск-менеджмента для сигнала"""
        try:
            # Проверяем текущий баланс
            balance = await self.exchange_client.get_balance('USDT')
            if balance < 10:  # Минимум $10
                logger.warning("⚠️ Недостаточно средств для торговли")
                return False
            
            # Проверяем количество открытых позиций
            open_positions = await self.position_manager.get_open_positions()
            if len(open_positions) >= self.max_positions:
                logger.warning(f"⚠️ Достигнут лимит позиций: {len(open_positions)}/{self.max_positions}")
                return False
            
            # Проверяем есть ли уже позиция по этому символу
            for pos in open_positions:
                if pos.get('symbol') == symbol:
                    logger.debug(f"ℹ️ Позиция по {symbol} уже открыта")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка валидации риск-менеджмента: {e}")
            return False
    
    async def _execute_trade(self, symbol: str, signal, strategy: str) -> bool:
        """Выполнение торговой сделки"""
        try:
            # Получаем текущий баланс
            try:
                balance_data = await self.exchange.get_balance()
                usdt_balance = balance_data.get('USDT', {}).get('free', 0)
            except Exception as e:
                logger.error(f"❌ Ошибка получения баланса для торговли: {e}")
                return False
            
            # Рассчитываем размер позиции
            position_size_usdt = usdt_balance * self.risk_per_trade
            
            # Минимальный размер позиции
            if position_size_usdt < 10:
                position_size_usdt = 10
            
            # Максимальный размер позиции (защита)
            max_position_size = usdt_balance * 0.1  # Максимум 10% от баланса
            if position_size_usdt > max_position_size:
                position_size_usdt = max_position_size
            
            logger.info(f"💰 Размер позиции для {symbol}: ${position_size_usdt:.2f} USDT")
            
            # Выполняем сделку через execution engine
            if self.execution_engine:
                try:
                    result = await self.execution_engine.execute_signal(
                        symbol=symbol,
                        signal=signal,
                        position_size_usdt=position_size_usdt,
                        strategy=strategy
                    )
                    
                    if isinstance(result, dict):
                        return result.get('success', False)
                    else:
                        # Если execution_engine возвращает объект с атрибутами
                        return hasattr(result, 'status') and str(result.status) == 'completed'
                        
                except Exception as e:
                    logger.error(f"❌ Ошибка выполнения через execution engine: {e}")
                    return False
            else:
                # Fallback - выполняем напрямую через exchange
                logger.warning("⚠️ Execution Engine недоступен, выполняем через exchange")
                try:
                    # Получаем текущую цену
                    ticker = await self.exchange.get_ticker(symbol)
                    if not ticker:
                        logger.error(f"❌ Нет данных тикера для {symbol}")
                        return False
                    
                    current_price = ticker.get('last', 0)
                    if current_price <= 0:
                        logger.error(f"❌ Некорректная цена для {symbol}: {current_price}")
                        return False
                    
                    # Рассчитываем количество
                    quantity = position_size_usdt / current_price
                    
                    # Размещаем ордер
                    order_result = await self.exchange.place_order(
                        symbol=symbol,
                        side=signal.action.lower(),  # 'buy' или 'sell'
                        amount=quantity,
                        order_type='market'
                    )
                    
                    if order_result and not order_result.get('error'):
                        logger.info(f"✅ Ордер размещен: {symbol} {signal.action} {quantity:.6f}")
                        return True
                    else:
                        logger.error(f"❌ Ошибка размещения ордера: {order_result}")
                        return False
                        
                except Exception as e:
                    logger.error(f"❌ Ошибка выполнения напрямую через exchange: {e}")
                    return False
            
        except Exception as e:
            logger.error(f"❌ Критическая ошибка выполнения сделки {symbol}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def _monitor_existing_positions(self):
        """Мониторинг существующих позиций"""
        try:
            if not self.position_manager:
                logger.debug("ℹ️ Position Manager недоступен для мониторинга")
                return
            
            open_positions = await self.position_manager.get_open_positions()
            
            # Проверяем формат ответа
            if not open_positions:
                logger.debug("ℹ️ Нет открытых позиций")
                return
            
            # Преобразуем в список если нужно
            if isinstance(open_positions, dict):
                positions_list = open_positions.get('positions', [])
            else:
                positions_list = open_positions if isinstance(open_positions, list) else []
            
            if not positions_list:
                logger.debug("ℹ️ Список позиций пуст")
                return
            
            logger.debug(f"📊 Мониторинг {len(positions_list)} позиций")
            
            for position in positions_list:
                try:
                    if not isinstance(position, dict):
                        continue
                        
                    symbol = position.get('symbol')
                    entry_price = position.get('entry_price', 0)
                    current_price = position.get('current_price', 0)
                    side = position.get('side', 'BUY')
                    
                    if not symbol or not entry_price:
                        continue
                    
                    # Получаем текущую цену если её нет
                    if not current_price:
                        try:
                            ticker = await self.exchange.get_ticker(symbol)
                            current_price = ticker.get('last', 0) if ticker else 0
                        except Exception:
                            continue
                    
                    if current_price and entry_price:
                        # Рассчитываем P&L
                        if side.upper() == 'BUY':
                            pnl_percent = ((current_price - entry_price) / entry_price) * 100
                        else:
                            pnl_percent = ((entry_price - current_price) / entry_price) * 100
                        
                        logger.debug(f"📊 {symbol}: {side} P&L: {pnl_percent:.2f}%")
                        
                        # Проверяем условия закрытия
                        await self._check_position_exit_conditions(position, pnl_percent)
                        
                except Exception as e:
                    logger.error(f"❌ Ошибка мониторинга позиции: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"❌ Ошибка мониторинга позиций: {e}")
    
    async def _check_position_exit_conditions(self, position: dict, pnl_percent: float):
        """Проверка условий выхода из позиции"""
        try:
            symbol = position.get('symbol')
            
            if not symbol:
                return
            
            # Стоп-лосс
            if pnl_percent <= -2.0:  # -2%
                logger.warning(f"🛑 Стоп-лосс для {symbol}: {pnl_percent:.2f}%")
                try:
                    if self.position_manager:
                        await self.position_manager.close_position(symbol, reason="stop_loss")
                        logger.info(f"✅ Позиция {symbol} закрыта по стоп-лоссу")
                    else:
                        logger.warning("⚠️ Position Manager недоступен для закрытия по стоп-лоссу")
                except Exception as e:
                    logger.error(f"❌ Ошибка закрытия по стоп-лоссу {symbol}: {e}")
            
            # Тейк-профит
            elif pnl_percent >= 4.0:  # +4%
                logger.info(f"🎯 Тейк-профит для {symbol}: {pnl_percent:.2f}%")
                try:
                    if self.position_manager:
                        await self.position_manager.close_position(symbol, reason="take_profit")
                        logger.info(f"✅ Позиция {symbol} закрыта по тейк-профиту")
                    else:
                        logger.warning("⚠️ Position Manager недоступен для закрытия по тейк-профиту")
                except Exception as e:
                    logger.error(f"❌ Ошибка закрытия по тейк-профиту {symbol}: {e}")
            
            # Частичное закрытие при хорошей прибыли
            elif pnl_percent >= 6.0:  # +6%
                logger.info(f"💰 Частичное закрытие для {symbol}: {pnl_percent:.2f}%")
                try:
                    if self.position_manager and hasattr(self.position_manager, 'partial_close_position'):
                        await self.position_manager.partial_close_position(
                            symbol, 
                            percentage=50,  # Закрываем 50% позиции
                            reason="partial_profit"
                        )
                        logger.info(f"✅ 50% позиции {symbol} закрыто частично")
                except Exception as e:
                    logger.error(f"❌ Ошибка частичного закрытия {symbol}: {e}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка проверки условий выхода: {e}")
    
    def disable_trading(self):
        """Отключение торговли"""
        self.is_trading_enabled = False
        
        logger.info("⏸️ Торговля отключена", category='bot')

# =================================================================
# ГЛОБАЛЬНЫЕ ФУНКЦИИ
# =================================================================

# Глобальный экземпляр
trading_bot = None

def get_trading_bot(config: Optional[Dict] = None) -> TradingBotWithRealTrading:
    """Получить глобальный экземпляр торгового бота"""
    global trading_bot
    
    if trading_bot is None and config:
        trading_bot = TradingBotWithRealTrading(config)
    
    return trading_bot

def create_trading_bot(config: Dict[str, Any]) -> TradingBotWithRealTrading:
    """Создать новый экземпляр торгового бота"""
    return TradingBotWithRealTrading(config)

# Экспорты
__all__ = [
    'TradingBotWithRealTrading',
    'get_trading_bot',
    'create_trading_bot'
]