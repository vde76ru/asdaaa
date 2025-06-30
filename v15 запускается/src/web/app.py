"""
Flask веб-приложение для Crypto Trading Bot - ПОЛНАЯ ИСПРАВЛЕННАЯ ВЕРСИЯ
Файл: src/web/app.py
"""
import os
import json
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request, redirect, url_for, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import asyncio
from functools import wraps
from typing import Dict, Any, List, Optional
import logging

# Импорты из нашего проекта
from ..core.database import SessionLocal
from ..core.models import (
    User, Trade, Signal, Order, BotState, Balance, 
    TradingPair, StrategyPerformance, TradeStatus,
    OrderSide, SignalAction
)
from ..core.unified_config import unified_config as config
from ..exchange.unified_exchange import UnifiedExchangeClient as ExchangeClient
from .async_handler import async_handler
from .websocket_manager import create_websocket_manager

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Глобальные переменные
app = None
socketio = None
bot_manager = None
exchange_client = None
login_manager = None
ws_manager = None

# Хранилище для WebSocket соединений
ws_clients = set()

def create_app():
    """Создание и настройка Flask приложения"""
    global app, socketio, bot_manager, exchange_client, login_manager
    
    # Создаем Flask приложение
    app = Flask(__name__, 
                template_folder='templates',
                static_folder='static')
    
    # Конфигурация
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
    
    # CORS
    CORS(app, resources={r"/*": {"origins": "*"}})
    
    # Инициализация SocketIO
    socketio = SocketIO(app, 
                       cors_allowed_origins="*", 
                       async_mode='threading',
                       logger=True,
                       engineio_logger=True)
    
    # Инициализация LoginManager
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'login'
    login_manager.login_message = 'Пожалуйста, войдите в систему'
    
    # Инициализация компонентов
    try:
        from ..bot.manager import BotManager
        bot_manager = BotManager()
        logger.info("✅ BotManager инициализирован")
    except Exception as e:
        logger.warning(f"⚠️ Не удалось инициализировать BotManager: {e}")
        bot_manager = None
    
    try:
        exchange_client = ExchangeClient()
        logger.info("✅ ExchangeClient инициализирован")
    except Exception as e:
        logger.warning(f"⚠️ Не удалось инициализировать ExchangeClient: {e}")
        exchange_client = None
        
     # Создание улучшенного WebSocket менеджера  
    global ws_manager
    try:
        ws_manager = create_websocket_manager(socketio, bot_manager)
        ws_manager.start()
        logger.info("✅ Улучшенный WebSocketManager интегрирован")
    except Exception as e:
        logger.error(f"❌ Ошибка создания WebSocket менеджера: {e}")
        ws_manager = None
    
    @login_manager.user_loader
    def load_user(user_id):
        """Загрузка пользователя для Flask-Login"""
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == int(user_id)).first()
            return user
        finally:
            db.close()
    
    # ===== ОСНОВНЫЕ МАРШРУТЫ (ОПРЕДЕЛЯЕМ ПЕРВЫМИ!) =====
    
    @app.route('/')
    def index():
        """Перенаправление на дашборд или логин"""
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        return redirect(url_for('login'))
    
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        """Страница входа"""
        if request.method == 'POST':
            data = request.get_json() if request.is_json else request.form
            username = data.get('username')
            password = data.get('password')
            
            db = SessionLocal()
            try:
                user = db.query(User).filter(User.username == username).first()
                
                if user and user.check_password(password):
                    # Проверяем блокировку
                    if user.is_blocked:
                        return jsonify({
                            'success': False,
                            'message': 'Аккаунт заблокирован. Обратитесь к администратору.'
                        }), 403
                    
                    # Успешный вход
                    login_user(user, remember=True)
                    user.last_login = datetime.utcnow()
                    user.failed_login_attempts = 0
                    db.commit()
                    
                    return jsonify({
                        'success': True,
                        'redirect': url_for('dashboard')
                    })
                else:
                    # Неудачная попытка
                    if user:
                        user.failed_login_attempts += 1
                        if user.failed_login_attempts >= 5:
                            user.is_blocked = True
                            user.blocked_at = datetime.utcnow()
                        db.commit()
                    
                    return jsonify({
                        'success': False,
                        'message': 'Неверное имя пользователя или пароль'
                    }), 401
                    
            finally:
                db.close()
        
        return render_template('login.html')
    
    @app.route('/logout')
    @login_required
    def logout():
        """Выход из системы"""
        logout_user()
        return redirect(url_for('login'))
    
    @app.route('/dashboard')
    @login_required
    def dashboard():
        """Главная страница дашборда"""
        db = SessionLocal()
        try:
            # Получаем статистику
            total_trades = db.query(Trade).count()
            active_trades = db.query(Trade).filter(
                Trade.status == TradeStatus.OPEN
            ).count()
            
            # Последние сделки
            recent_trades = db.query(Trade).order_by(
                Trade.created_at.desc()
            ).limit(10).all()
            
            # Статус бота
            bot_status = False
            if bot_manager:
                status = bot_manager.get_status()
                bot_status = status.get('is_running', False)
            
            return render_template('dashboard.html',
                total_trades=total_trades,
                active_trades=active_trades,
                recent_trades=recent_trades,
                bot_status=bot_status
            )
        finally:
            db.close()
    
    # === СТРАНИЦЫ С ГРАФИКАМИ (ОПРЕДЕЛЯЕМ ДО API!) ===
    
    @app.route('/charts')
    @login_required
    def charts_page():
        """Страница с графиками"""
        return render_template('charts.html')
    
    @app.route('/analytics')
    @login_required  
    def analytics_page():
        """Страница с аналитикой"""
        return render_template('analytics.html')
    
    @app.route('/news')
    @login_required
    def news():
        """Страница новостей"""
        return render_template('news.html')
    
    @app.route('/settings')
    @login_required
    def settings():
        """Страница настроек"""
        return render_template('settings.html')
    
    # ===== API ENDPOINTS =====
    
    @app.route('/api/status')
    @login_required
    def api_status():
        """Получить статус системы"""
        status = {
            'bot': {
                'running': False,
                'status': 'stopped'
            },
            'exchange': {
                'connected': False
            },
            'database': {
                'connected': True
            }
        }
        
        # Статус бота
        if bot_manager:
            bot_status = bot_manager.get_status()
            status['bot'] = bot_status
        
        # Статус биржи
        if exchange_client:
            status['exchange']['connected'] = True
        
        return jsonify(status)
    
    @app.route('/api/bot/status')
    @login_required
    def api_bot_status():
        """API статуса бота для графиков"""
        try:
            if bot_manager:
                status = bot_manager.get_status()
                return jsonify({
                    'success': True,
                    'status': status.get('bot_status', 'stopped'),
                    'is_running': status.get('is_running', False),
                    'start_time': status.get('start_time'),
                    'active_pairs': status.get('active_pairs', []),
                    'positions_count': status.get('open_positions', 0),
                    'trades_today': status.get('trades_today', 0)
                })
            else:
                return jsonify({
                    'success': True,
                    'status': 'stopped',
                    'is_running': False,
                    'start_time': None,
                    'active_pairs': ['BTCUSDT', 'ETHUSDT'],
                    'positions_count': 0,
                    'trades_today': 0,
                    'source': 'demo'
                })
        except Exception as e:
            logger.error(f"Ошибка получения статуса бота: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/trades/legacy')
    @login_required
    def get_trades_legacy():
        """Получить историю сделок (legacy endpoint)"""
        db = SessionLocal()
        try:
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 20, type=int)
            status_filter = request.args.get('status')
            
            # Базовый запрос
            query = db.query(Trade)
            
            # Фильтр по статусу
            if status_filter:
                if status_filter == 'open':
                    query = query.filter(Trade.status == TradeStatus.OPEN)
                elif status_filter == 'closed':
                    query = query.filter(Trade.status == TradeStatus.CLOSED)
            
            # Общее количество
            total = query.count()
            
            # Получаем сделки с пагинацией
            trades = query.order_by(Trade.created_at.desc()).offset(
                (page - 1) * per_page
            ).limit(per_page).all()
            
            return jsonify({
                'trades': [trade_to_dict(trade) for trade in trades],
                'total': total,
                'page': page,
                'per_page': per_page,
                'pages': (total + per_page - 1) // per_page
            })
        finally:
            db.close()
    
    @app.route('/api/signals')
    @login_required
    def get_signals():
        """Получить последние сигналы"""
        db = SessionLocal()
        try:
            signals = db.query(Signal).order_by(
                Signal.created_at.desc()
            ).limit(50).all()
            
            return jsonify({
                'signals': [signal_to_dict(signal) for signal in signals]
            })
        finally:
            db.close()
    
    @app.route('/api/analytics/summary')
    @login_required
    def get_analytics_summary():
        """Получить сводку аналитики"""
        db = SessionLocal()
        try:
            # Период анализа - последние 30 дней
            start_date = datetime.utcnow() - timedelta(days=30)
            
            # Статистика по сделкам
            trades = db.query(Trade).filter(
                Trade.created_at >= start_date,
                Trade.status == TradeStatus.CLOSED
            ).all()
            
            total_trades = len(trades)
            profitable_trades = len([t for t in trades if t.profit and t.profit > 0])
            total_profit = sum(t.profit or 0 for t in trades)
            
            # Статистика по стратегиям
            strategy_stats = {}
            for trade in trades:
                if trade.strategy:
                    if trade.strategy not in strategy_stats:
                        strategy_stats[trade.strategy] = {
                            'trades': 0,
                            'profit': 0,
                            'wins': 0
                        }
                    strategy_stats[trade.strategy]['trades'] += 1
                    strategy_stats[trade.strategy]['profit'] += trade.profit or 0
                    if trade.profit and trade.profit > 0:
                        strategy_stats[trade.strategy]['wins'] += 1
            
            return jsonify({
                'period_days': 30,
                'total_trades': total_trades,
                'profitable_trades': profitable_trades,
                'win_rate': round(profitable_trades / total_trades * 100, 2) if total_trades > 0 else 0,
                'total_profit': round(total_profit, 2),
                'strategies': strategy_stats
            })
        finally:
            db.close()
    
    # ===== WebSocket HANDLERS =====
    
    @socketio.on('connect')
    def handle_connect(auth=None):
        """Обработка подключения WebSocket"""
        logger.info(f"WebSocket подключен: {request.sid}")
        ws_clients.add(request.sid)
        
        # Отправляем текущий статус
        if bot_manager:
            try:
                status = bot_manager.get_status()
                emit('bot_status', status)
            except Exception as e:
                logger.error(f"Ошибка получения статуса: {e}")
                emit('bot_status', {
                    'status': 'error',
                    'is_running': False,
                    'error': str(e)
                })
    
    @socketio.on('disconnect')
    def handle_disconnect():
        """Обработка отключения WebSocket"""
        logger.info(f"WebSocket отключен: {request.sid}")
        ws_clients.discard(request.sid)
    
    @socketio.on('get_status')
    def handle_get_status():
        """Получение статуса системы через WebSocket"""
        try:
            if bot_manager:
                status = bot_manager.get_status()
                emit('bot_status', status)
            else:
                emit('bot_status', {
                    'status': 'error',
                    'is_running': False,
                    'error': 'Bot manager не инициализирован'
                })
        except Exception as e:
            logger.error(f"Ошибка получения статуса: {e}")
            emit('bot_status', {
                'status': 'error',
                'is_running': False,
                'error': str(e)
            })
    
    @socketio.on('subscribe_updates')
    def handle_subscribe(data):
        """Подписка на обновления"""
        update_type = data.get('type', 'all')
        logger.info(f"Подписка на обновления: {update_type}")
        # Здесь можно реализовать логику подписок
    
    # ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====
    
    def trade_to_dict(trade: Trade) -> Dict[str, Any]:
        """Преобразование Trade в словарь"""
        return {
            'id': trade.id,
            'symbol': trade.symbol,
            'side': trade.side.value if trade.side else 'unknown',
            'entry_price': float(trade.entry_price) if trade.entry_price else 0,
            'exit_price': float(trade.exit_price) if trade.exit_price else 0,
            'quantity': float(trade.quantity) if trade.quantity else 0,
            'profit': float(trade.profit) if trade.profit else 0,
            'profit_percent': float(trade.profit_percent) if trade.profit_percent else 0,
            'status': trade.status.value if trade.status else 'unknown',
            'strategy': trade.strategy,
            'created_at': trade.created_at.isoformat() if trade.created_at else None,
            'closed_at': trade.closed_at.isoformat() if trade.closed_at else None
        }
    
    def signal_to_dict(signal: Signal) -> Dict[str, Any]:
        """Преобразование Signal в словарь"""
        return {
            'id': signal.id,
            'symbol': signal.symbol,
            'action': signal.action.value if signal.action else 'unknown',
            'price': float(signal.price) if signal.price else 0,
            'confidence': float(signal.confidence) if signal.confidence else 0,
            'strategy': signal.strategy,
            'indicators': signal.indicators,
            'created_at': signal.created_at.isoformat() if signal.created_at else None
        }
    
    # ===== ERROR HANDLERS =====
    
    @app.errorhandler(404)
    def not_found_error(error):
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Endpoint not found'}), 404
        return render_template('404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal error: {error}")
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Internal server error'}), 500
        return render_template('500.html'), 500
    
    @app.before_request
    def before_request():
        """Перед каждым запросом"""
        # Обновляем сессию
        session.permanent = True
        app.permanent_session_lifetime = timedelta(hours=24)
    
    # === ДИАГНОСТИЧЕСКИЙ РОУТ ===
    
    @app.route('/api/system/health')
    def system_health():
        """Проверка здоровья системы включая AsyncRouteHandler"""
        try:
            health_status = {
                'timestamp': datetime.utcnow().isoformat(),
                'components': {
                    'flask_app': True,
                    'bot_manager': bot_manager is not None,
                    'exchange_client': exchange_client is not None,
                    'async_handler': True  # AsyncRouteHandler всегда должен быть доступен
                },
                'async_handler_stats': async_handler.get_stats() if async_handler else None
            }
            
            # Проверяем работоспособность AsyncRouteHandler
            handler_healthy = (
                async_handler and 
                async_handler.loop and 
                async_handler.loop.is_running() and 
                not async_handler.loop.is_closed()
            )
            
            health_status['components']['async_handler_healthy'] = handler_healthy
            
            # Общий статус системы
            all_critical_ok = (
                health_status['components']['flask_app'] and
                health_status['components']['async_handler_healthy']
            )
            
            health_status['overall_status'] = 'healthy' if all_critical_ok else 'degraded'
            
            return jsonify(health_status)
            
        except Exception as e:
            logger.error(f"Ошибка проверки здоровья системы: {e}")
            return jsonify({
                'overall_status': 'error',
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }), 500
    # === WEBSOCKET ДИАГНОСТИКА ===
    @app.route('/api/websocket/stats')
    def websocket_stats():
        """Статистика WebSocket соединений"""
        try:
            global ws_manager
            if ws_manager is not None:
                stats = ws_manager.get_stats()
                return jsonify({
                    'success': True,
                    'websocket_stats': stats,
                    'timestamp': datetime.utcnow().isoformat()
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'WebSocket менеджер не инициализирован'
                }), 503
        except Exception as e:
            logger.error(f"Ошибка получения WebSocket статистики: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/websocket/health')
    def websocket_health():
        """Проверка здоровья WebSocket системы"""
        try:
            global ws_manager
            if ws_manager is not None:
                stats = ws_manager.get_stats()
                
                # Определяем здоровье системы
                health_status = "healthy"
                if stats['active_connections'] == 0:
                    health_status = "no_connections"
                elif stats['messages_failed'] > stats['messages_sent'] * 0.1:
                    health_status = "degraded"
                
                return jsonify({
                    'status': health_status,
                    'active_connections': stats['active_connections'],
                    'queue_size': stats['queue_size'],
                    'error_rate': stats['messages_failed'] / max(stats['messages_sent'], 1),
                    'timestamp': datetime.utcnow().isoformat()
                })
            else:
                return jsonify({
                    'status': 'error',
                    'error': 'WebSocket менеджер недоступен'
                }), 503
        except Exception as e:
            return jsonify({
                'status': 'error', 
                'error': str(e)
            }), 500
    
    # === GRACEFUL SHUTDOWN ===
    
    import atexit
    
    def cleanup():
        """Корректное завершение работы при остановке приложения"""
        try:
            logger.info("🛑 Начинаем корректное завершение работы приложения...")
            
            # Останавливаем AsyncRouteHandler
            if async_handler:
                async_handler.shutdown()
            
            # Останавливаем WebSocket менеджер
            global ws_manager
            if ws_manager is not None:
                try:
                    ws_manager.stop()
                    logger.info("✅ WebSocket менеджер остановлен")
                except Exception as e:
                    logger.error(f"❌ Ошибка остановки WebSocket менеджера: {e}")
            
            logger.info("✅ Приложение корректно завершено")
            
        except Exception as e:
            logger.error(f"❌ Ошибка при завершении работы: {e}")
    
    atexit.register(cleanup)
    
    # === РЕГИСТРИРУЕМ API РОУТЫ ДЛЯ ГРАФИКОВ (ПОСЛЕ ОСНОВНЫХ РОУТОВ!) ===
    
    # === РЕГИСТРИРУЕМ ОБЪЕДИНЕННЫЙ API ===
    try:
        from .unified_api import register_unified_api_routes
        register_unified_api_routes(app, bot_manager, exchange_client)
        logger.info("✅ Объединенный API зарегистрирован (charts + trading + social + bot_control)")
    except ImportError as e:
        logger.error(f"❌ Не удалось импортировать unified_api: {e}")
        logger.error("❌ Система не может работать без unified_api! Проверьте файл src/web/unified_api.py")
    except Exception as e:
        logger.error(f"❌ Ошибка регистрации unified_api: {e}")
    
    # === ВАЛИДАЦИЯ КОНФИГУРАЦИИ ДЛЯ LIVE ТОРГОВЛИ ===
    if not config.PAPER_TRADING and config.LIVE_TRADING:
        try:
            config.validate_config()
            logger.info("✅ Конфигурация для live торговли валидна")
        except ValueError as e:
            logger.error(f"❌ Ошибка конфигурации live торговли: {e}")
            logger.warning("⚠️ Принудительное переключение на paper trading")
            config.PAPER_TRADING = True
            config.LIVE_TRADING = False
    
    # === ДИАГНОСТИКА РОУТОВ ===
    logger.info("🔍 Зарегистрированные роуты:")
    charts_found = False
    for rule in app.url_map.iter_rules():
        if '/charts' in rule.rule or rule.endpoint in ['charts', 'charts_page']:
            logger.info(f"   ⭐ {rule.endpoint} -> {rule.rule}")
            charts_found = True
    
    if not charts_found:
        logger.warning("⚠️ Роуты для /charts не найдены!")
    
    logger.info("🚀 Flask приложение создано успешно")
    
    return app, socketio

# Экспортируем функцию создания приложения
__all__ = ['create_app']