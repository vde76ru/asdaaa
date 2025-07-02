#!/usr/bin/env python3
"""
Система управления компонентами бота
Файл: src/core/component_system.py

Этот модуль отвечает за правильную инициализацию всех компонентов системы
с учетом зависимостей и обработкой ошибок.
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional, Callable, Set, Tuple
from enum import Enum
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

class ComponentStatus(Enum):
    """Статусы компонентов"""
    NOT_INITIALIZED = "not_initialized"
    INITIALIZING = "initializing"
    READY = "ready"
    FAILED = "failed"
    DISABLED = "disabled"

@dataclass
class ComponentInfo:
    """Информация о компоненте"""
    name: str
    status: ComponentStatus
    instance: Any = None
    error: Optional[str] = None
    dependencies: List[str] = None
    is_critical: bool = False
    retry_count: int = 0
    max_retries: int = 3
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []

class ComponentManager:
    """
    Менеджер компонентов для системы бота
    
    Обеспечивает:
    - Правильный порядок инициализации
    - Обработку зависимостей
    - Graceful degradation при ошибках
    - Возможность перезапуска компонентов
    """
    
    def __init__(self):
        self.components: Dict[str, ComponentInfo] = {}
        self.initialization_order: List[str] = []
        self._lock = asyncio.Lock()
        
    def register_component(
        self,
        name: str,
        initializer: Callable,
        dependencies: List[str] = None,
        is_critical: bool = False,
        max_retries: int = 3
    ):
        """
        Регистрация компонента
        
        Args:
            name: Имя компонента
            initializer: Функция инициализации
            dependencies: Список зависимостей
            is_critical: Критичность компонента
            max_retries: Максимальное количество попыток
        """
        if dependencies is None:
            dependencies = []
            
        self.components[name] = ComponentInfo(
            name=name,
            status=ComponentStatus.NOT_INITIALIZED,
            dependencies=dependencies,
            is_critical=is_critical,
            max_retries=max_retries
        )
        
        # Сохраняем функцию инициализации
        setattr(self, f"_init_{name}", initializer)
        
        logger.debug(f"📝 Зарегистрирован компонент: {name}")
    
    def _resolve_dependencies(self) -> List[str]:
        """
        Определение правильного порядка инициализации с улучшенной диагностикой
        
        Returns:
            List[str]: Порядок инициализации компонентов
            
        Raises:
            ValueError: При обнаружении циклических зависимостей
        """
        # Топологическая сортировка для разрешения зависимостей
        visited = set()
        temp_visited = set()
        order = []
        dependency_path = []  # ✅ ДОБАВЛЕНО: отслеживание пути зависимостей
        
        def visit(component_name: str):
            """Рекурсивный обход компонента с проверкой циклов"""
            
            # ✅ УЛУЧШЕНО: Детальная диагностика циклических зависимостей
            if component_name in temp_visited:
                cycle_path = " -> ".join(dependency_path + [component_name])
                logger.error(f"❌ Обнаружена циклическая зависимость:")
                logger.error(f"   Путь цикла: {cycle_path}")
                logger.error(f"   Проблемный компонент: {component_name}")
                
                # Показываем все зависимости проблемного компонента
                if component_name in self.components:
                    deps = self.components[component_name].dependencies
                    logger.error(f"   Его зависимости: {deps}")
                
                raise ValueError(f"Циклическая зависимость: {cycle_path}")
            
            if component_name not in visited:
                temp_visited.add(component_name)
                dependency_path.append(component_name)  # ✅ ДОБАВЛЕНО: отслеживание пути
                
                component = self.components.get(component_name)
                if component:
                    logger.debug(f"🔍 Обрабатываем зависимости для {component_name}: {component.dependencies}")
                    
                    for dep in component.dependencies:
                        if dep in self.components:
                            visit(dep)
                        else:
                            # ✅ УЛУЧШЕНО: Предупреждение о недостающих зависимостях
                            logger.warning(f"⚠️ Зависимость '{dep}' не найдена для компонента '{component_name}'")
                            logger.warning(f"   Доступные компоненты: {list(self.components.keys())}")
                            
                            # Проверяем, не является ли это опечаткой
                            similar_components = [name for name in self.components.keys() 
                                                if dep.lower() in name.lower() or name.lower() in dep.lower()]
                            if similar_components:
                                logger.warning(f"   Возможно имелось в виду: {similar_components}")
                else:
                    logger.error(f"❌ Компонент '{component_name}' не зарегистрирован")
                
                dependency_path.pop()  # ✅ ДОБАВЛЕНО: убираем из пути при выходе
                temp_visited.remove(component_name)
                visited.add(component_name)
                order.append(component_name)
                
                logger.debug(f"✅ Компонент '{component_name}' добавлен в порядок инициализации")
        
        # ✅ УЛУЧШЕНО: Подробная информация о процессе разрешения
        logger.info(f"🔍 Начинаем разрешение зависимостей для {len(self.components)} компонентов")
        
        # Посещаем все компоненты
        for component_name in self.components:
            if component_name not in visited:
                logger.debug(f"🚀 Начинаем обход для корневого компонента: {component_name}")
                try:
                    visit(component_name)
                except ValueError as e:
                    # Добавляем контекст к ошибке циклической зависимости
                    logger.error(f"❌ Ошибка при обработке компонента '{component_name}': {e}")
                    raise
        
        # ✅ ДОБАВЛЕНО: Финальная диагностика
        logger.info(f"✅ Зависимости разрешены успешно")
        logger.info(f"📋 Порядок инициализации ({len(order)} компонентов): {' -> '.join(order)}")
        
        # Проверяем критичные компоненты
        critical_components = [name for name, comp in self.components.items() if comp.is_critical]
        critical_positions = {name: order.index(name) for name in critical_components if name in order}
        logger.info(f"🔥 Критичные компоненты и их позиции: {critical_positions}")
        
        return order
    
    def validate_dependencies(self) -> Tuple[bool, List[str]]:
        """
        ✅ НОВЫЙ МЕТОД: Валидация всех зависимостей перед инициализацией
        
        Returns:
            Tuple[bool, List[str]]: (Валидны ли зависимости, Список ошибок)
        """
        errors = []
        
        logger.info("🔍 Валидация зависимостей компонентов...")
        
        for component_name, component in self.components.items():
            # Проверяем существование зависимостей
            for dep in component.dependencies:
                if dep not in self.components:
                    error_msg = f"Компонент '{component_name}' зависит от несуществующего '{dep}'"
                    errors.append(error_msg)
                    logger.error(f"❌ {error_msg}")
            
            # Проверяем критичные зависимости
            if component.is_critical:
                for dep in component.dependencies:
                    if dep in self.components and not self.components[dep].is_critical:
                        warning_msg = f"Критичный компонент '{component_name}' зависит от некритичного '{dep}'"
                        logger.warning(f"⚠️ {warning_msg}")
        
        # Проверяем на циклические зависимости
        try:
            self._resolve_dependencies()
            logger.info("✅ Циклические зависимости не обнаружены")
        except ValueError as e:
            errors.append(f"Циклическая зависимость: {str(e)}")
        
        is_valid = len(errors) == 0
        
        if is_valid:
            logger.info("✅ Все зависимости валидны")
        else:
            logger.error(f"❌ Найдено {len(errors)} ошибок в зависимостях")
            for error in errors:
                logger.error(f"   • {error}")
        
        return is_valid, errors
    
    async def diagnose_component_health(self) -> Dict[str, Any]:
        """
        ✅ НОВЫЙ МЕТОД: Полная диагностика здоровья компонентов
        
        Returns:
            Dict с полной информацией о состоянии системы компонентов
        """
        diagnosis = {
            'timestamp': datetime.utcnow().isoformat(),
            'total_components': len(self.components),
            'components_by_status': {},
            'critical_components': {},
            'dependency_graph': {},
            'initialization_order': self.initialization_order.copy(),
            'health_score': 0,
            'recommendations': []
        }
        
        # Подсчет компонентов по статусам
        status_counts = {}
        critical_ready = 0
        critical_total = 0
        
        for name, component in self.components.items():
            status = component.status.value
            status_counts[status] = status_counts.get(status, 0) + 1
            
            if component.is_critical:
                critical_total += 1
                if component.status == ComponentStatus.READY:
                    critical_ready += 1
            
            # Строим граф зависимостей
            diagnosis['dependency_graph'][name] = {
                'dependencies': component.dependencies.copy(),
                'status': status,
                'is_critical': component.is_critical,
                'error': component.error,
                'retry_count': component.retry_count
            }
        
        diagnosis['components_by_status'] = status_counts
        diagnosis['critical_components'] = {
            'ready': critical_ready,
            'total': critical_total,
            'percentage': (critical_ready / critical_total * 100) if critical_total > 0 else 0
        }
        
        # Вычисляем общий health score
        ready_count = status_counts.get('ready', 0)
        total_count = len(self.components)
        critical_health = diagnosis['critical_components']['percentage']
        
        diagnosis['health_score'] = int((ready_count / total_count * 50) + (critical_health * 0.5))
        
        # Генерируем рекомендации
        if critical_ready < critical_total:
            diagnosis['recommendations'].append("Критичные компоненты не готовы - требуется немедленное внимание")
        
        if status_counts.get('failed', 0) > 0:
            diagnosis['recommendations'].append(f"Есть {status_counts['failed']} неработающих компонентов")
        
        if diagnosis['health_score'] < 80:
            diagnosis['recommendations'].append("Низкий health score - проверьте статус компонентов")
        
        if not diagnosis['recommendations']:
            diagnosis['recommendations'].append("Система компонентов работает стабильно")
        
        return diagnosis
    
    async def initialize_all(self) -> Dict[str, bool]:
        """
        Инициализация всех компонентов в правильном порядке
        
        Returns:
            Dict[str, bool]: Результат инициализации каждого компонента
        """
        async with self._lock:
            logger.info("🚀 Начинаем инициализацию всех компонентов...")
            
            # Определяем порядок инициализации
            try:
                self.initialization_order = self._resolve_dependencies()
                logger.info(f"📋 Порядок инициализации: {self.initialization_order}")
            except ValueError as e:
                logger.error(f"❌ Ошибка разрешения зависимостей: {e}")
                return {}
            
            results = {}
            
            # Инициализируем компоненты по порядку
            for component_name in self.initialization_order:
                result = await self._initialize_component(component_name)
                results[component_name] = result
                
                # Если критичный компонент не инициализировался, останавливаемся
                component = self.components[component_name]
                if component.is_critical and not result:
                    logger.error(f"❌ Критичный компонент {component_name} не инициализирован")
                    break
            
            # Выводим итоговую статистику
            self._log_initialization_summary(results)
            return results
    
    async def _initialize_component(self, name: str) -> bool:
        """
        Инициализация конкретного компонента
        
        Args:
            name: Имя компонента
            
        Returns:
            bool: Успешность инициализации
        """
        component = self.components.get(name)
        if not component:
            logger.error(f"❌ Компонент {name} не найден")
            return False
        
        # Проверяем зависимости
        for dep in component.dependencies:
            dep_component = self.components.get(dep)
            if not dep_component or dep_component.status != ComponentStatus.READY:
                logger.error(f"❌ Зависимость {dep} для {name} не готова")
                component.status = ComponentStatus.FAILED
                component.error = f"Dependency {dep} not ready"
                return False
        
        # Пытаемся инициализировать
        for attempt in range(component.max_retries):
            try:
                logger.info(f"🔧 Инициализируем {name} (попытка {attempt + 1}/{component.max_retries})")
                component.status = ComponentStatus.INITIALIZING
                
                # Получаем функцию инициализации
                initializer = getattr(self, f"_init_{name}", None)
                if not initializer:
                    raise AttributeError(f"Initializer for {name} not found")
                
                # Выполняем инициализацию
                if asyncio.iscoroutinefunction(initializer):
                    instance = await initializer()
                else:
                    instance = initializer()
                
                # Успешная инициализация
                component.instance = instance
                component.status = ComponentStatus.READY
                component.error = None
                component.retry_count = attempt + 1
                
                logger.info(f"✅ Компонент {name} инициализирован успешно")
                return True
                
            except Exception as e:
                error_msg = f"Ошибка инициализации {name}: {str(e)}"
                logger.warning(f"⚠️ {error_msg}")
                component.error = error_msg
                component.retry_count = attempt + 1
                
                # Если это последняя попытка
                if attempt == component.max_retries - 1:
                    component.status = ComponentStatus.FAILED
                    logger.error(f"❌ Компонент {name} не удалось инициализировать после {component.max_retries} попыток")
                    return False
                
                # Ждем перед следующей попыткой
                await asyncio.sleep(1)
        
        return False
    
    def get_component(self, name: str) -> Any:
        """
        Получение экземпляра компонента
        
        Args:
            name: Имя компонента
            
        Returns:
            Any: Экземпляр компонента или None
        """
        component = self.components.get(name)
        if component and component.status == ComponentStatus.READY:
            return component.instance
        return None
    
    def get_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Получение статуса всех компонентов
        
        Returns:
            Dict: Статус каждого компонента
        """
        status = {}
        for name, component in self.components.items():
            status[name] = {
                'status': component.status.value,
                'is_critical': component.is_critical,
                'dependencies': component.dependencies,
                'retry_count': component.retry_count,
                'error': component.error,
                'has_instance': component.instance is not None
            }
        return status
    
    async def restart_component(self, name: str) -> bool:
        """
        Перезапуск компонента
        
        Args:
            name: Имя компонента
            
        Returns:
            bool: Успешность перезапуска
        """
        component = self.components.get(name)
        if not component:
            return False
        
        logger.info(f"🔄 Перезапускаем компонент: {name}")
        
        # Сбрасываем состояние
        component.status = ComponentStatus.NOT_INITIALIZED
        component.instance = None
        component.error = None
        component.retry_count = 0
        
        # Инициализируем заново
        return await self._initialize_component(name)
    
    def _log_initialization_summary(self, results: Dict[str, bool]):
        """
        Вывод итоговой статистики инициализации
        
        Args:
            results: Результаты инициализации
        """
        total = len(results)
        success = sum(1 for r in results.values() if r)
        failed = total - success
        
        logger.info("=" * 50)
        logger.info("📊 ИТОГИ ИНИЦИАЛИЗАЦИИ КОМПОНЕНТОВ")
        logger.info("=" * 50)
        logger.info(f"📈 Всего компонентов: {total}")
        logger.info(f"✅ Успешно: {success}")
        logger.info(f"❌ Не удалось: {failed}")
        logger.info("=" * 50)
        
        # Детальная информация
        for name, success in results.items():
            component = self.components[name]
            status_icon = "✅" if success else "❌"
            critical_icon = "🔥" if component.is_critical else "📦"
            
            logger.info(f"{status_icon} {critical_icon} {name}")
            if not success and component.error:
                logger.info(f"    └─ Ошибка: {component.error}")
        
        logger.info("=" * 50)
        
    def is_ready(self, component_name: str) -> bool:
        """
        Проверка готовности компонента к работе
        
        Метод проверяет, что компонент:
        1. Зарегистрирован в системе
        2. Имеет статус READY
        3. Успешно инициализирован
        
        Args:
            component_name (str): Имя компонента для проверки
            
        Returns:
            bool: True если компонент готов к работе, False в противном случае
            
        Raises:
            None: Метод никогда не вызывает исключения для обеспечения стабильности
            
        Example:
            >>> component_manager.is_ready('exchange')
            True
            >>> component_manager.is_ready('non_existent')
            False
        """
        try:
            # Проверка существования компонента
            if component_name not in self.components:
                logger.warning(f"⚠️ Компонент '{component_name}' не зарегистрирован в системе")
                return False
            
            # Получение информации о компоненте
            component_info = self.components[component_name]
            
            # Проверка статуса
            is_component_ready = component_info.status == ComponentStatus.READY
            
            # Дополнительная проверка критичности
            if not is_component_ready and component_info.is_critical:
                logger.error(f"❌ Критичный компонент '{component_name}' не готов. "
                            f"Статус: {component_info.status.value}")
            elif not is_component_ready:
                logger.warning(f"⚠️ Компонент '{component_name}' не готов. "
                             f"Статус: {component_info.status.value}")
            else:
                logger.debug(f"✅ Компонент '{component_name}' готов к работе")
            
            return is_component_ready
            
        except Exception as e:
            logger.error(f"❌ Ошибка при проверке компонента '{component_name}': {str(e)}")
            return False
    
    def get_component_status(self, component_name: str) -> Optional[ComponentStatus]:
        """
        Получение текущего статуса конкретного компонента
        
        Args:
            component_name (str): Имя компонента
            
        Returns:
            Optional[ComponentStatus]: Статус компонента или None если не найден
        """
        if component_name not in self.components:
            logger.debug(f"🔍 Компонент '{component_name}' не найден")
            return None
        
        return self.components[component_name].status
    
    def get_ready_components(self) -> List[str]:
        """
        Получение списка всех готовых компонентов
        
        Returns:
            List[str]: Список имен компонентов со статусом READY
        """
        ready_components = []
        for name, component in self.components.items():
            if component.status == ComponentStatus.READY:
                ready_components.append(name)
        
        return ready_components
    
    def get_failed_components(self) -> List[str]:
        """
        Получение списка всех проблемных компонентов
        
        Returns:
            List[str]: Список имен компонентов со статусом FAILED
        """
        failed_components = []
        for name, component in self.components.items():
            if component.status == ComponentStatus.FAILED:
                failed_components.append(name)
        
        return failed_components
    
    def validate_critical_components(self) -> Tuple[bool, List[str]]:
        """
        Проверка готовности всех критичных компонентов
        
        Returns:
            Tuple[bool, List[str]]: (Все ли критичные готовы, Список неготовых критичных)
        """
        critical_not_ready = []
        
        for name, component in self.components.items():
            if component.is_critical and component.status != ComponentStatus.READY:
                critical_not_ready.append(name)
        
        all_critical_ready = len(critical_not_ready) == 0
        
        if not all_critical_ready:
            logger.error(f"❌ Критичные компоненты не готовы: {critical_not_ready}")
        else:
            logger.info("✅ Все критичные компоненты готовы")
        
        return all_critical_ready, critical_not_ready

# Глобальный менеджер компонентов
component_manager = ComponentManager()