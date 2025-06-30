"""
Модуль для имитации человеческого поведения при торговле
Защита от обнаружения ботов
"""
import asyncio
import sys
import random
import time
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta

from ..core.config import config

logger = logging.getLogger(__name__)

class HumanBehaviorMixin:
    """Миксин для добавления человеческого поведения"""
    
    def _init_human_behavior(self):
        """Инициализация параметров человеческого поведения"""
        self.enable_human_mode = config.ENABLE_HUMAN_MODE
        self.min_delay = config.MIN_DELAY_SECONDS
        self.max_delay = config.MAX_DELAY_SECONDS
        
        # Время последнего действия
        self.last_action_time = None
        
        # Счетчики для паттернов
        self.actions_count = 0
        self.session_start = datetime.now()
        
        # Паттерны активности
        self.activity_patterns = {
            'morning': (6, 12),    # Утренняя сессия
            'afternoon': (12, 18), # Дневная сессия
            'evening': (18, 23),   # Вечерняя сессия
            'night': (23, 6)       # Ночная сессия (меньше активности)
        }
    
    async def micro_delay(self):
        """Микро-задержка для быстрых операций"""
        if self.enable_human_mode:
            await asyncio.sleep(random.uniform(0.1, 0.5))
    
    async def human_delay(self, action_type: str = "default"):
        """Человеческая задержка между действиями"""
        if not self.enable_human_mode:
            return
        
        # Базовая задержка
        delay = random.uniform(self.min_delay, self.max_delay)
        
        # Модификаторы задержки в зависимости от типа действия
        modifiers = {
            'order': 1.5,      # Больше думаем перед ордером
            'cancel': 0.8,     # Быстрее отменяем
            'check': 0.5,      # Быстрая проверка
            'analysis': 2.0,   # Долгий анализ
            'panic': 0.3       # Паника - быстрые действия
        }
        
        modifier = modifiers.get(action_type, 1.0)
        delay *= modifier
        
        # Добавляем вариативность по времени суток
        current_hour = datetime.now().hour
        if 23 <= current_hour or current_hour < 6:
            # Ночью медленнее
            delay *= random.uniform(1.5, 2.5)
        
        # Случайные микро-паузы
        if random.random() < 0.1:
            delay += random.uniform(0.5, 2.0)
        
        logger.debug(f"Человеческая задержка: {delay:.2f}с для действия '{action_type}'")
        await asyncio.sleep(delay)
        
        self.last_action_time = datetime.now()
        self.actions_count += 1
    
    async def think_before_action(self):
        """Имитация размышлений перед важным действием"""
        if not self.enable_human_mode:
            return
        
        # Иногда долго думаем
        if random.random() < 0.15:
            think_time = random.uniform(3, 8)
            logger.debug(f"Долгое размышление: {think_time:.1f}с")
            await asyncio.sleep(think_time)
        else:
            await self.human_delay('analysis')
    
    def should_hesitate(self) -> bool:
        """Иногда сомневаемся и отменяем действие"""
        if not self.enable_human_mode:
            return False
        
        # 5% шанс передумать
        return random.random() < 0.05
    
    def humanize_amount(self, amount: float) -> float:
        """Человеческое округление количества"""
        if not self.enable_human_mode:
            return amount
        
        # Люди не используют слишком точные числа
        if amount > 1000:
            # Округляем до 50 или 100
            return round(amount / 50) * 50
        elif amount > 100:
            # Округляем до 10
            return round(amount / 10) * 10
        elif amount > 10:
            # Округляем до 1
            return round(amount)
        else:
            # Округляем до 0.1
            return round(amount, 1)
    
    def humanize_price(self, price: float, symbol: str) -> float:
        """Человеческое округление цены"""
        if not self.enable_human_mode:
            return price
        
        # Для BTC округляем до долларов
        if 'BTC' in symbol:
            return round(price)
        # Для остальных - до центов
        else:
            return round(price, 2)
    
    async def simulate_mouse_movement(self):
        """Имитация движения мыши (через случайные задержки)"""
        if not self.enable_human_mode:
            return
        
        # Случайные микро-паузы как будто двигаем мышь
        movements = random.randint(2, 5)
        for _ in range(movements):
            await asyncio.sleep(random.uniform(0.1, 0.3))
    
    async def simulate_typing(self, text_length: int):
        """Имитация набора текста"""
        if not self.enable_human_mode:
            return
        
        # ~200-300 символов в минуту для обычного человека
        typing_speed = random.uniform(200, 300) / 60  # символов в секунду
        typing_time = text_length / typing_speed
        
        # Добавляем вариативность
        typing_time *= random.uniform(0.8, 1.2)
        
        await asyncio.sleep(typing_time)
    
    def should_take_break(self) -> bool:
        """Проверка, нужен ли перерыв"""
        if not self.enable_human_mode:
            return False
        
        # Проверяем время с начала сессии
        session_duration = (datetime.now() - self.session_start).total_seconds() / 3600
        
        # После 2 часов работы - вероятность перерыва растет
        if session_duration > 2:
            break_probability = min(0.3, (session_duration - 2) * 0.1)
            return random.random() < break_probability
        
        # Случайные короткие перерывы
        return random.random() < 0.02
    
    async def take_break(self):
        """Взять перерыв"""
        if not self.enable_human_mode:
            return
        
        # Короткий перерыв (1-5 минут) или длинный (10-30 минут)
        if random.random() < 0.7:
            # Короткий
            break_time = random.uniform(60, 300)
            logger.info(f"Короткий перерыв: {break_time/60:.1f} минут")
        else:
            # Длинный
            break_time = random.uniform(600, 1800)
            logger.info(f"Длинный перерыв: {break_time/60:.1f} минут")
        
        await asyncio.sleep(break_time)
        
        # Сбрасываем счетчики после перерыва
        self.session_start = datetime.now()
        self.actions_count = 0
    
    def add_human_errors(self, value: float, error_rate: float = 0.01) -> float:
        """Добавление человеческих ошибок в значения"""
        if not self.enable_human_mode:
            return value
        
        # Изредка делаем небольшие ошибки
        if random.random() < error_rate:
            # Ошибка в пределах 1-3%
            error = random.uniform(-0.03, 0.03)
            return value * (1 + error)
        
        return value
    
    def get_activity_level(self) -> float:
        """Получить уровень активности в зависимости от времени"""
        current_hour = datetime.now().hour
        
        # Ночью меньше активности
        if 0 <= current_hour < 6:
            return random.uniform(0.2, 0.4)
        # Утром нарастает
        elif 6 <= current_hour < 9:
            return random.uniform(0.5, 0.7)
        # День - максимум
        elif 9 <= current_hour < 18:
            return random.uniform(0.8, 1.0)
        # Вечер - снижается
        elif 18 <= current_hour < 22:
            return random.uniform(0.6, 0.8)
        # Поздний вечер
        else:
            return random.uniform(0.3, 0.5)
    
    async def simulate_reading_time(self, text_length: int):
        """Имитация времени чтения"""
        if not self.enable_human_mode:
            return
        
        # ~200-250 слов в минуту для среднего человека
        words = text_length / 5  # примерно 5 символов на слово
        reading_speed = random.uniform(200, 250) / 60  # слов в секунду
        reading_time = words / reading_speed
        
        await asyncio.sleep(reading_time * random.uniform(0.8, 1.2))