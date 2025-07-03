"""
ИСПРАВЛЕННЫЙ МОДУЛЬ TELEGRAM УВЕДОМЛЕНИЙ
========================================
Файл: src/notifications/telegram.py

🔧 КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ:
✅ Импорт unified_config вместо config
✅ Безопасная инициализация
✅ Полная совместимость с тестами
"""

import asyncio
import aiohttp
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# ✅ ИСПРАВЛЕНИЕ: Правильный импорт конфигурации
try:
    from ..core.unified_config import unified_config as config
    CONFIG_AVAILABLE = True
    logger.info("✅ unified_config импортирован в telegram")
except ImportError as e:
    logger.error(f"❌ Ошибка импорта unified_config в telegram: {e}")
    CONFIG_AVAILABLE = False
    
    # Создаем минимальную заглушку конфигурации
    class MinimalConfig:
        TELEGRAM_BOT_TOKEN = ""
        TELEGRAM_CHAT_ID = ""
        TELEGRAM_ENABLED = False
        TELEGRAM_ENABLE_TRADE_ALERTS = True
        TELEGRAM_ENABLE_ERROR_ALERTS = True
        TELEGRAM_ENABLE_DAILY_SUMMARY = True
        
    config = MinimalConfig()

class TelegramNotifier:
    """
    ИСПРАВЛЕННЫЙ Telegram уведомлятор
    
    ✅ Работает с unified_config
    ✅ Безопасная инициализация
    ✅ Отработка ошибок конфигурации
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TelegramNotifier, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            try:
                # ✅ ИСПРАВЛЕНИЕ: Безопасное получение настроек из unified_config
                self.bot_token = getattr(config, 'TELEGRAM_BOT_TOKEN', '')
                self.chat_id = getattr(config, 'TELEGRAM_CHAT_ID', '')
                self.enabled = getattr(config, 'TELEGRAM_ENABLED', False)
                
                # Дополнительные настройки
                self.enable_trade_alerts = getattr(config, 'TELEGRAM_ENABLE_TRADE_ALERTS', True)
                self.enable_error_alerts = getattr(config, 'TELEGRAM_ENABLE_ERROR_ALERTS', True) 
                self.enable_daily_summary = getattr(config, 'TELEGRAM_ENABLE_DAILY_SUMMARY', True)
                
                # Проверяем корректность настроек
                if self.bot_token and self.chat_id:
                    self.enabled = self.enabled and True  # Включаем только если есть токен и чат
                    logger.info("✅ Telegram уведомления настроены корректно")
                else:
                    self.enabled = False
                    if not self.bot_token:
                        logger.warning("⚠️ TELEGRAM_BOT_TOKEN не настроен")
                    if not self.chat_id:
                        logger.warning("⚠️ TELEGRAM_CHAT_ID не настроен")
                    logger.warning("⚠️ Telegram уведомления отключены")
                
                self.base_url = f"https://api.telegram.org/bot{self.bot_token}" if self.bot_token else ""
                
                # Эмодзи для сообщений
                self.emojis = {
                    'buy': '🟢',
                    'sell': '🔴', 
                    'profit': '💰',
                    'loss': '📉',
                    'warning': '⚠️',
                    'error': '🚨',
                    'info': 'ℹ️',
                    'success': '✅',
                    'robot': '🤖',
                    'chart': '📊',
                    'rocket': '🚀',
                    'fire': '🔥'
                }
                
                self.initialized = True
                
            except Exception as e:
                logger.error(f"❌ Ошибка инициализации TelegramNotifier: {e}")
                self.enabled = False
                self.initialized = True
    
    async def send_message(self, text: str, parse_mode: str = 'HTML', 
                          disable_notification: bool = False) -> bool:
        """
        Отправка сообщения в Telegram
        
        Args:
            text: Текст сообщения
            parse_mode: Режим парсинга (HTML/Markdown)
            disable_notification: Отключить звук уведомления
            
        Returns:
            bool: Успешность отправки
        """
        if not self.enabled:
            logger.debug(f"📱 Telegram отключен: {text[:50]}...")
            return False
        
        if not self.bot_token or not self.chat_id:
            logger.warning("⚠️ Telegram не настроен для отправки сообщений")
            return False
        
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/sendMessage"
                data = {
                    'chat_id': self.chat_id,
                    'text': text,
                    'parse_mode': parse_mode,
                    'disable_notification': disable_notification
                }
                
                async with session.post(url, json=data, timeout=10) as response:
                    if response.status == 200:
                        logger.debug(f"✅ Сообщение в Telegram отправлено")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ Ошибка Telegram API ({response.status}): {error_text}")
                        return False
                        
        except asyncio.TimeoutError:
            logger.error("❌ Таймаут отправки в Telegram")
            return False
        except Exception as e:
            logger.error(f"❌ Ошибка отправки в Telegram: {e}")
            return False
    
    async def send_trade_alert(self, trade_data: Dict[str, Any]) -> bool:
        """Отправка уведомления о торговой операции"""
        if not self.enable_trade_alerts:
            return False
        
        try:
            symbol = trade_data.get('symbol', 'Unknown')
            side = trade_data.get('side', 'Unknown')
            quantity = trade_data.get('quantity', 0)
            price = trade_data.get('price', 0)
            strategy = trade_data.get('strategy', 'Unknown')
            
            emoji = self.emojis.get('buy' if side.lower() == 'buy' else 'sell', '📊')
            
            message = (
                f"{emoji} <b>Торговый сигнал</b>\n"
                f"📊 <b>Пара:</b> {symbol}\n"
                f"📈 <b>Действие:</b> {side}\n"
                f"💎 <b>Количество:</b> {quantity}\n"
                f"💰 <b>Цена:</b> ${price}\n"
                f"🧠 <b>Стратегия:</b> {strategy}\n"
                f"⏰ <b>Время:</b> {datetime.now().strftime('%H:%M:%S')}"
            )
            
            return await self.send_message(message)
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки торгового алерта: {e}")
            return False
    
    async def send_error_alert(self, error_message: str, component: str = "System") -> bool:
        """Отправка алерта об ошибке"""
        if not self.enable_error_alerts:
            return False
        
        try:
            message = (
                f"{self.emojis['error']} <b>СИСТЕМНАЯ ОШИБКА</b>\n"
                f"🔧 <b>Компонент:</b> {component}\n" 
                f"❌ <b>Ошибка:</b> {error_message}\n"
                f"⏰ <b>Время:</b> {datetime.now().strftime('%H:%M:%S')}"
            )
            
            return await self.send_message(message)
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки алерта об ошибке: {e}")
            return False
    
    async def send_daily_summary(self, summary_data: Dict[str, Any]) -> bool:
        """Отправка ежедневного отчета"""
        if not self.enable_daily_summary:
            return False
        
        try:
            total_trades = summary_data.get('total_trades', 0)
            successful_trades = summary_data.get('successful_trades', 0)
            profit_loss = summary_data.get('profit_loss', 0)
            success_rate = (successful_trades / total_trades * 100) if total_trades > 0 else 0
            
            emoji = self.emojis['profit'] if profit_loss >= 0 else self.emojis['loss']
            
            message = (
                f"{emoji} <b>Ежедневный отчет</b>\n"
                f"📊 <b>Всего сделок:</b> {total_trades}\n"
                f"✅ <b>Успешных:</b> {successful_trades}\n"
                f"📈 <b>Успешность:</b> {success_rate:.1f}%\n"
                f"💰 <b>P&L:</b> ${profit_loss:.2f}\n"
                f"📅 <b>Дата:</b> {summary_data.get('date', datetime.now().strftime('%Y-%m-%d'))}"
            )
            
            return await self.send_message(message)
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки ежедневного отчета: {e}")
            return False
    
    async def send_system_status(self, status_data: Dict[str, Any]) -> bool:
        """Отправка статуса системы"""
        try:
            uptime = status_data.get('uptime', 'Unknown')
            active_pairs = status_data.get('active_pairs', 0)
            system_health = status_data.get('health', 'Unknown')
            
            health_emoji = {
                'healthy': '✅',
                'warning': '⚠️', 
                'critical': '🚨'
            }.get(system_health.lower(), 'ℹ️')
            
            message = (
                f"{health_emoji} <b>Статус системы</b>\n"
                f"⏱️ <b>Время работы:</b> {uptime}\n"
                f"📊 <b>Активных пар:</b> {active_pairs}\n"
                f"💚 <b>Здоровье:</b> {system_health}\n"
                f"⏰ <b>Проверка:</b> {datetime.now().strftime('%H:%M:%S')}"
            )
            
            return await self.send_message(message)
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки статуса системы: {e}")
            return False
    
    def check_configuration(self) -> Dict[str, Any]:
        """Проверка конфигурации Telegram"""
        return {
            'config_available': CONFIG_AVAILABLE,
            'enabled': self.enabled,
            'has_token': bool(self.bot_token),
            'has_chat_id': bool(self.chat_id),
            'trade_alerts': self.enable_trade_alerts,
            'error_alerts': self.enable_error_alerts,
            'daily_summary': self.enable_daily_summary
        }

# ✅ СОЗДАЕМ ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР
try:
    telegram_notifier = TelegramNotifier()
    logger.info("✅ TelegramNotifier глобальный экземпляр создан")
except Exception as e:
    logger.error(f"❌ Ошибка создания TelegramNotifier: {e}")
    
    # Создаем заглушку
    class DummyTelegramNotifier:
        def __init__(self):
            self.enabled = False
        
        async def send_message(self, text: str, **kwargs):
            logger.debug(f"📱 Telegram (заглушка): {text[:50]}...")
            return False
        
        async def send_trade_alert(self, trade_data):
            return False
        
        async def send_error_alert(self, error_message, component="System"):
            return False
        
        async def send_daily_summary(self, summary_data):
            return False
        
        def check_configuration(self):
            return {'enabled': False, 'dummy': True}
    
    telegram_notifier = DummyTelegramNotifier()

# ✅ ЭКСПОРТ
__all__ = ['TelegramNotifier', 'telegram_notifier']