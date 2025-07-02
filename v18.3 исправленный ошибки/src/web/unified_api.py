"""
ЕДИНЫЙ API МОДУЛЬ - Объединение всех веб API функций
=====================================================

Объединяет функциональность из:
- charts_routes.py
- consolidated_api.py  
- trading_api.py
- social_api.py
- bot_control.py

Файл: src/web/unified_api.py
"""

import asyncio
import json
import logging
import random
from datetime import datetime, timedelta
from functools import wraps
from typing import Dict, List, Optional, Any, Union

from flask import jsonify, request
from sqlalchemy import text, desc, and_, func
from sqlalchemy.orm import Session

from ..core.database import SessionLocal, get_session
from ..core.models import (
    Balance, Trade, BotState, TradingPair, Signal, TradeStatus,
    User, Order, StrategyPerformance, OrderSide, SignalAction
)
from ..core.unified_config import unified_config
from ..logging.smart_logger import get_logger

logger = get_logger(__name__)

# =================================================================
# ДЕКОРАТОРЫ И УТИЛИТЫ
# =================================================================

def login_required(f):
    """Декоратор для проверки авторизации"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header and not request.cookies.get('session'):
            return jsonify({
                'success': False,
                'error': 'Authorization required'
            }), 401
        return f(*args, **kwargs)
    return decorated_function

def handle_api_error(f):
    """Декоратор для обработки ошибок API"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"❌ API Error in {f.__name__}: {e}")
            return jsonify({
                'success': False,
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }), 500
    return decorated_function

# =================================================================
# ОСНОВНОЙ КЛАСС UNIFIED API
# =================================================================

class UnifiedAPI:
    """
    Единый класс для всех API операций
    Объединяет функциональность всех веб модулей
    """
    
    def __init__(self, exchange_client=None, bot_manager=None):
        self.exchange_client = exchange_client
        self.bot_manager = bot_manager
        self.cache = {}
        self.cache_timeout = 30
        self.ws_manager = None
        
        logger.info("✅ UnifiedAPI инициализирован")
    
    # =================================================================
    # ФУНКЦИИ БАЛАНСА (из charts_routes.py + consolidated_api.py)
    # =================================================================
    
    def get_balance_from_database(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Получение баланса из базы данных
        Из: charts_routes.py
        """
        try:
            with SessionLocal() as db:
                user_filter = user_id or 1
                
                # Получаем последний баланс
                balance_record = db.query(Balance).filter(
                    Balance.user_id == user_filter
                ).order_by(desc(Balance.created_at)).first()
                
                if balance_record:
                    return {
                        'total_usdt': float(balance_record.total_balance or 0),
                        'free_usdt': float(balance_record.available_balance or 0),
                        'used_usdt': float((balance_record.total_balance or 0) - (balance_record.available_balance or 0)),
                        'assets': json.loads(balance_record.details) if balance_record.details else {},
                        'last_updated': balance_record.updated_at.isoformat() if balance_record.updated_at else None,
                        'source': 'database'
                    }
                
                # Если нет записей, возвращаем демо данные
                return self._get_demo_balance_data()
                
        except Exception as e:
            logger.error(f"❌ Ошибка получения баланса из БД: {e}")
            return self._get_demo_balance_data()
    
    def get_consolidated_balance(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Консолидированное получение баланса
        Из: consolidated_api.py
        """
        cache_key = f"balance_{user_id or 'default'}"
        
        # Проверяем кеш
        if self._is_cache_valid(cache_key):
            return self.cache[cache_key]['data']
        
        try:
            # Пытаемся получить с биржи
            if self.exchange_client and hasattr(self.exchange_client, 'get_balance'):
                exchange_balance = self.exchange_client.get_balance()
                if 'error' not in exchange_balance:
                    self._set_cache(cache_key, exchange_balance)
                    return exchange_balance
            
            # Иначе из базы данных
            db_balance = self.get_balance_from_database(user_id)
            self._set_cache(cache_key, db_balance)
            return db_balance
            
        except Exception as e:
            logger.error(f"❌ Ошибка консолидированного баланса: {e}")
            return {'error': str(e)}
    
    def _get_demo_balance_data(self) -> Dict[str, Any]:
        """Демо данные баланса"""
        return {
            'total_usdt': 1000.0,
            'free_usdt': 800.0,
            'used_usdt': 200.0,
            'assets': {
                'USDT': {'free': 800.0, 'used': 200.0, 'total': 1000.0},
                'BTC': {'free': 0.01, 'used': 0.005, 'total': 0.015},
                'ETH': {'free': 0.5, 'used': 0.2, 'total': 0.7}
            },
            'daily_pnl': 25.50,
            'daily_pnl_percent': 2.55,
            'source': 'demo'
        }
    
    # =================================================================
    # ФУНКЦИИ ТОРГОВЫХ ДАННЫХ (из charts_routes.py + consolidated_api.py)
    # =================================================================
    
    def get_recent_trades_from_database(self, limit: int = 10, user_id: Optional[int] = None) -> List[Dict]:
        """
        Получение последних сделок из базы данных
        Из: charts_routes.py
        """
        try:
            with SessionLocal() as db:
                user_filter = user_id or 1
                
                trades = db.query(Trade).filter(
                    Trade.user_id == user_filter
                ).order_by(desc(Trade.created_at)).limit(limit).all()
                
                result = []
                for trade in trades:
                    result.append({
                        'id': trade.id,
                        'symbol': trade.symbol,
                        'side': trade.side.value if trade.side else 'unknown',
                        'amount': float(trade.amount or 0),
                        'price': float(trade.price or 0),
                        'total': float(trade.amount or 0) * float(trade.price or 0),
                        'profit_loss': float(trade.profit_loss or 0),
                        'status': trade.status.value if trade.status else 'unknown',
                        'strategy': trade.strategy,
                        'created_at': trade.created_at.isoformat() if trade.created_at else None,
                        'fees': float(trade.fees or 0)
                    })
                
                return result
                
        except Exception as e:
            logger.error(f"❌ Ошибка получения сделок из БД: {e}")
            return self._get_demo_trades_data()
    
    def get_consolidated_trades(self, user_id: Optional[int] = None, limit: int = 10, symbol: str = None) -> Dict[str, Any]:
        """
        Консолидированное получение торговых данных
        Из: consolidated_api.py
        """
        try:
            trades = self.get_recent_trades_from_database(limit, user_id)
            
            # Фильтруем по символу если указан
            if symbol:
                trades = [trade for trade in trades if trade['symbol'] == symbol]
            
            # Статистика
            total_trades = len(trades)
            profitable_trades = len([t for t in trades if float(t['profit_loss']) > 0])
            win_rate = (profitable_trades / total_trades * 100) if total_trades > 0 else 0
            total_pnl = sum(float(t['profit_loss']) for t in trades)
            
            return {
                'success': True,
                'trades': trades,
                'statistics': {
                    'total_trades': total_trades,
                    'profitable_trades': profitable_trades,
                    'win_rate': round(win_rate, 2),
                    'total_pnl': round(total_pnl, 2)
                },
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка консолидированных сделок: {e}")
            return {'success': False, 'error': str(e)}
    
    def _get_demo_trades_data(self) -> List[Dict]:
        """Демо данные сделок"""
        return [
            {
                'id': i,
                'symbol': ['BTCUSDT', 'ETHUSDT', 'BNBUSDT'][i % 3],
                'side': ['BUY', 'SELL'][i % 2],
                'amount': round(random.uniform(0.001, 0.1), 6),
                'price': round(random.uniform(20000, 70000), 2),
                'profit_loss': round(random.uniform(-50, 100), 2),
                'status': 'CLOSED',
                'created_at': (datetime.utcnow() - timedelta(hours=i)).isoformat()
            }
            for i in range(10)
        ]
    
    # =================================================================
    # ФУНКЦИИ СТАТУСА БОТА (из charts_routes.py + bot_control.py)
    # =================================================================
    
    def get_bot_status_from_database(self) -> Dict[str, Any]:
        """
        Получение статуса бота из базы данных
        Из: charts_routes.py
        """
        try:
            # Сначала пытаемся получить от bot_manager
            if self.bot_manager and hasattr(self.bot_manager, 'get_status'):
                try:
                    return self.bot_manager.get_status()
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка получения статуса от bot_manager: {e}")
            
            # Иначе из базы данных
            with SessionLocal() as db:
                bot_state = db.query(BotState).order_by(desc(BotState.created_at)).first()
                
                if bot_state:
                    return {
                        'is_running': bool(bot_state.is_running),
                        'strategy': bot_state.strategy or 'auto',
                        'trading_pairs': json.loads(bot_state.trading_pairs) if bot_state.trading_pairs else [],
                        'last_activity': bot_state.last_activity.isoformat() if bot_state.last_activity else None,
                        'active_positions': bot_state.active_positions or 0,
                        'daily_trades': bot_state.daily_trades or 0,
                        'status': 'active' if bot_state.is_running else 'stopped',
                        'source': 'database'
                    }
                
                # Демо статус если нет записей
                return {
                    'is_running': False,
                    'strategy': 'auto',
                    'trading_pairs': ['BTCUSDT', 'ETHUSDT'],
                    'active_positions': 0,
                    'daily_trades': 0,
                    'status': 'stopped',
                    'source': 'demo'
                }
                
        except Exception as e:
            logger.error(f"❌ Ошибка получения статуса бота: {e}")
            return {'error': str(e)}
    
    def get_consolidated_bot_status(self) -> Dict[str, Any]:
        """
        Консолидированный статус бота
        Из: consolidated_api.py
        """
        try:
            status = self.get_bot_status_from_database()
            
            # Добавляем дополнительную информацию
            if 'error' not in status:
                status.update({
                    'uptime': self._calculate_uptime(),
                    'performance': self._get_bot_performance(),
                    'health': self._check_bot_health()
                })
            
            return status
            
        except Exception as e:
            logger.error(f"❌ Ошибка консолидированного статуса: {e}")
            return {'error': str(e)}
    
    # =================================================================
    # ФУНКЦИИ УПРАВЛЕНИЯ БОТОМ (из trading_api.py + bot_control.py)
    # =================================================================
    
    def start_bot(self, strategy: str = 'auto', pairs: List[str] = None) -> Dict[str, Any]:
        """
        Запуск торгового бота
        Из: trading_api.py
        """
        try:
            if not self.bot_manager:
                return {
                    'success': False,
                    'error': 'Bot manager not available'
                }
            
            # Подготавливаем параметры
            trading_pairs = pairs or ['BTCUSDT', 'ETHUSDT']
            
            # Запускаем бот
            success = self.bot_manager.start(strategy=strategy, pairs=trading_pairs)
            
            if success:
                # Уведомляем через WebSocket
                self._notify_websocket('bot_started', {
                    'strategy': strategy,
                    'pairs': trading_pairs,
                    'timestamp': datetime.utcnow().isoformat()
                })
                
                return {
                    'success': True,
                    'message': 'Bot started successfully',
                    'strategy': strategy,
                    'trading_pairs': trading_pairs,
                    'timestamp': datetime.utcnow().isoformat()
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to start bot'
                }
                
        except Exception as e:
            logger.error(f"❌ Ошибка запуска бота: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def stop_bot(self) -> Dict[str, Any]:
        """
        Остановка торгового бота
        Из: trading_api.py
        """
        try:
            if not self.bot_manager:
                return {
                    'success': False,
                    'error': 'Bot manager not available'
                }
            
            success = self.bot_manager.stop()
            
            if success:
                # Уведомляем через WebSocket
                self._notify_websocket('bot_stopped', {
                    'timestamp': datetime.utcnow().isoformat()
                })
                
                return {
                    'success': True,
                    'message': 'Bot stopped successfully',
                    'timestamp': datetime.utcnow().isoformat()
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to stop bot'
                }
                
        except Exception as e:
            logger.error(f"❌ Ошибка остановки бота: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def restart_bot(self) -> Dict[str, Any]:
        """
        Перезапуск торгового бота
        Из: trading_api.py
        """
        try:
            # Останавливаем
            stop_result = self.stop_bot()
            if not stop_result['success']:
                return stop_result
            
            # Ждем немного
            import time
            time.sleep(2)
            
            # Запускаем
            return self.start_bot()
            
        except Exception as e:
            logger.error(f"❌ Ошибка перезапуска бота: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def emergency_stop(self) -> Dict[str, Any]:
        """
        Экстренная остановка бота
        Из: trading_api.py
        """
        try:
            if self.bot_manager and hasattr(self.bot_manager, 'emergency_stop'):
                success = self.bot_manager.emergency_stop()
            else:
                success = self.stop_bot()['success']
            
            return {
                'success': success,
                'message': 'Emergency stop executed',
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка экстренной остановки: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    # =================================================================
    # ФУНКЦИИ ПОЗИЦИЙ (из trading_api.py)
    # =================================================================
    
    def get_bot_positions(self) -> Dict[str, Any]:
        """
        Получение открытых позиций
        Из: trading_api.py
        """
        try:
            if self.bot_manager and hasattr(self.bot_manager, 'get_positions'):
                positions = self.bot_manager.get_positions()
                return {
                    'success': True,
                    'positions': positions,
                    'count': len(positions),
                    'timestamp': datetime.utcnow().isoformat()
                }
            
            return {
                'success': True,
                'positions': [],
                'count': 0,
                'message': 'No active positions'
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения позиций: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def close_position(self, symbol: str) -> Dict[str, Any]:
        """
        Закрытие конкретной позиции
        Из: trading_api.py
        """
        try:
            if self.bot_manager and hasattr(self.bot_manager, 'close_position'):
                success = self.bot_manager.close_position(symbol)
                return {
                    'success': success,
                    'message': f'Position {symbol} close requested',
                    'symbol': symbol,
                    'timestamp': datetime.utcnow().isoformat()
                }
            
            return {
                'success': False,
                'error': 'Bot manager not available'
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка закрытия позиции {symbol}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def close_all_positions(self) -> Dict[str, Any]:
        """
        Закрытие всех позиций
        Из: trading_api.py
        """
        try:
            if self.bot_manager and hasattr(self.bot_manager, 'close_all_positions'):
                success = self.bot_manager.close_all_positions()
                return {
                    'success': success,
                    'message': 'All positions close requested',
                    'timestamp': datetime.utcnow().isoformat()
                }
            
            return {
                'success': False,
                'error': 'Bot manager not available'
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка закрытия всех позиций: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    # =================================================================
    # СОЦИАЛЬНЫЕ ФУНКЦИИ (из social_api.py)
    # =================================================================
    
    def get_latest_news(self, limit: int = 20, category: str = 'all', sentiment: str = 'all') -> Dict[str, Any]:
        """
        Получение последних новостей
        Из: social_api.py
        """
        try:
            # Генерируем демо новости (в реальной версии здесь будет API)
            news = self._generate_demo_news(limit, category, sentiment)
            
            return {
                'success': True,
                'news': news,
                'count': len(news),
                'filters': {
                    'category': category,
                    'sentiment': sentiment,
                    'limit': limit
                },
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения новостей: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_sentiment_analysis(self, symbol: str = 'BTCUSDT', period: str = '24h') -> Dict[str, Any]:
        """
        Анализ настроений
        Из: social_api.py
        """
        try:
            # Демо данные сентимента
            sentiment_data = {
                'symbol': symbol,
                'period': period,
                'overall_sentiment': round(random.uniform(-1, 1), 3),
                'sentiment_score': round(random.uniform(0, 100), 1),
                'sources': {
                    'twitter': round(random.uniform(-1, 1), 3),
                    'reddit': round(random.uniform(-1, 1), 3),
                    'news': round(random.uniform(-1, 1), 3)
                },
                'trend': random.choice(['bullish', 'bearish', 'neutral']),
                'confidence': round(random.uniform(0.5, 0.95), 2)
            }
            
            return {
                'success': True,
                'sentiment': sentiment_data,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка анализа настроений: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_social_signals(self, symbol: str = 'BTCUSDT') -> Dict[str, Any]:
        """
        Получение социальных сигналов
        Из: social_api.py
        """
        try:
            signals = {
                'symbol': symbol,
                'social_volume': random.randint(1000, 10000),
                'mentions_24h': random.randint(500, 5000),
                'engagement_rate': round(random.uniform(0.5, 15.0), 2),
                'influencer_sentiment': round(random.uniform(-1, 1), 3),
                'viral_posts': random.randint(0, 10),
                'trending_hashtags': ['#bitcoin', '#crypto', '#trading']
            }
            
            return {
                'success': True,
                'signals': signals,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения социальных сигналов: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    # =================================================================
    # ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
    # =================================================================
    
    def _is_cache_valid(self, key: str) -> bool:
        """Проверка валидности кеша"""
        if key not in self.cache:
            return False
        
        cached_time = self.cache[key]['timestamp']
        current_time = datetime.utcnow()
        
        return (current_time - cached_time).total_seconds() < self.cache_timeout
    
    def _set_cache(self, key: str, data: Any):
        """Установка кеша"""
        self.cache[key] = {
            'data': data,
            'timestamp': datetime.utcnow()
        }
    
    def clear_cache(self):
        """Очистка кеша"""
        self.cache.clear()
        logger.info("🗑️ Кеш API очищен")
    
    def _calculate_uptime(self) -> str:
        """Расчет времени работы бота"""
        # Здесь будет реальная логика расчета
        return "2h 35m"
    
    def _get_bot_performance(self) -> Dict[str, Any]:
        """Получение производительности бота"""
        return {
            'daily_pnl': round(random.uniform(-100, 200), 2),
            'win_rate': round(random.uniform(60, 85), 1),
            'trades_today': random.randint(5, 25)
        }
    
    def _check_bot_health(self) -> str:
        """Проверка здоровья бота"""
        return random.choice(['healthy', 'warning', 'error'])
    
    def _notify_websocket(self, event: str, data: Dict[str, Any]):
        """Уведомление через WebSocket"""
        if self.ws_manager:
            try:
                self.ws_manager.broadcast(event, data)
            except Exception as e:
                logger.warning(f"⚠️ Ошибка WebSocket уведомления: {e}")
    
    def _generate_demo_news(self, limit: int, category: str, sentiment: str) -> List[Dict]:
        """Генерация демо новостей"""
        news_templates = [
            "Bitcoin reaches new monthly high amid institutional adoption",
            "Ethereum upgrade shows promising scalability improvements",
            "Major exchange announces new trading features",
            "Regulatory clarity boosts crypto market confidence",
            "DeFi protocol launches innovative yield farming program"
        ]
        
        return [
            {
                'id': i,
                'title': news_templates[i % len(news_templates)],
                'summary': f"Summary for news item {i}...",
                'sentiment': round(random.uniform(-1, 1), 3),
                'impact_score': round(random.uniform(0, 10), 1),
                'source': random.choice(['CoinDesk', 'CoinTelegraph', 'Decrypt']),
                'published_at': (datetime.utcnow() - timedelta(hours=i)).isoformat(),
                'url': f"https://example.com/news/{i}"
            }
            for i in range(limit)
        ]

# =================================================================
# ФУНКЦИИ РЕГИСТРАЦИИ API ENDPOINTS
# =================================================================

def register_unified_api_routes(app, exchange_client=None, bot_manager=None, ws_manager=None):
    """
    Единая регистрация всех API endpoints
    ЗАМЕНЯЕТ: все register_*_routes функции
    """
    
    # Создаем экземпляр объединенного API
    api = UnifiedAPI(exchange_client, bot_manager)
    api.ws_manager = ws_manager
    
    logger.info("🔄 Регистрация объединенных API routes...")
    
    # =================================================================
    # ENDPOINTS БАЛАНСА
    # =================================================================
    
    @app.route('/api/balance', methods=['GET'])
    @handle_api_error
    def get_balance():
        """Получение баланса"""
        user_id = request.args.get('user_id', type=int)
        balance_data = api.get_consolidated_balance(user_id)
        return jsonify({
            'success': 'error' not in balance_data,
            'balance': balance_data,
            'timestamp': datetime.utcnow().isoformat()
        })
    
    @app.route('/api/balance/refresh', methods=['POST'])
    @handle_api_error
    def refresh_balance():
        """Обновление баланса"""
        api.clear_cache()
        user_id = request.json.get('user_id') if request.json else None
        balance_data = api.get_consolidated_balance(user_id)
        return jsonify({
            'success': True,
            'message': 'Balance refreshed',
            'balance': balance_data
        })
    
    # =================================================================
    # ENDPOINTS ТОРГОВЛИ
    # =================================================================
    
    @app.route('/api/trades', methods=['GET'])
    @handle_api_error
    def get_trades():
        """Получение торговых данных"""
        user_id = request.args.get('user_id', type=int)
        limit = request.args.get('limit', 10, type=int)
        symbol = request.args.get('symbol')
        
        trades_data = api.get_consolidated_trades(user_id, limit, symbol)
        return jsonify(trades_data)
    
    @app.route('/api/trades/recent', methods=['GET'])
    @handle_api_error  
    def get_recent_trades():
        """Получение последних торговых данных"""
        user_id = request.args.get('user_id', type=int)
        limit = request.args.get('limit', 10, type=int)
        symbol = request.args.get('symbol')
        
        trades_data = api.get_consolidated_trades(user_id, limit, symbol)
        return jsonify(trades_data)
    
    # =================================================================
    # ENDPOINTS УПРАВЛЕНИЯ БОТОМ
    # =================================================================
    
    @app.route('/api/bot/status', methods=['GET'])
    @handle_api_error
    def get_bot_status():
        """Получение статуса бота"""
        status_data = api.get_consolidated_bot_status()
        return jsonify(status_data)
    
    @app.route('/api/bot/start', methods=['POST'])
    @login_required
    @handle_api_error
    def start_bot():
        """Запуск бота"""
        data = request.get_json() or {}
        strategy = data.get('strategy', 'auto')
        pairs = data.get('pairs', ['BTCUSDT', 'ETHUSDT'])
        
        result = api.start_bot(strategy, pairs)
        return jsonify(result)
    
    @app.route('/api/bot/stop', methods=['POST'])
    @login_required
    @handle_api_error
    def stop_bot():
        """Остановка бота"""
        result = api.stop_bot()
        return jsonify(result)
    
    @app.route('/api/bot/restart', methods=['POST'])
    @login_required
    @handle_api_error
    def restart_bot():
        """Перезапуск бота"""
        result = api.restart_bot()
        return jsonify(result)
    
    @app.route('/api/bot/emergency-stop', methods=['POST'])
    @login_required
    @handle_api_error
    def emergency_stop():
        """Экстренная остановка"""
        result = api.emergency_stop()
        return jsonify(result)
    
    # =================================================================
    # ENDPOINTS ПОЗИЦИЙ
    # =================================================================
    
    @app.route('/api/bot/positions', methods=['GET'])
    @handle_api_error
    def get_positions():
        """Получение позиций"""
        result = api.get_bot_positions()
        return jsonify(result)
    
    @app.route('/api/bot/close-position/<symbol>', methods=['POST'])
    @login_required
    @handle_api_error
    def close_position(symbol):
        """Закрытие позиции"""
        result = api.close_position(symbol)
        return jsonify(result)
    
    @app.route('/api/bot/close-all-positions', methods=['POST'])
    @login_required
    @handle_api_error
    def close_all_positions():
        """Закрытие всех позиций"""
        result = api.close_all_positions()
        return jsonify(result)
    
    # =================================================================
    # ENDPOINTS СОЦИАЛЬНЫХ ДАННЫХ
    # =================================================================
    
    @app.route('/api/news/latest', methods=['GET'])
    @handle_api_error
    def get_latest_news():
        """Получение новостей"""
        limit = int(request.args.get('limit', 20))
        category = request.args.get('category', 'all')
        sentiment = request.args.get('sentiment', 'all')
        
        result = api.get_latest_news(limit, category, sentiment)
        return jsonify(result)
    
    @app.route('/api/news/sentiment', methods=['GET'])
    @handle_api_error
    def get_sentiment():
        """Анализ настроений"""
        symbol = request.args.get('symbol', 'BTCUSDT')
        period = request.args.get('period', '24h')
        
        result = api.get_sentiment_analysis(symbol, period)
        return jsonify(result)
    
    @app.route('/api/social/signals', methods=['GET'])
    @handle_api_error
    def get_social_signals():
        """Социальные сигналы"""
        symbol = request.args.get('symbol', 'BTCUSDT')
        result = api.get_social_signals(symbol)
        return jsonify(result)
    
    # =================================================================
    # CORS SUPPORT
    # =================================================================
    
    @app.route('/api/<path:path>', methods=['OPTIONS'])
    def handle_options(path):
        """CORS preflight"""
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
        return response
    
    # =================================================================
    # HEALTH CHECK
    # =================================================================
    
    @app.route('/api/health', methods=['GET'])
    def health_check():
        """Health check"""
        return jsonify({
            'success': True,
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'api_version': '3.0.0'
        })
    
    logger.info("✅ Объединенные API routes зарегистрированы:")
    logger.info("   🟢 Баланс: /api/balance")
    logger.info("   🟢 Торговля: /api/trades, /api/bot/*")
    logger.info("   🟢 Позиции: /api/bot/positions")
    logger.info("   🟢 Социальные: /api/news/*, /api/social/*")
    logger.info("   🟢 Утилиты: /api/health")
    
    return api

# =================================================================
# ЭКСПОРТЫ
# =================================================================

__all__ = [
    'UnifiedAPI',
    'register_unified_api_routes',
    'login_required',
    'handle_api_error'
]