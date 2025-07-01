"""
Web интерфейс торгового бота - ОБНОВЛЕННАЯ ВЕРСИЯ
Использует объединенный API
"""

# Импортируем основную функцию создания приложения
try:
    from .app import create_app
except ImportError as e:
    print(f"⚠️ Не удалось импортировать create_app: {e}")
    create_app = None

# Импортируем unified_api
try:
    from .unified_api import register_unified_api_routes
    UNIFIED_API_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Не удалось импортировать unified_api: {e}")
    UNIFIED_API_AVAILABLE = False
    register_unified_api_routes = None

# Fallback импорты старых API модулей (для совместимости)
if not UNIFIED_API_AVAILABLE:
    try:
        from .charts_routes import register_chart_routes
    except ImportError:
        register_chart_routes = None
    
    try:
        from .trading_api import register_trading_api_routes
    except ImportError:
        register_trading_api_routes = None
    
    try:
        from .social_api import register_social_api_routes  
    except ImportError:
        register_social_api_routes = None
    
    try:
        from .bot_control import register_bot_control_routes
    except ImportError:
        register_bot_control_routes = None
else:
    # Если unified доступен, устанавливаем fallback в None
    register_chart_routes = None
    register_trading_api_routes = None
    register_social_api_routes = None
    register_bot_control_routes = None

# Импортируем дополнительные модули
try:
    from .async_handler import async_handler
except ImportError:
    async_handler = None

try:
    from .websocket_manager import create_websocket_manager
except ImportError:
    create_websocket_manager = None

# Экспорт
__all__ = [
    # Основная функция
    'create_app',
    
    # Unified API
    'register_unified_api_routes',
    
    # Fallback API функции (для совместимости)
    'register_chart_routes',
    'register_trading_api_routes', 
    'register_social_api_routes',
    'register_bot_control_routes',
    
    # Дополнительные модули
    'async_handler',
    'create_websocket_manager'
]
