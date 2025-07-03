"""
Фабрика стратегий для криптотрейдинг бота - ИСПРАВЛЕННАЯ ВЕРСИЯ
Файл: src/strategies/factory.py
"""

from typing import Dict, Type, List, Optional
import logging

logger = logging.getLogger(__name__)

# Импорт базового класса
from .base import BaseStrategy

# Импорт основных стратегий
from .momentum import MomentumStrategy
from .multi_indicator import MultiIndicatorStrategy
from .scalping import ScalpingStrategy

class StrategyFactory:
    """
    Фабрика для создания торговых стратегий - ИСПРАВЛЕННАЯ ВЕРСИЯ
    
    ИСПРАВЛЕНИЯ:
    - Правильная передача параметров в конструкторы стратегий
    - Обработка случаев, когда стратегия принимает только название
    - Улучшенная обработка ошибок
    """
    
    def __init__(self):
        """Инициализация фабрики стратегий"""
        # Базовые стратегии (всегда доступны)
        self._strategies: Dict[str, Type[BaseStrategy]] = {
            'momentum': MomentumStrategy,
            'multi_indicator': MultiIndicatorStrategy,
            'scalping': ScalpingStrategy
        }
        
        # Попытаемся загрузить дополнительные стратегии
        self._load_additional_strategies()
    
    def _load_additional_strategies(self):
        """Безопасная загрузка дополнительных стратегий"""
        
        # Загружаем безопасную стратегию
        try:
            from .safe_multi_indicator import SafeMultiIndicatorStrategy
            self._strategies['safe_multi_indicator'] = SafeMultiIndicatorStrategy
            logger.debug("✅ Загружена стратегия: safe_multi_indicator")
        except ImportError as e:
            logger.debug(f"⚠️ SafeMultiIndicatorStrategy не найдена: {e}")
        except Exception as e:
            logger.warning(f"❌ Ошибка загрузки SafeMultiIndicatorStrategy: {e}")
        
        # Загружаем консервативную стратегию
        try:
            from .conservative import ConservativeStrategy
            self._strategies['conservative'] = ConservativeStrategy
            logger.debug("✅ Загружена стратегия: conservative")
        except ImportError as e:
            logger.debug(f"⚠️ ConservativeStrategy не найдена: {e}")
        except Exception as e:
            logger.warning(f"❌ Ошибка загрузки ConservativeStrategy: {e}")
    
    def create(self, name: str, config: Optional[Dict] = None, **kwargs) -> BaseStrategy:
        """
        Создание экземпляра стратегии - ИСПРАВЛЕННАЯ ВЕРСИЯ
        
        Args:
            name: Название стратегии
            config: Конфигурация стратегии (словарь)
            **kwargs: Дополнительные параметры для стратегии
            
        Returns:
            Экземпляр стратегии
            
        Raises:
            ValueError: Если стратегия не найдена
        """
        if name not in self._strategies:
            available = ', '.join(self._strategies.keys())
            raise ValueError(
                f"Неизвестная стратегия: '{name}'. "
                f"Доступные стратегии: {available}"
            )
        
        strategy_class = self._strategies[name]
        
        try:
            # ✅ ИСПРАВЛЕНИЕ: Правильная передача параметров
            # Проверяем, что принимает конструктор стратегии
            import inspect
            sig = inspect.signature(strategy_class.__init__)
            params = list(sig.parameters.keys())[1:]  # Исключаем 'self'
            
            if len(params) == 0:
                # Конструктор не принимает параметры (старый стиль)
                logger.debug(f"Создаем стратегию {name} без параметров")
                strategy = strategy_class()
                
                # Устанавливаем name и config после создания
                if hasattr(strategy, 'name'):
                    strategy.name = name
                if hasattr(strategy, 'config') and config:
                    strategy.config.update(config)
                    
                return strategy
                
            elif 'config' in params:
                # Новый стиль: конструктор принимает config
                logger.debug(f"Создаем стратегию {name} с config параметром")
                merged_config = {**kwargs}
                if config:
                    merged_config.update(config)
                    
                return strategy_class(name, config=merged_config)
                
            else:
                # Конструктор принимает только name или другие параметры
                logger.debug(f"Создаем стратегию {name} с базовыми параметрами")
                
                # Попробуем разные варианты вызова
                try:
                    # Вариант 1: только имя
                    return strategy_class(name)
                except TypeError:
                    try:
                        # Вариант 2: без параметров
                        strategy = strategy_class()
                        strategy.name = name
                        return strategy
                    except TypeError:
                        # Вариант 3: с **kwargs
                        return strategy_class(**kwargs)
                        
        except Exception as e:
            logger.error(f"❌ Ошибка создания стратегии {name}: {e}")
            logger.error(f"   Параметры: config={config}, kwargs={kwargs}")
            
            # Попытка создать стратегию без параметров как fallback
            try:
                logger.warning(f"🔄 Пытаемся создать {name} без параметров")
                strategy = strategy_class()
                strategy.name = name
                return strategy
            except Exception as fallback_error:
                logger.error(f"❌ Fallback создание тоже не удалось: {fallback_error}")
                raise e
    
    def list_strategies(self) -> List[str]:
        """
        Получение списка доступных стратегий
        
        Returns:
            Список названий стратегий
        """
        return list(self._strategies.keys())
    
    def get_strategy_info(self, name: str) -> Optional[Dict]:
        """
        Получение информации о стратегии
        
        Args:
            name: Название стратегии
            
        Returns:
            Словарь с информацией о стратегии или None
        """
        if name not in self._strategies:
            return None
        
        strategy_class = self._strategies[name]
        
        # Базовая информация
        info = {
            'name': name,
            'class_name': strategy_class.__name__,
            'description': getattr(strategy_class, '__doc__', 'Описание отсутствует').strip()
        }
        
        # Дополнительные атрибуты, если есть
        if hasattr(strategy_class, 'STRATEGY_TYPE'):
            info['type'] = strategy_class.STRATEGY_TYPE
        else:
            info['type'] = 'general'
        
        if hasattr(strategy_class, 'RISK_LEVEL'):
            info['risk_level'] = strategy_class.RISK_LEVEL
        else:
            info['risk_level'] = 'medium'
        
        if hasattr(strategy_class, 'TIMEFRAMES'):
            info['timeframes'] = strategy_class.TIMEFRAMES
        
        if hasattr(strategy_class, 'SUPPORTED_PAIRS'):
            info['supported_pairs'] = strategy_class.SUPPORTED_PAIRS
        
        return info
    
    def get_all_strategies_info(self) -> Dict[str, Dict]:
        """
        Получение информации о всех стратегиях
        
        Returns:
            Словарь с информацией о всех стратегиях
        """
        return {
            name: self.get_strategy_info(name) 
            for name in self._strategies.keys()
        }
    
    def register_strategy(self, name: str, strategy_class: Type[BaseStrategy]):
        """
        Регистрация новой стратегии
        
        Args:
            name: Название стратегии
            strategy_class: Класс стратегии
        """
        if not issubclass(strategy_class, BaseStrategy):
            raise ValueError(
                f"Стратегия {strategy_class.__name__} должна наследоваться от BaseStrategy"
            )
        
        self._strategies[name] = strategy_class
        logger.info(f"✅ Зарегистрирована стратегия: {name}")
    
    def unregister_strategy(self, name: str):
        """
        Удаление стратегии из фабрики
        
        Args:
            name: Название стратегии
        """
        if name in self._strategies:
            del self._strategies[name]
            logger.info(f"❌ Удалена стратегия: {name}")
    
    def strategy_exists(self, name: str) -> bool:
        """
        Проверка существования стратегии
        
        Args:
            name: Название стратегии
            
        Returns:
            True если стратегия существует
        """
        return name in self._strategies
    
    def get_strategy_count(self) -> int:
        """
        Получение количества доступных стратегий
        
        Returns:
            Количество зарегистрированных стратегий
        """
        return len(self._strategies)

# Создаем глобальный экземпляр фабрики стратегий
strategy_factory = StrategyFactory()

# Информация о версии модуля
__version__ = "1.1.0"

def get_version() -> str:
    """Получить версию модуля стратегий"""
    return __version__

def print_strategies_info():
    """Вывод информации о доступных стратегиях"""
    print(f"📊 Модуль стратегий инициализирован (версия {__version__})")
    print(f"🎯 Загружено стратегий: {strategy_factory.get_strategy_count()}")
    
    for strategy_name in strategy_factory.list_strategies():
        info = strategy_factory.get_strategy_info(strategy_name)
        risk_level = info.get('risk_level', 'unknown')
        strategy_type = info.get('type', 'general')
        print(f" ✅ {strategy_name} ({strategy_type}, риск: {risk_level})")

# Автоматически выводим информацию при импорте
print_strategies_info()

# Экспортируем важные объекты
__all__ = [
    'StrategyFactory',
    'strategy_factory',
    'get_version',
    'print_strategies_info'
]