"""
Модули логирования
"""

try:
    from .smart_logger import SmartLogger, get_logger
except ImportError:
    import logging
    SmartLogger = logging.getLogger
    get_logger = logging.getLogger

__all__ = ['SmartLogger', 'get_logger']