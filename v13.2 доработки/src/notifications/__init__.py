"""
ИСПРАВЛЕННЫЙ МОДУЛЬ УВЕДОМЛЕНИЙ
===============================
Файл: src/notifications/__init__.py

🔧 КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ:
✅ Импорт unified_config вместо config
✅ Правильные алиасы для совместимости
✅ Безопасная инициализация
"""

import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# ✅ ИСПРАВЛЕНИЕ #1: Правильный импорт конфигурации
try:
    from ..core.unified_config import unified_config as config
    CONFIG_AVAILABLE = True
    logger.info("✅ unified_config импортирован в notifications")
except ImportError as e:
    logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА: Не удалось импортировать unified_config: {e}")
    CONFIG_AVAILABLE = False
    
    # Создаем минимальную заглушку
    class MinimalConfig:
        TELEGRAM_ENABLED = False
        TELEGRAM_BOT_TOKEN = ""
        TELEGRAM_CHAT_ID = ""
        EMAIL_ENABLED = False
        
    config = MinimalConfig()

# ✅ БЕЗОПАСНЫЕ ИМПОРТЫ КОМПОНЕНТОВ
try:
    from .telegram import TelegramNotifier, telegram_notifier
    TELEGRAM_AVAILABLE = True
    logger.info("✅ TelegramNotifier импортирован")
except ImportError as e:
    logger.warning(f"⚠️ TelegramNotifier недоступен: {e}")
    TELEGRAM_AVAILABLE = False
    
    # Создаем заглушку
    class TelegramNotifier:
        def __init__(self):
            self.enabled = False
        
        async def send_message(self, text: str, **kwargs):
            logger.info(f"📱 Telegram (заглушка): {text}")
    
    telegram_notifier = TelegramNotifier()

try:
    from .email import EmailNotifier
    EMAIL_AVAILABLE = True
    logger.info("✅ EmailNotifier импортирован")
except ImportError as e:
    logger.warning(f"⚠️ EmailNotifier недоступен: {e}")
    EMAIL_AVAILABLE = False
    
    # Создаем заглушку
    class EmailNotifier:
        def __init__(self):
            self.enabled = False
        
        async def send_email(self, subject: str, body: str, **kwargs):
            logger.info(f"📧 Email (заглушка): {subject}")

# ✅ ГЛАВНЫЙ КЛАСС МЕНЕДЖЕРА УВЕДОМЛЕНИЙ
class NotificationManager:
    """
    Центральный менеджер всех уведомлений
    
    ✅ ИСПРАВЛЕНО: Правильная работа с unified_config
    """
    
    def __init__(self):
        """Инициализация менеджера уведомлений"""
        self.config = config
        self.telegram = telegram_notifier if TELEGRAM_AVAILABLE else TelegramNotifier()
        self.email = EmailNotifier() if EMAIL_AVAILABLE else EmailNotifier()
        
        # Проверяем доступность сервисов
        self.telegram_enabled = (
            TELEGRAM_AVAILABLE and 
            getattr(config, 'TELEGRAM_ENABLED', False) and
            getattr(config, 'TELEGRAM_BOT_TOKEN', '') and
            getattr(config, 'TELEGRAM_CHAT_ID', '')
        )
        
        self.email_enabled = (
            EMAIL_AVAILABLE and 
            getattr(config, 'EMAIL_ENABLED', False)
        )
        
        logger.info(f"📱 Telegram уведомления: {'✅' if self.telegram_enabled else '❌'}")
        logger.info(f"📧 Email уведомления: {'✅' if self.email_enabled else '❌'}")
    
    async def send_trade_notification(self, trade_data: Dict[str, Any]):
        """Отправка уведомления о торговой операции"""
        try:
            symbol = trade_data.get('symbol', 'Unknown')
            side = trade_data.get('side', 'Unknown')
            quantity = trade_data.get('quantity', 0)
            price = trade_data.get('price', 0)
            
            # Формируем сообщение
            emoji = "🟢" if side == "Buy" else "🔴"
            message = (
                f"{emoji} Торговый сигнал\n"
                f"📊 {symbol}\n"
                f"📈 {side}: {quantity} @ ${price}\n"
                f"⏰ {trade_data.get('timestamp', 'Now')}"
            )
            
            # Отправляем через доступные каналы
            if self.telegram_enabled:
                await self.telegram.send_message(message)
            
            if self.email_enabled:
                await self.email.send_email(
                    subject=f"Trade Alert: {symbol} {side}",
                    body=message
                )
                
        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления о сделке: {e}")
    
    async def send_error_alert(self, error_message: str, component: str = "System"):
        """Отправка алерта об ошибке"""
        try:
            message = (
                f"🚨 ОШИБКА СИСТЕМЫ\n"
                f"🔧 Компонент: {component}\n"
                f"❌ Ошибка: {error_message}\n"
                f"⏰ {logger.name}: критическая ошибка"
            )
            
            if self.telegram_enabled:
                await self.telegram.send_message(message)
                
        except Exception as e:
            logger.error(f"❌ Ошибка отправки алерта: {e}")
    
    async def send_daily_summary(self, summary_data: Dict[str, Any]):
        """Отправка ежедневного отчета"""
        try:
            total_trades = summary_data.get('total_trades', 0)
            profit_loss = summary_data.get('profit_loss', 0)
            
            emoji = "📈" if profit_loss >= 0 else "📉"
            message = (
                f"{emoji} Ежедневный отчет\n"
                f"📊 Сделок: {total_trades}\n"
                f"💰 P&L: ${profit_loss:.2f}\n"
                f"📅 {summary_data.get('date', 'Today')}"
            )
            
            if self.telegram_enabled:
                await self.telegram.send_message(message)
                
        except Exception as e:
            logger.error(f"❌ Ошибка отправки отчета: {e}")
    
    def check_status(self) -> Dict[str, bool]:
        """Проверка статуса всех уведомлений"""
        return {
            'telegram_available': TELEGRAM_AVAILABLE,
            'telegram_enabled': self.telegram_enabled,
            'email_available': EMAIL_AVAILABLE,
            'email_enabled': self.email_enabled,
            'config_available': CONFIG_AVAILABLE
        }

# ✅ СОЗДАЕМ ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР
try:
    notification_manager = NotificationManager()
    logger.info("✅ NotificationManager инициализирован")
except Exception as e:
    logger.error(f"❌ Ошибка инициализации NotificationManager: {e}")
    
    # Создаем заглушку
    class DummyNotificationManager:
        def __init__(self):
            pass
        
        async def send_trade_notification(self, trade_data):
            pass
        
        async def send_error_alert(self, error_message, component="System"):
            pass
        
        async def send_daily_summary(self, summary_data):
            pass
        
        def check_status(self):
            return {'all_disabled': True}
    
    notification_manager = DummyNotificationManager()

# ✅ ЭКСПОРТЫ
__all__ = [
    'NotificationManager',
    'TelegramNotifier', 
    'EmailNotifier',
    'notification_manager',
    'telegram_notifier'
]