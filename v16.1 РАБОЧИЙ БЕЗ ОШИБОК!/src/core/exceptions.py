"""Кастомные исключения"""

class BotException(Exception):
    """Базовое исключение бота"""
    pass

class ConfigurationError(BotException):
    """Ошибка конфигурации"""
    pass

class ExchangeError(BotException):
    """Ошибка работы с биржей"""
    pass

class StrategyError(BotException):
    """Ошибка стратегии"""
    pass

class InsufficientBalanceError(BotException):
    """Недостаточно средств"""
    pass
