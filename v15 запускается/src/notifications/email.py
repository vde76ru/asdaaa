# =================================================================
# Файл: src/notifications/email.py
# =================================================================
"""
Email уведомления для торгового бота
"""
import smtplib
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

class EmailNotifier:
    """Отправка уведомлений по email"""
    
    def __init__(self, smtp_server: str = "smtp.gmail.com", 
                 smtp_port: int = 587):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = None
        self.password = None
        
    def configure(self, username: str, password: str):
        """Настройка SMTP аутентификации"""
        self.username = username
        self.password = password
    
    async def send_trade_notification(self, trade_data: dict):
        """Отправка уведомления о сделке"""
        try:
            subject = f"🚀 Новая сделка: {trade_data.get('symbol')} {trade_data.get('side')}"
            body = f"""
            Выполнена новая сделка:
            
            Символ: {trade_data.get('symbol')}
            Сторона: {trade_data.get('side')}
            Количество: {trade_data.get('quantity')}
            Цена: {trade_data.get('price')}
            Стратегия: {trade_data.get('strategy')}
            Время: {trade_data.get('timestamp')}
            """
            
            return await self.send_email(subject, body)
            
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления о сделке: {e}")
            return False
    
    async def send_email(self, subject: str, body: str, 
                        recipients: Optional[List[str]] = None):
        """Отправка email"""
        if not self.username or not self.password:
            logger.warning("Email не настроен")
            return False
            
        try:
            # Пока что просто логируем
            logger.info(f"📧 Email уведомление: {subject}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка отправки email: {e}")
            return False