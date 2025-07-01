#!/usr/bin/env python3
"""
Trading RL Agent для обучения с подкреплением - БАЗОВАЯ РЕАЛИЗАЦИЯ
================================================================
Файл: src/ml/models/rl_agent.py

✅ ИСПРАВЛЯЕТ: No module named 'src.ml.models.rl_agent'
✅ Базовая реализация Q-Learning для торговли
✅ Полная совместимость с существующей системой
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any, Union
from datetime import datetime, timedelta
import pickle
import json
from pathlib import Path
import logging
from dataclasses import dataclass
from enum import Enum
import random
from collections import deque


# Безопасные импорты
try:
    from ...core.unified_config import unified_config
    CONFIG_AVAILABLE = True
except ImportError:
    unified_config = None
    CONFIG_AVAILABLE = False

try:
    from ...logging.smart_logger import SmartLogger
    logger = SmartLogger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)
    
from enum import IntEnum


class TradingAction(IntEnum):
    """
    Торговые действия для RL агента
    ✅ ИСПРАВЛЕНО: правильный порядок значений для тестов
    """
    SELL = 0      # ✅ Продажа = 0 (как ожидается в тесте)
    HOLD = 1      # ✅ Удержание = 1 
    BUY = 2       # ✅ Покупка = 2

    def __str__(self):
        return self.name
    
    def get_action_name(self):
        """Получить название действия"""
        return {
            0: "SELL",
            1: "HOLD", 
            2: "BUY"
        }.get(self.value, "UNKNOWN")

@dataclass
class TradingState:
    """Состояние торгового окружения"""
    price: float
    volume: float
    rsi: float
    macd: float
    bb_position: float
    portfolio_value: float
    position_size: float
    timestamp: datetime

@dataclass
class TradingReward:
    """Награда за торговое действие"""
    profit: float
    penalty: float
    total_reward: float
    risk_penalty: float
    transaction_cost: float

class TradingEnvironment:
    """
    Торговое окружение для RL агента
    """
    
    def __init__(self, 
                 data: pd.DataFrame,
                 initial_balance: float = 10000.0,
                 transaction_cost: float = 0.001,
                 max_position_size: float = 1.0):
        """
        Инициализация торгового окружения
        
        Args:
            data: Исторические данные OHLCV
            initial_balance: Начальный баланс
            transaction_cost: Комиссия за сделку
            max_position_size: Максимальный размер позиции
        """
        self.data = data.copy()
        self.initial_balance = initial_balance
        self.transaction_cost = transaction_cost
        self.max_position_size = max_position_size
        
        # Состояние окружения
        self.current_step = 0
        self.balance = initial_balance
        self.position = 0.0  # Текущая позиция
        self.total_trades = 0
        self.winning_trades = 0
        
        # История
        self.portfolio_history = []
        self.action_history = []
        self.reward_history = []
        
        logger.info("✅ TradingEnvironment инициализирован")
    
    def reset(self) -> np.ndarray:
        """Сброс окружения к начальному состоянию"""
        self.current_step = 0
        self.balance = self.initial_balance
        self.position = 0.0
        self.total_trades = 0
        self.winning_trades = 0
        
        self.portfolio_history = []
        self.action_history = []
        self.reward_history = []
        
        return self._get_state()
    
    def _get_state(self) -> np.ndarray:
        """Получение текущего состояния"""
        if self.current_step >= len(self.data):
            return np.zeros(8)  # Пустое состояние
        
        row = self.data.iloc[self.current_step]
        
        # Нормализуем состояние
        state = np.array([
            row.get('close', 0) / 100.0,  # Нормализованная цена
            row.get('volume', 0) / 1000000.0,  # Нормализованный объем
            row.get('rsi', 50) / 100.0,  # RSI [0,1]
            (row.get('macd', 0) + 100) / 200.0,  # MACD нормализованный
            row.get('bb_position', 0.5),  # BB позиция [0,1]
            self.balance / self.initial_balance,  # Нормализованный баланс
            self.position / self.max_position_size,  # Нормализованная позиция
            self.current_step / len(self.data)  # Временная позиция
        ])
        
        return state
    
    def step(self, action: int) -> Tuple[np.ndarray, float, bool, Dict]:
        """
        Выполнение действия в окружении
        
        Args:
            action: Действие (0=SELL, 1=HOLD, 2=BUY)
            
        Returns:
            Tuple: (new_state, reward, done, info)
        """
        if self.current_step >= len(self.data) - 1:
            return self._get_state(), 0.0, True, {}
        
        current_price = self.data.iloc[self.current_step]['close']
        next_price = self.data.iloc[self.current_step + 1]['close']
        
        # Выполняем действие
        reward = self._execute_action(action, current_price, next_price)
        
        # Обновляем состояние
        self.current_step += 1
        
        # Записываем историю
        portfolio_value = self.balance + self.position * next_price
        self.portfolio_history.append(portfolio_value)
        self.action_history.append(action)
        self.reward_history.append(reward)
        
        # Проверяем завершение эпизода
        done = (self.current_step >= len(self.data) - 1) or (portfolio_value <= 0)
        
        info = {
            'portfolio_value': portfolio_value,
            'balance': self.balance,
            'position': self.position,
            'total_trades': self.total_trades,
            'win_rate': self.winning_trades / max(self.total_trades, 1)
        }
        
        return self._get_state(), reward, done, info
    
    def _execute_action(self, action: int, current_price: float, next_price: float) -> float:
        """Выполнение торгового действия"""
        action_enum = TradingAction(action)
        reward = 0.0
        
        price_change = (next_price - current_price) / current_price
        
        if action_enum == TradingAction.BUY and self.position < self.max_position_size:
            # Покупка
            trade_size = min(0.1, self.max_position_size - self.position)
            cost = trade_size * current_price * (1 + self.transaction_cost)
            
            if self.balance >= cost:
                self.balance -= cost
                self.position += trade_size
                self.total_trades += 1
                
                # Награда за прибыльную покупку
                reward = trade_size * price_change * 100
                if price_change > 0:
                    self.winning_trades += 1
        
        elif action_enum == TradingAction.SELL and self.position > 0:
            # Продажа
            trade_size = min(0.1, self.position)
            revenue = trade_size * current_price * (1 - self.transaction_cost)
            
            self.balance += revenue
            self.position -= trade_size
            self.total_trades += 1
            
            # Награда за прибыльную продажу (обратная к движению цены)
            reward = trade_size * (-price_change) * 100
            if price_change < 0:
                self.winning_trades += 1
        
        else:
            # HOLD или невозможное действие
            # Небольшая награда за удержание при неопределенности
            reward = -0.01  # Штраф за бездействие
        
        # Дополнительные штрафы/награды
        portfolio_value = self.balance + self.position * next_price
        
        # Штраф за убытки
        if portfolio_value < self.initial_balance * 0.9:
            reward -= 1.0
        
        # Награда за рост портфеля
        if portfolio_value > self.initial_balance * 1.1:
            reward += 0.5
        
        return reward

class TradingRLAgent:
    """
    ✅ ИСПРАВЛЕННЫЙ: RL агент для торговли с использованием Q-Learning
    
    Базовая реализация агента обучения с подкреплением для торговли.
    Использует Q-Learning для изучения оптимальной торговой стратегии.
    """
    
    def __init__(self,
                 state_size: int = 8,
                 action_size: int = 3,
                 learning_rate: float = 0.001,
                 epsilon: float = 1.0,
                 epsilon_decay: float = 0.995,
                 epsilon_min: float = 0.01,
                 gamma: float = 0.95,
                 memory_size: int = 10000):
        """
        Инициализация RL агента
        
        Args:
            state_size: Размер вектора состояния
            action_size: Количество возможных действий
            learning_rate: Скорость обучения
            epsilon: Начальная вероятность случайного действия
            epsilon_decay: Коэффициент уменьшения epsilon
            epsilon_min: Минимальное значение epsilon
            gamma: Коэффициент дисконтирования
            memory_size: Размер буфера опыта
        """
        self.state_size = state_size
        self.action_size = action_size
        self.learning_rate = learning_rate
        self.epsilon = epsilon
        self.epsilon_decay = epsilon_decay
        self.epsilon_min = epsilon_min
        self.gamma = gamma
        
        # Q-table для простого Q-Learning
        self.q_table = {}
        
        # Буфер опыта
        self.memory = deque(maxlen=memory_size)
        
        # Метрики
        self.training_history = []
        self.is_trained = False
        
        logger.info("✅ TradingRLAgent инициализирован")
    
    def _discretize_state(self, state: np.ndarray) -> str:
        """Дискретизация состояния для Q-table"""
        # Простая дискретизация: округляем до 1 знака после запятой
        discretized = np.round(state, 1)
        return str(discretized.tolist())
    
    def get_action(self, state: np.ndarray, training: bool = True) -> int:
        """
        Выбор действия на основе epsilon-greedy стратегии
        
        Args:
            state: Текущее состояние
            training: Режим обучения
            
        Returns:
            Выбранное действие (0, 1, 2)
        """
        state_key = self._discretize_state(state)
        
        # Инициализируем Q-значения для нового состояния
        if state_key not in self.q_table:
            self.q_table[state_key] = np.zeros(self.action_size)
        
        # Epsilon-greedy выбор действия
        if training and random.random() < self.epsilon:
            return random.randint(0, self.action_size - 1)
        else:
            return np.argmax(self.q_table[state_key])
    
    def remember(self, state: np.ndarray, action: int, reward: float, 
                 next_state: np.ndarray, done: bool):
        """Запоминание опыта"""
        self.memory.append((state, action, reward, next_state, done))
    
    def replay(self, batch_size: int = 32):
        """Обучение на батче из буфера опыта"""
        if len(self.memory) < batch_size:
            return
        
        # Выбираем случайный батч
        batch = random.sample(self.memory, min(batch_size, len(self.memory)))
        
        for state, action, reward, next_state, done in batch:
            state_key = self._discretize_state(state)
            next_state_key = self._discretize_state(next_state)
            
            # Инициализируем Q-значения если нужно
            if state_key not in self.q_table:
                self.q_table[state_key] = np.zeros(self.action_size)
            if next_state_key not in self.q_table:
                self.q_table[next_state_key] = np.zeros(self.action_size)
            
            # Q-Learning обновление
            target = reward
            if not done:
                target += self.gamma * np.max(self.q_table[next_state_key])
            
            # Обновляем Q-значение
            current_q = self.q_table[state_key][action]
            self.q_table[state_key][action] = current_q + self.learning_rate * (target - current_q)
        
        # Уменьшаем epsilon
        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay
    
    def train(self, 
              data: pd.DataFrame,
              episodes: int = 100,
              max_steps_per_episode: int = None,
              validation_split: float = 0.2) -> Dict[str, Any]:
        """
        Обучение RL агента
        
        Args:
            data: Исторические данные для обучения
            episodes: Количество эпизодов обучения
            max_steps_per_episode: Максимальное количество шагов за эпизод
            validation_split: Доля данных для валидации
            
        Returns:
            Результаты обучения
        """
        try:
            logger.info(f"🎯 Начало обучения RL агента на {episodes} эпизодах...")
            
            # Разделяем данные
            split_idx = int(len(data) * (1 - validation_split))
            train_data = data.iloc[:split_idx].copy()
            val_data = data.iloc[split_idx:].copy()
            
            # Создаем окружение
            env = TradingEnvironment(train_data)
            
            # Метрики обучения
            episode_rewards = []
            episode_portfolio_values = []
            
            max_steps = max_steps_per_episode or len(train_data) - 1
            
            for episode in range(episodes):
                state = env.reset()
                episode_reward = 0
                
                for step in range(max_steps):
                    # Выбираем действие
                    action = self.get_action(state, training=True)
                    
                    # Выполняем действие
                    next_state, reward, done, info = env.step(action)
                    
                    # Запоминаем опыт
                    self.remember(state, action, reward, next_state, done)
                    
                    episode_reward += reward
                    state = next_state
                    
                    if done:
                        break
                
                # Обучаем агента
                self.replay()
                
                # Записываем метрики
                episode_rewards.append(episode_reward)
                final_portfolio = info.get('portfolio_value', env.initial_balance)
                episode_portfolio_values.append(final_portfolio)
                
                # Логируем прогресс
                if episode % 10 == 0:
                    avg_reward = np.mean(episode_rewards[-10:])
                    avg_portfolio = np.mean(episode_portfolio_values[-10:])
                    logger.info(f"Эпизод {episode}/{episodes}: "
                               f"Reward={avg_reward:.2f}, "
                               f"Portfolio=${avg_portfolio:.2f}, "
                               f"Epsilon={self.epsilon:.3f}")
            
            # Валидация
            val_results = self._validate(val_data)
            
            # Результаты обучения
            training_results = {
                'episodes_completed': episodes,
                'final_epsilon': self.epsilon,
                'q_table_size': len(self.q_table),
                'avg_episode_reward': np.mean(episode_rewards),
                'final_portfolio_value': episode_portfolio_values[-1],
                'total_return': (episode_portfolio_values[-1] / env.initial_balance - 1) * 100,
                'validation_results': val_results,
                'episode_rewards': episode_rewards,
                'episode_portfolio_values': episode_portfolio_values
            }
            
            self.training_history.append({
                'timestamp': datetime.now(),
                'results': training_results,
                'episodes': episodes
            })
            
            self.is_trained = True
            
            logger.info(f"✅ Обучение завершено!")
            logger.info(f"📊 Финальная доходность: {training_results['total_return']:.2f}%")
            logger.info(f"📊 Размер Q-table: {training_results['q_table_size']}")
            
            return training_results
            
        except Exception as e:
            logger.error(f"❌ Ошибка обучения RL агента: {e}")
            return {'success': False, 'error': str(e)}
    
    def _validate(self, val_data: pd.DataFrame) -> Dict[str, Any]:
        """Валидация агента на отложенных данных"""
        try:
            env = TradingEnvironment(val_data)
            state = env.reset()
            
            total_reward = 0
            actions_taken = []
            
            for step in range(len(val_data) - 1):
                action = self.get_action(state, training=False)
                next_state, reward, done, info = env.step(action)
                
                actions_taken.append(action)
                total_reward += reward
                state = next_state
                
                if done:
                    break
            
            final_value = info.get('portfolio_value', env.initial_balance)
            total_return = (final_value / env.initial_balance - 1) * 100
            
            return {
                'total_reward': total_reward,
                'final_portfolio_value': final_value,
                'total_return': total_return,
                'total_trades': info.get('total_trades', 0),
                'win_rate': info.get('win_rate', 0),
                'actions_distribution': {
                    'SELL': actions_taken.count(0),
                    'HOLD': actions_taken.count(1),
                    'BUY': actions_taken.count(2)
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка валидации: {e}")
            return {'error': str(e)}
    
    def predict(self, state: Union[np.ndarray, pd.Series, Dict]) -> Dict[str, Any]:
        """
        Предсказание действия для данного состояния
        
        Args:
            state: Состояние для предсказания
            
        Returns:
            Словарь с предсказанием
        """
        try:
            # Преобразуем в numpy array
            if isinstance(state, pd.Series):
                state_array = state.values
            elif isinstance(state, dict):
                # Предполагаем стандартный порядок признаков
                state_array = np.array([
                    state.get('close', 0),
                    state.get('volume', 0),
                    state.get('rsi', 50),
                    state.get('macd', 0),
                    state.get('bb_position', 0.5),
                    state.get('portfolio_value', 10000),
                    state.get('position', 0),
                    state.get('timestamp', 0)
                ])
            else:
                state_array = np.array(state)
            
            # Нормализуем состояние
            if len(state_array) != self.state_size:
                # Дополняем или обрезаем до нужного размера
                if len(state_array) < self.state_size:
                    state_array = np.pad(state_array, (0, self.state_size - len(state_array)))
                else:
                    state_array = state_array[:self.state_size]
            
            # Получаем действие
            action = self.get_action(state_array, training=False)
            
            # Получаем Q-значения
            state_key = self._discretize_state(state_array)
            if state_key in self.q_table:
                q_values = self.q_table[state_key].tolist()
                confidence = max(q_values) / (sum(q_values) + 1e-8)
            else:
                q_values = [0.33, 0.34, 0.33]
                confidence = 0.5
            
            action_names = {0: 'SELL', 1: 'HOLD', 2: 'BUY'}
            
            return {
                'action': action,
                'action_name': action_names[action],
                'confidence': confidence,
                'q_values': q_values,
                'state_known': state_key in self.q_table,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка предсказания: {e}")
            return {
                'action': 1,  # HOLD по умолчанию
                'action_name': 'HOLD',
                'confidence': 0.5,
                'error': str(e)
            }
    
    def save_model(self, filepath: str):
        """Сохранение модели"""
        try:
            model_data = {
                'q_table': self.q_table,
                'state_size': self.state_size,
                'action_size': self.action_size,
                'learning_rate': self.learning_rate,
                'epsilon': self.epsilon,
                'epsilon_decay': self.epsilon_decay,
                'epsilon_min': self.epsilon_min,
                'gamma': self.gamma,
                'training_history': self.training_history,
                'is_trained': self.is_trained,
                'timestamp': datetime.now().isoformat()
            }
            
            with open(filepath, 'wb') as f:
                pickle.dump(model_data, f)
            
            logger.info(f"✅ RL модель сохранена: {filepath}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения модели: {e}")
    
    def load_model(self, filepath: str):
        """Загрузка модели"""
        try:
            with open(filepath, 'rb') as f:
                model_data = pickle.load(f)
            
            self.q_table = model_data['q_table']
            self.state_size = model_data['state_size']
            self.action_size = model_data['action_size']
            self.learning_rate = model_data['learning_rate']
            self.epsilon = model_data['epsilon']
            self.epsilon_decay = model_data['epsilon_decay']
            self.epsilon_min = model_data['epsilon_min']
            self.gamma = model_data['gamma']
            self.training_history = model_data.get('training_history', [])
            self.is_trained = model_data.get('is_trained', True)
            
            logger.info(f"✅ RL модель загружена: {filepath}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки модели: {e}")
    
    def get_model_info(self) -> Dict[str, Any]:
        """Получение информации о модели"""
        return {
            'model_type': 'Q-Learning',
            'state_size': self.state_size,
            'action_size': self.action_size,
            'learning_rate': self.learning_rate,
            'epsilon': self.epsilon,
            'gamma': self.gamma,
            'q_table_size': len(self.q_table),
            'is_trained': self.is_trained,
            'training_episodes': len(self.training_history)
        }

# ✅ ЭКСПОРТ
__all__ = [
    'TradingRLAgent',
    'TradingEnvironment',
    'TradingAction',
    'TradingState',
    'TradingReward'
]