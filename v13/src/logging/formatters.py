"""
Кастомные форматтеры для различных целей логирования
Файл: src/logging/formatters.py
"""
import json
import logging
from datetime import datetime
from typing import Dict, Any


class JSONFormatter(logging.Formatter):
    """Форматирует логи в JSON для удобного парсинга"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Добавляем дополнительные атрибуты
        if hasattr(record, 'category'):
            log_data['category'] = record.category
        if hasattr(record, 'symbol'):
            log_data['symbol'] = record.symbol
        if hasattr(record, 'strategy'):
            log_data['strategy'] = record.strategy
        if hasattr(record, 'trade_id'):
            log_data['trade_id'] = record.trade_id
        if hasattr(record, 'context'):
            log_data['context'] = record.context
        
        # Добавляем информацию об исключении
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, ensure_ascii=False)


class ColoredConsoleFormatter(logging.Formatter):
    """Цветной форматтер для консоли"""
    
    # Цветовые коды ANSI
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
    }
    
    CATEGORY_COLORS = {
        'trade': '\033[94m',     # Blue
        'profit_loss': '\033[92m', # Light Green
        'signal': '\033[96m',    # Light Cyan
        'strategy': '\033[95m',  # Light Magenta
        'error': '\033[91m',     # Light Red
    }
    
    RESET = '\033[0m'
    BOLD = '\033[1m'
    
    def format(self, record: logging.LogRecord) -> str:
        # Базовое форматирование
        log_fmt = '%(asctime)s - %(levelname)s'
        
        # Добавляем категорию если есть
        if hasattr(record, 'category'):
            log_fmt += ' - %(category)s'
        
        # Добавляем символ если есть
        if hasattr(record, 'symbol'):
            log_fmt += ' [%(symbol)s]'
        
        log_fmt += ' - %(message)s'
        
        # Применяем форматирование
        formatter = logging.Formatter(log_fmt, datefmt='%H:%M:%S')
        formatted = formatter.format(record)
        
        # Добавляем цвета
        level_color = self.COLORS.get(record.levelname, '')
        
        # Цвет категории
        category_color = ''
        if hasattr(record, 'category'):
            category_color = self.CATEGORY_COLORS.get(record.category, '')
        
        # Применяем цвета
        if level_color:
            # Делаем уровень жирным и цветным
            formatted = formatted.replace(
                record.levelname,
                f"{self.BOLD}{level_color}{record.levelname}{self.RESET}"
            )
        
        if category_color and hasattr(record, 'category'):
            formatted = formatted.replace(
                record.category,
                f"{category_color}{record.category}{self.RESET}"
            )
        
        # Подсвечиваем важные слова
        keywords = {
            'PROFIT': '\033[92m',  # Light Green
            'LOSS': '\033[91m',    # Light Red
            'BUY': '\033[94m',     # Blue
            'SELL': '\033[93m',    # Yellow
        }
        
        for keyword, color in keywords.items():
            formatted = formatted.replace(
                keyword,
                f"{self.BOLD}{color}{keyword}{self.RESET}"
            )
        
        return formatted


class TelegramFormatter(logging.Formatter):
    """Форматтер для отправки в Telegram"""
    
    EMOJI_MAP = {
        'DEBUG': '🔍',
        'INFO': 'ℹ️',
        'WARNING': '⚠️',
        'ERROR': '❌',
        'CRITICAL': '🚨'
    }
    
    CATEGORY_EMOJI = {
        'trade': '💼',
        'profit_loss': '💰',
        'signal': '📊',
        'strategy': '🎯',
        'error': '🛑',
        'market': '📈',
        'system': '⚙️'
    }
    
    def format(self, record: logging.LogRecord) -> str:
        # Эмодзи для уровня
        level_emoji = self.EMOJI_MAP.get(record.levelname, '')
        
        # Эмодзи для категории
        category_emoji = ''
        if hasattr(record, 'category'):
            category_emoji = self.CATEGORY_EMOJI.get(record.category, '')
        
        # Форматируем сообщение
        parts = [
            f"{level_emoji} <b>{record.levelname}</b>",
            f"{category_emoji} {getattr(record, 'category', 'system').upper()}"
        ]
        
        # Добавляем символ
        if hasattr(record, 'symbol'):
            parts.append(f"[{record.symbol}]")
        
        # Основное сообщение
        parts.append(f"\n\n{record.getMessage()}")
        
        # Добавляем контекст для важных логов
        if record.levelname in ['ERROR', 'CRITICAL'] and hasattr(record, 'context'):
            context = getattr(record, 'context', {})
            if context:
                parts.append("\n\n<b>Детали:</b>")
                for key, value in context.items():
                    if key not in ['symbol', 'category', 'strategy']:
                        parts.append(f"• {key}: {value}")
        
        # Время
        parts.append(f"\n\n🕐 {datetime.now().strftime('%H:%M:%S')}")
        
        return '\n'.join(parts)


class CSVFormatter(logging.Formatter):
    """Форматтер для экспорта в CSV"""
    
    def format(self, record: logging.LogRecord) -> str:
        # Подготавливаем данные
        timestamp = datetime.utcnow().isoformat()
        level = record.levelname
        category = getattr(record, 'category', 'system')
        symbol = getattr(record, 'symbol', '')
        strategy = getattr(record, 'strategy', '')
        message = record.getMessage().replace('"', '""')  # Экранируем кавычки
        
        # Формируем CSV строку
        csv_parts = [
            timestamp,
            level,
            category,
            symbol,
            strategy,
            f'"{message}"'
        ]
        
        # Добавляем контекст как JSON
        if hasattr(record, 'context'):
            context_json = json.dumps(
                getattr(record, 'context', {}), 
                ensure_ascii=False
            ).replace('"', '""')
            csv_parts.append(f'"{context_json}"')
        else:
            csv_parts.append('""')
        
        return ','.join(csv_parts)


class MetricsFormatter(logging.Formatter):
    """Форматтер для метрик в формате Prometheus"""
    
    def format(self, record: logging.LogRecord) -> str:
        # Только для категорий с метриками
        if not hasattr(record, 'context'):
            return ''
        
        context = getattr(record, 'context', {})
        metrics = []
        
        # Извлекаем метрики из контекста
        if record.category == 'trade':
            if 'price' in context:
                metrics.append(f'trade_price{{symbol="{record.symbol}",action="{context.get("side", "unknown")}"}} {context["price"]}')
            if 'quantity' in context:
                metrics.append(f'trade_quantity{{symbol="{record.symbol}"}} {context["quantity"]}')
        
        elif record.category == 'profit_loss':
            if 'profit' in context:
                metrics.append(f'trade_profit{{symbol="{record.symbol}"}} {context["profit"]}')
            if 'profit_percent' in context:
                metrics.append(f'trade_profit_percent{{symbol="{record.symbol}"}} {context["profit_percent"]}')
        
        elif record.category == 'signal':
            if 'confidence' in context:
                metrics.append(f'signal_confidence{{symbol="{record.symbol}",strategy="{record.strategy}"}} {context["confidence"]}')
        
        # Добавляем timestamp
        timestamp = int(datetime.utcnow().timestamp() * 1000)
        return '\n'.join([f"{metric} {timestamp}" for metric in metrics])


class SlackFormatter(logging.Formatter):
    """Форматтер для Slack webhooks"""
    
    def format(self, record: logging.LogRecord) -> Dict[str, Any]:
        # Цвета для уровней
        color_map = {
            'DEBUG': '#36a64f',
            'INFO': '#2eb886',
            'WARNING': '#ff9900',
            'ERROR': '#ff0000',
            'CRITICAL': '#8b0000'
        }
        
        # Основное сообщение
        text = f"{record.levelname}: {record.getMessage()}"
        
        # Формируем attachment
        attachment = {
            "color": color_map.get(record.levelname, '#808080'),
            "title": getattr(record, 'category', 'System').title(),
            "text": record.getMessage(),
            "fields": [],
            "footer": "Trading Bot",
            "ts": int(datetime.utcnow().timestamp())
        }
        
        # Добавляем поля
        if hasattr(record, 'symbol'):
            attachment['fields'].append({
                "title": "Symbol",
                "value": record.symbol,
                "short": True
            })
        
        if hasattr(record, 'strategy'):
            attachment['fields'].append({
                "title": "Strategy",
                "value": record.strategy,
                "short": True
            })
        
        # Добавляем контекст для важных событий
        if record.levelname in ['ERROR', 'CRITICAL'] and hasattr(record, 'context'):
            context = getattr(record, 'context', {})
            for key, value in context.items():
                if key not in ['symbol', 'strategy', 'category']:
                    attachment['fields'].append({
                        "title": key.replace('_', ' ').title(),
                        "value": str(value),
                        "short": True
                    })
        
        return {
            "text": text,
            "attachments": [attachment]
        }