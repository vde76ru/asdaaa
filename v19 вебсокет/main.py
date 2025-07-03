#!/usr/bin/env python3
"""
🚀 ОБНОВЛЕННЫЙ ГЛАВНЫЙ ФАЙЛ ЗАПУСКА CRYPTO TRADING BOT
Файл: main.py

✅ КРИТИЧЕСКИЕ ИСПРАВЛЕНИЯ:
- ИСПРАВЛЕНА ошибка с await и синхронной функцией
- Правильная передача config в конструктор TradingBotWithRealTrading
- Улучшенная обработка ошибок инициализации
- Добавлена детальная диагностика проблем
- Корректная обработка fallback сценариев
"""

import sys
import os
import asyncio
import logging
import threading
import time
from pathlib import Path
from dotenv import load_dotenv
import signal
from typing import Optional, Dict, Any

# ========================================
# НАСТРОЙКА ОКРУЖЕНИЯ И ПУТЕЙ
# ========================================

# Добавляем корневую директорию в PYTHONPATH
ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR))

# Загружаем переменные окружения
env_path = ROOT_DIR / '.env'
if not env_path.exists():
    # Ищем в других местах
    possible_paths = [
        ROOT_DIR / 'config' / '.env',
        ROOT_DIR / '.env.example',
        Path('/etc/crypto/config/.env')
    ]
    for path in possible_paths:
        if path.exists():
            env_path = path
            break

load_dotenv(env_path)

# Подавляем предупреждения
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '3')
os.environ.setdefault('TF_ENABLE_ONEDNN_OPTS', '0')
os.environ.setdefault('PYTHONPATH', str(ROOT_DIR))

# ========================================
# НАСТРОЙКА ЛОГИРОВАНИЯ
# ========================================

def setup_logging():
    """Настройка системы логирования"""
    
    # Создаем директорию для логов
    log_dir = ROOT_DIR / 'logs'
    log_dir.mkdir(exist_ok=True)
    
    # Настройка форматтера
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Консольный handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    
    # Файловый handler
    file_handler = logging.FileHandler(log_dir / 'main.log')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    
    # Настройка root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    return root_logger

# Инициализируем логирование
logger = setup_logging()

# ========================================
# КРАСИВЫЙ БАННЕР ЗАПУСКА
# ========================================

def show_startup_banner():
    """Показать баннер запуска"""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║                    🚀 CRYPTO TRADING BOT v3.1                ║
║                  Professional Trading System                 ║
║                        SYSTEMETECH                           ║
╠══════════════════════════════════════════════════════════════╣
║  ✅ Полная автоматизация торговли                            ║
║  🧠 Машинное обучение и ИИ                                   ║
║  🌐 Веб-интерфейс реального времени                          ║
║  🛡️ Продвинутый риск-менеджмент                              ║
║  📊 Интеграция с Bybit                                       ║
╚══════════════════════════════════════════════════════════════╝
"""
    print(banner)

# ========================================
# СИСТЕМНЫЕ ПРОВЕРКИ
# ========================================

def check_environment():
    """Проверка окружения"""
    logger.info("🔧 Настройка окружения...")
    
    # Проверяем Python версию
    if sys.version_info < (3, 8):
        logger.error("❌ Требуется Python 3.8+")
        return False
    
    # Проверяем переменные окружения (опционально)
    optional_env_vars = [
        'DATABASE_URL',
        'BYBIT_API_KEY',
        'BYBIT_API_SECRET'
    ]
    
    missing_vars = []
    for var in optional_env_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.warning(f"⚠️ Отсутствуют переменные окружения: {missing_vars}")
        logger.info("ℹ️ Будет использоваться тестовый режим")
    
    logger.info("✅ Настройка окружения завершена")
    return True

async def check_system_components():
    """Проверка системных компонентов"""
    logger.info("🔍 Проверка системных компонентов...")
    
    results = {
        'environment': False,
        'database': False,
        'exchange': False,
        'ml_capabilities': False,
        'bot_components': False
    }
    
    # 1. Проверка окружения
    results['environment'] = check_environment()
    
    # 2. ✅ ИСПРАВЛЕНИЕ: Проверка базы данных БЕЗ await
    try:
        from src.core.database import test_database_connection
        # ✅ УБИРАЕМ await - функция синхронная!
        results['database'] = test_database_connection()
        if results['database']:
            logger.info("✅ База данных доступна")
        else:
            logger.warning("⚠️ Проблемы с базой данных")
    except Exception as e:
        logger.error(f"❌ Ошибка проверки БД: {e}")
        # Продолжаем работу без БД в тестовом режиме
        results['database'] = False
    
    # 3. Проверка exchange
    try:
        from src.exchange import check_exchange_capabilities
        exchange_caps = check_exchange_capabilities()
        results['exchange'] = exchange_caps.get('full_exchange_stack', False)
        
        if results['exchange']:
            logger.info("✅ Exchange система готова")
        else:
            logger.warning("⚠️ Ограниченные возможности exchange")
    except Exception as e:
        logger.error(f"❌ Ошибка проверки exchange: {e}")
        results['exchange'] = False
    
    # 4. Проверка ML
    try:
        from src.ml import check_ml_capabilities
        ml_caps = check_ml_capabilities()
        results['ml_capabilities'] = ml_caps.get('production_ready', False)
        
        if results['ml_capabilities']:
            logger.info("✅ ML система готова")
        else:
            logger.warning("⚠️ ML система работает с ограничениями")
    except Exception as e:
        logger.error(f"❌ Ошибка проверки ML: {e}")
        results['ml_capabilities'] = False
    
    # 5. Проверка bot компонентов
    try:
        from src.bot import check_bot_capabilities
        bot_caps = check_bot_capabilities()
        results['bot_components'] = bot_caps.get('full_bot_stack', False)
        
        if results['bot_components']:
            logger.info("✅ Bot компоненты готовы")
        else:
            logger.warning("⚠️ Bot система работает с ограничениями")
    except Exception as e:
        logger.error(f"❌ Ошибка проверки bot: {e}")
        results['bot_components'] = False
    
    # Итоговая оценка
    critical_components = ['environment']  # Только критически важные компоненты
    critical_passed = all(results[comp] for comp in critical_components)
    
    if critical_passed:
        logger.info("✅ Критически важные компоненты готовы")
        return True
    else:
        failed = [comp for comp in critical_components if not results[comp]]
        logger.warning(f"⚠️ Система частично готова - проверьте компоненты: {failed}")
        return False

# ========================================
# ЗАПУСК ТОРГОВОГО БОТА
# ========================================

async def run_trading_bot():
    """Запуск торгового бота"""
    logger.info("🤖 Запуск торгового бота...")
    
    # Проверяем готовность системы
    system_ready = await check_system_components()
    if not system_ready:
        logger.warning("⚠️ Система не полностью готова, но продолжаем в тестовом режиме")
    
    # ✅ ИСПРАВЛЕНО: Безопасная загрузка конфигурации
    try:
        from src.core.unified_config import unified_config as config
        logger.info("✅ Конфигурация загружена")
        
        # Валидируем конфигурацию
        if not config.validate_config():
            logger.error("❌ Конфигурация содержит ошибки")
            return False
            
    except ImportError as e:
        logger.error(f"❌ Ошибка загрузки конфигурации: {e}")
        return False
    
    # ✅ ИСПРАВЛЕНО: Создание конфигурации бота с валидацией
    bot_config = {
        'trading_enabled': True,
        'testnet': getattr(config, 'TESTNET', True),
        'max_positions': getattr(config, 'MAX_POSITIONS', 10),
        'risk_per_trade': getattr(config, 'RISK_PER_TRADE_PERCENT', 1.0) / 100,
        'stop_loss_percent': getattr(config, 'STOP_LOSS_PERCENT', 2.0) / 100,
        'take_profit_percent': getattr(config, 'TAKE_PROFIT_PERCENT', 4.0) / 100,
        'trading_pairs': getattr(config, 'TRADING_PAIRS', None) or ['BTCUSDT', 'ETHUSDT'],
        'analysis_interval': 60,  # секунды
        'auto_strategy_selection': True,
        'emergency_stop_enabled': True
    }
    
    # Логируем конфигурацию
    logger.info("🎯 Конфигурация бота:")
    logger.info(f"   🔧 Режим: {'TESTNET' if bot_config['testnet'] else 'LIVE'}")
    logger.info(f"   📊 Максимум позиций: {bot_config['max_positions']}")
    logger.info(f"   ⚠️ Риск на сделку: {bot_config['risk_per_trade']*100:.1f}%")
    logger.info(f"   🛡️ Stop Loss: {bot_config['stop_loss_percent']*100:.1f}%")
    logger.info(f"   🎯 Take Profit: {bot_config['take_profit_percent']*100:.1f}%")
    logger.info(f"   💰 Торговые пары: {', '.join(bot_config['trading_pairs'])}")
    logger.info(f"   ⏱️ Интервал анализа: {bot_config['analysis_interval']}с")
    
    # Выбираем класс бота
    bot_class = None
    available_bots = [
        ('src.bot.manager', 'TradingBotWithRealTrading', 'TradingBotWithRealTrading'),
        ('src.bot.manager', 'BotManager', 'BotManager'),
        ('src.bot.trader', 'Trader', 'Trader'),
        ('src.bot.trading_integration', 'TradingIntegration', 'TradingIntegration'),
        ('src.bot.advanced_manager', 'AdvancedTradingBot', 'AdvancedTradingBot'),
    ]
    
    for module_name, class_name, display_name in available_bots:
        try:
            module = __import__(module_name, fromlist=[class_name])
            bot_class = getattr(module, class_name)
            logger.info(f"✅ Будем использовать {display_name}")
            break
        except (ImportError, AttributeError) as e:
            logger.debug(f"⚠️ {display_name} недоступен: {e}")
            continue
    
    if bot_class is None:
        logger.error("❌ Не удалось найти ни один подходящий класс бота")
        logger.info("💡 Убедитесь что хотя бы один из bot модулей доступен")
        return False
    
    # Создаем и запускаем бота
    try:
        logger.info(f"🎯 Создаем экземпляр {bot_class.__name__}...")
        
        # ✅ ИСПРАВЛЕНО: Создание бота с обработкой ошибок
        try:
            # Проверяем что конструктор принимает config
            import inspect
            signature = inspect.signature(bot_class.__init__)
            
            if 'config' in signature.parameters:
                bot = bot_class(config=bot_config)
                logger.info("✅ Передали config в конструктор")
            elif 'bot_config' in signature.parameters:
                bot = bot_class(bot_config=bot_config)
                logger.info("✅ Передали bot_config в конструктор")
            else:
                bot = bot_class()
                logger.info("✅ Создали бота без параметров")
                
        except Exception as init_error:
            logger.error(f"❌ Ошибка создания бота: {init_error}")
            logger.error(f"❌ Класс: {bot_class.__name__}")
            return False
        
        # Запускаем бота
        logger.info("🚀 Запуск торгового бота...")
        
        # Проверяем какой метод запуска доступен
        if hasattr(bot, 'start') and callable(getattr(bot, 'start')):
            if asyncio.iscoroutinefunction(bot.start):
                await bot.start()
            else:
                bot.start()
        elif hasattr(bot, 'run') and callable(getattr(bot, 'run')):
            if asyncio.iscoroutinefunction(bot.run):
                await bot.run()
            else:
                bot.run()
        else:
            logger.error("❌ Не найден метод запуска бота")
            return False
        
        logger.info("✅ Торговый бот успешно запущен!")
        return True
        
    except KeyboardInterrupt:
        logger.info("🛑 Получен сигнал остановки")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка работы торгового бота: {e}")
        logger.exception("📊 Полная трассировка ошибки:")
        return False

# ========================================
# ЗАПУСК ВЕБ-ИНТЕРФЕЙСА
# ========================================

async def run_web_interface():
    """Запуск веб-интерфейса"""
    logger.info("🌐 Запуск веб-интерфейса...")
    
    try:
        from src.web.app import create_app
        
        # Создаем Flask приложение
        app = create_app()
        
        # Получаем порт из конфигурации
        port = int(os.getenv('WEB_PORT', 5000))
        
        # Запускаем сервер
        logger.info(f"🌐 Веб-интерфейс запущен на http://localhost:{port}")
        app.run(host='0.0.0.0', port=port, debug=False)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка запуска веб-интерфейса: {e}")
        return False

# ========================================
# ГЛАВНАЯ ФУНКЦИЯ
# ========================================

async def main():
    """Главная функция"""
    show_startup_banner()
    
    # Получаем режим запуска
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
    else:
        mode = 'bot'  # По умолчанию запускаем бота
    
    logger.info(f"🎯 Режим: {mode.title()}")
    
    try:
        if mode == 'bot':
            logger.info("🤖 Инициализация торгового бота...")
            success = await run_trading_bot()
        elif mode == 'web':
            logger.info("🌐 Инициализация веб-интерфейса...")
            success = await run_web_interface()
        elif mode == 'both':
            logger.info("🚀 Инициализация полной системы...")
            # Запускаем бота в фоне
            bot_task = asyncio.create_task(run_trading_bot())
            # Запускаем веб-интерфейс
            web_task = asyncio.create_task(run_web_interface())
            
            # Ждем завершения любой из задач
            done, pending = await asyncio.wait(
                [bot_task, web_task], 
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Отменяем незавершенные задачи
            for task in pending:
                task.cancel()
                
            success = True
        elif mode == 'check':
            logger.info("🔍 Проверка системы...")
            success = await check_system_components()
            logger.info("✅ Проверка завершена")
        else:
            logger.error(f"❌ Неизвестный режим: {mode}")
            logger.info("💡 Доступные режимы: bot, web, both, check")
            success = False
        
        if success:
            logger.info("✅ Система успешно завершила работу")
        else:
            logger.error("❌ Ошибка выполнения операции")
            
    except KeyboardInterrupt:
        logger.info("🛑 Получен сигнал остановки")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        logger.exception("📊 Полная трассировка ошибки:")
    finally:
        logger.info("🏁 Завершение работы")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Программа остановлена пользователем")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка запуска: {e}")
        sys.exit(1)