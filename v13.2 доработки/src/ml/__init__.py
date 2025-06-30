#!/usr/bin/env python3
"""
ML модуль для торгового бота - ПОЛНАЯ ВЕРСИЯ
===========================================
Файл: src/ml/__init__.py

✅ Полная интеграция всех ML компонентов
✅ Безопасные импорты с заглушками  
✅ Оптимизация памяти и производительности
✅ Совместимость со всей системой
"""

import logging
import warnings
import os
warnings.filterwarnings('ignore')

# Подавляем TensorFlow логи
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

logger = logging.getLogger(__name__)

# =================================================================
# ПРОВЕРКА БАЗОВЫХ ЗАВИСИМОСТЕЙ
# =================================================================

# NumPy
try:
    import numpy as np
    NUMPY_AVAILABLE = True
    logger.info("✅ NumPy импортирован")
except ImportError:
    logger.error("❌ NumPy не установлен - критическая зависимость!")
    NUMPY_AVAILABLE = False
    np = None

# Pandas
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
    logger.info("✅ Pandas импортирован")
except ImportError:
    logger.error("❌ Pandas не установлен - критическая зависимость!")
    PANDAS_AVAILABLE = False
    pd = None

# Scikit-learn
try:
    import sklearn
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split
    SKLEARN_AVAILABLE = True
    logger.info("✅ scikit-learn доступен")
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.warning("⚠️ scikit-learn недоступен")

# TensorFlow
try:
    import tensorflow as tf
    TENSORFLOW_AVAILABLE = True
    logger.info("✅ TensorFlow доступен")
except ImportError:
    TENSORFLOW_AVAILABLE = False
    logger.warning("⚠️ TensorFlow недоступен")

# PyTorch
try:
    import torch
    TORCH_AVAILABLE = True
    logger.info("✅ PyTorch доступен")
except ImportError:
    TORCH_AVAILABLE = False
    logger.warning("⚠️ PyTorch недоступен")

# =================================================================
# ИМПОРТ ОСНОВНЫХ ML КОМПОНЕНТОВ
# =================================================================

# Feature Engineering - НОВЫЙ МОДУЛЬ
try:
    # ✅ ИСПРАВЛЕНО: импорт из правильной директории features
    from .features.feature_engineering import FeatureEngineer, FeatureConfig
    FEATURE_ENGINEERING_AVAILABLE = True
    logger.info("✅ FeatureEngineer импортирован успешно")
except ImportError as e:
    logger.warning(f"⚠️ FeatureEngineer недоступен: {e}")
    FEATURE_ENGINEERING_AVAILABLE = False
    
    # Заглушки
    @dataclass
    class FeatureConfig:
        price_windows: List[int] = None
        volume_windows: List[int] = None
        volatility_windows: List[int] = None
        trend_windows: List[int] = None
        enable_technical_indicators: bool = True
        enable_price_features: bool = True
        enable_volume_features: bool = True
        enable_time_features: bool = True
        enable_lag_features: bool = True
        max_lag_periods: int = 10
        
        def __post_init__(self):
            if self.price_windows is None:
                self.price_windows = [5, 10, 20, 50]
            if self.volume_windows is None:
                self.volume_windows = [5, 10, 20]
            if self.volatility_windows is None:
                self.volatility_windows = [10, 20, 50]
            if self.trend_windows is None:
                self.trend_windows = [10, 20, 50, 100]
    
    class FeatureEngineer:
        def __init__(self, config=None):
            self.config = config or FeatureConfig()
            self.is_fitted = False
            self.feature_names = []
        
        def create_features(self, df, symbol="BTCUSDT"):
            logger.warning("⚠️ FeatureEngineer работает в режиме заглушки")
            return df
        
        def extract_features(self, df, symbol="BTCUSDT", **kwargs):
            return {
                'features': df,
                'feature_names': [],
                'symbol': symbol,
                'rows_count': len(df),
                'features_count': 0,
                'is_fitted': False,
                'test_mode': True
            }
        
        def transform(self, df, symbol="BTCUSDT"):
            return df
        
        def get_feature_importance(self, model=None, method='correlation'):
            return pd.DataFrame() if pd else None
    
    # Алиас для обратной совместимости
    FeatureEngineering = FeatureEngineer

# Direction Classifier - НОВЫЙ МОДУЛЬ
try:
    from .models.direction_classifier import DirectionClassifier, DirectionClassifierLight
    DIRECTION_CLASSIFIER_AVAILABLE = True
    logger.info("✅ DirectionClassifier импортирован успешно")
except ImportError as e:
    logger.warning(f"⚠️ DirectionClassifier недоступен: {e}")
    DIRECTION_CLASSIFIER_AVAILABLE = False
    
    # Заглушки
    class DirectionClassifier:
        def __init__(self, **kwargs):
            self.is_fitted = False
            self.model_type = kwargs.get('model_type', 'random_forest')
            self.forecast_horizon = kwargs.get('forecast_horizon', 5)
            self.threshold = kwargs.get('threshold', 0.01)
            self.confidence_threshold = kwargs.get('confidence_threshold', 0.6)
        
        def train(self, features_df, **kwargs):
            self.is_fitted = True
            return {
                'train_accuracy': 0.65,
                'test_accuracy': 0.62,
                'precision': 0.60,
                'recall': 0.63,
                'f1_score': 0.61,
                'confidence': 0.58,
                'test_mode': True
            }
        
        def predict(self, features_df):
            size = len(features_df) if hasattr(features_df, '__len__') else 1
            return {
                'predictions': [1] * size,
                'direction_labels': ['SIDEWAYS'] * size,
                'confidence': [0.6] * size,
                'probabilities': [[0.2, 0.6, 0.2]] * size,
                'high_confidence_count': size,
                'total_predictions': size,
                'test_mode': True
            }
        
        def predict_single(self, features):
            return {
                'prediction': 1,
                'direction': 'SIDEWAYS',
                'confidence': 0.6,
                'probabilities': [0.2, 0.6, 0.2],
                'test_mode': True
            }
        
        def evaluate(self, features_df, price_column='close'):
            return {
                'accuracy': 0.62,
                'precision': 0.60,
                'recall': 0.63,
                'f1_score': 0.61,
                'test_mode': True
            }
        
        def get_feature_importance(self):
            return pd.DataFrame() if pd else None
        
        def save_model(self, filepath):
            logger.info(f"Заглушка: сохранение модели в {filepath}")
        
        def load_model(self, filepath):
            logger.info(f"Заглушка: загрузка модели из {filepath}")
            self.is_fitted = True
        
        def get_model_info(self):
            return {
                'model_type': self.model_type,
                'is_fitted': self.is_fitted,
                'test_mode': True
            }
    
    DirectionClassifierLight = DirectionClassifier

# Price Level Regressor - НОВЫЙ МОДУЛЬ
try:
    from .models.price_regressor import PriceLevelRegressor
    PRICE_REGRESSOR_AVAILABLE = True
    logger.info("✅ PriceLevelRegressor импортирован успешно")
except ImportError as e:
    logger.warning(f"⚠️ PriceLevelRegressor недоступен: {e}")
    PRICE_REGRESSOR_AVAILABLE = False
    
    # Заглушка
    class PriceLevelRegressor:
        def __init__(self, **kwargs):
            self.is_fitted = False
            self.model_type = kwargs.get('model_type', 'random_forest')
            self.forecast_horizon = kwargs.get('forecast_horizon', 5)
            self.price_targets = kwargs.get('price_targets', ['future_close', 'support_level', 'resistance_level'])
        
        def train(self, features_df, **kwargs):
            self.is_fitted = True
            return {
                'models_trained': len(self.price_targets),
                'total_models': len(self.price_targets),
                'average_r2': 0.75,
                'average_rmse': 2.5,
                'average_mae': 1.8,
                'test_mode': True
            }
        
        def predict(self, features_df):
            size = len(features_df) if hasattr(features_df, '__len__') else 1
            return {
                'predictions': {
                    'future_close': [100.0] * size,
                    'support_level': [95.0] * size,
                    'resistance_level': [105.0] * size,
                    'volatility': [0.02] * size
                },
                'forecast_horizon': self.forecast_horizon,
                'valid_samples': size,
                'test_mode': True
            }
        
        def predict_single(self, features):
            return {
                'predictions': {
                    'future_close': 100.0,
                    'support_level': 95.0,
                    'resistance_level': 105.0,
                    'volatility': 0.02
                },
                'test_mode': True
            }
        
        def get_model_performance(self):
            return {
                'models_trained': len(self.price_targets),
                'average_r2': 0.75,
                'test_mode': True
            }
        
        def get_feature_importance(self, target_name=None):
            return pd.DataFrame() if pd else None
        
        def save_models(self, directory):
            logger.info(f"Заглушка: сохранение моделей в {directory}")
        
        def load_models(self, directory):
            logger.info(f"Заглушка: загрузка моделей из {directory}")
            self.is_fitted = True
        
        def get_model_info(self):
            return {
                'model_type': self.model_type,
                'is_fitted': self.is_fitted,
                'price_targets': self.price_targets,
                'test_mode': True
            }

# Trading RL Agent - НОВЫЙ МОДУЛЬ
try:
    from .models.rl_agent import TradingRLAgent, TradingEnvironment, TradingAction
    RL_AGENT_AVAILABLE = True
    logger.info("✅ TradingRLAgent импортирован успешно")
except ImportError as e:
    logger.warning(f"⚠️ TradingRLAgent недоступен: {e}")
    RL_AGENT_AVAILABLE = False
    
    # Заглушки
    class TradingAction:
        SELL = 0
        HOLD = 1
        BUY = 2
    
    class TradingEnvironment:
        def __init__(self, data, **kwargs):
            self.data = data
            self.initial_balance = kwargs.get('initial_balance', 10000.0)
        
        def reset(self):
            return [0.0] * 8
        
        def step(self, action):
            return [0.0] * 8, 0.0, True, {'portfolio_value': self.initial_balance}
    
    class TradingRLAgent:
        def __init__(self, **kwargs):
            self.is_trained = False
            self.state_size = kwargs.get('state_size', 8)
            self.action_size = kwargs.get('action_size', 3)
        
        def train(self, data, episodes=100, **kwargs):
            self.is_trained = True
            return {
                'episodes_completed': episodes,
                'final_epsilon': 0.1,
                'q_table_size': 100,
                'avg_episode_reward': 150.0,
                'final_portfolio_value': 11500.0,
                'total_return': 15.0,
                'test_mode': True
            }
        
        def predict(self, state):
            return {
                'action': 1,
                'action_name': 'HOLD',
                'confidence': 0.6,
                'q_values': [0.3, 0.6, 0.1],
                'test_mode': True
            }
        
        def get_action(self, state, **kwargs):
            return 1  # HOLD
        
        def save_model(self, filepath):
            logger.info(f"Заглушка: сохранение RL модели в {filepath}")
        
        def load_model(self, filepath):
            logger.info(f"Заглушка: загрузка RL модели из {filepath}")
            self.is_trained = True
        
        def get_model_info(self):
            return {
                'model_type': 'Q-Learning',
                'is_trained': self.is_trained,
                'state_size': self.state_size,
                'action_size': self.action_size,
                'test_mode': True
            }

# Strategy Selection - СУЩЕСТВУЮЩИЙ МОДУЛЬ
try:
    from .strategy_selection import AutoStrategySelector
    STRATEGY_SELECTION_AVAILABLE = True
    logger.info("✅ AutoStrategySelector доступен")
except ImportError as e:
    logger.warning(f"⚠️ AutoStrategySelector недоступен: {e}")
    STRATEGY_SELECTION_AVAILABLE = False
    
    # Заглушка
    class AutoStrategySelector:
        def __init__(self, *args, **kwargs):
            pass
        
        def select_best_strategy(self, *args, **kwargs):
            return 'trend_following'
        
        def get_strategy_recommendations(self, *args, **kwargs):
            return ['trend_following', 'mean_reversion', 'momentum']

# ML Trainer - СУЩЕСТВУЮЩИЙ МОДУЛЬ
try:
    from .training.trainer import MLTrainer
    ML_TRAINER_AVAILABLE = True
    logger.info("✅ MLTrainer доступен")
except ImportError as e:
    logger.warning(f"⚠️ MLTrainer недоступен: {e}")
    ML_TRAINER_AVAILABLE = False
    MLTrainer = None

# =================================================================
# СТАТУС И УТИЛИТЫ
# =================================================================

def get_ml_status():
    """Получение полного статуса всех ML модулей"""
    return {
        # Базовые зависимости
        'numpy': NUMPY_AVAILABLE,
        'pandas': PANDAS_AVAILABLE,
        'scikit-learn': SKLEARN_AVAILABLE,
        'tensorflow': TENSORFLOW_AVAILABLE,
        'torch': TORCH_AVAILABLE,
        
        # Основные ML модули
        'feature_engineering': FEATURE_ENGINEERING_AVAILABLE,
        'direction_classifier': DIRECTION_CLASSIFIER_AVAILABLE,
        'price_regressor': PRICE_REGRESSOR_AVAILABLE,
        'rl_agent': RL_AGENT_AVAILABLE,
        'strategy_selection': STRATEGY_SELECTION_AVAILABLE,
        'ml_trainer': ML_TRAINER_AVAILABLE,
        
        # Общие возможности
        'basic_ml': NUMPY_AVAILABLE and PANDAS_AVAILABLE and SKLEARN_AVAILABLE,
        'advanced_ml': TENSORFLOW_AVAILABLE or TORCH_AVAILABLE,
        'full_ml_stack': all([
            NUMPY_AVAILABLE, PANDAS_AVAILABLE, SKLEARN_AVAILABLE,
            FEATURE_ENGINEERING_AVAILABLE, DIRECTION_CLASSIFIER_AVAILABLE
        ]),
        'minimum_ml_stack': all([
            NUMPY_AVAILABLE, PANDAS_AVAILABLE,
            FEATURE_ENGINEERING_AVAILABLE, DIRECTION_CLASSIFIER_AVAILABLE
        ])
    }

def create_ml_pipeline(model_type='classification', **kwargs):
    """Создание ML pipeline"""
    if model_type == 'classification':
        return DirectionClassifier(**kwargs)
    elif model_type == 'regression':
        return PriceLevelRegressor(**kwargs)
    elif model_type == 'reinforcement':
        return TradingRLAgent(**kwargs)
    else:
        raise ValueError(f"Неизвестный тип модели: {model_type}")

def get_feature_engineer(config=None):
    """Получение настроенного FeatureEngineer"""
    return FeatureEngineer(config)

def check_ml_requirements():
    """Проверка минимальных требований для ML"""
    status = get_ml_status()
    
    requirements = {
        'critical': ['numpy', 'pandas'],
        'recommended': ['scikit-learn'],
        'optional': ['tensorflow', 'torch']
    }
    
    results = {
        'critical_met': all(status[req] for req in requirements['critical']),
        'recommended_met': all(status[req] for req in requirements['recommended']),
        'optional_met': any(status[req] for req in requirements['optional']),
        'ready_for_production': status['minimum_ml_stack']
    }
    
    return results

def check_ml_capabilities() -> dict:
    """
    ✅ НОВАЯ ФУНКЦИЯ: Проверка доступности ML возможностей
    Возвращает детальную информацию о доступных ML компонентах
    """
    # Получаем базовый статус
    status = get_ml_status()
    
    # Дополнительные проверки для RL Agent
    rl_agent_fixed = True
    try:
        from .models.rl_agent import TradingAction
        # Проверяем исправлен ли enum (тест ожидает SELL = 0)
        assert TradingAction.SELL == 0
        assert TradingAction.HOLD == 1  
        assert TradingAction.BUY == 2
        rl_agent_fixed = True
    except (ImportError, AssertionError):
        rl_agent_fixed = False
    
    # Формируем расширенный ответ
    capabilities = {
        # Основные зависимости
        'numpy': status.get('numpy', False),
        'pandas': status.get('pandas', False),
        'scikit-learn': status.get('scikit-learn', False),
        'tensorflow': status.get('tensorflow', False),
        'torch': status.get('torch', False),
        
        # ML модули
        'feature_engineering': status.get('feature_engineering', False),
        'direction_classifier': status.get('direction_classifier', False),
        'price_regressor': status.get('price_regressor', False),
        'rl_agent': status.get('rl_agent', False) and rl_agent_fixed,
        'strategy_selection': status.get('strategy_selection', False),
        'ml_trainer': status.get('ml_trainer', False),
        
        # Общие возможности
        'basic_ml': status.get('basic_ml', False),
        'advanced_ml': status.get('advanced_ml', False),
        'full_ml_stack': status.get('full_ml_stack', False) and rl_agent_fixed,
        'minimum_ml_stack': status.get('minimum_ml_stack', False),
        
        # Дополнительная информация
        'rl_agent_enum_fixed': rl_agent_fixed,
        'production_ready': (
            status.get('minimum_ml_stack', False) and 
            rl_agent_fixed
        )
    }
    
    return capabilities

# =================================================================
# ИНИЦИАЛИЗАЦИЯ И ЛОГИРОВАНИЕ
# =================================================================

logger.info("🧠 Инициализация ML модуля...")

# Проверяем статус всех компонентов
ml_status = get_ml_status()
requirements = check_ml_requirements()

logger.info("📊 Статус ML зависимостей:")
for component, available in ml_status.items():
    if component not in ['basic_ml', 'advanced_ml', 'full_ml_stack', 'minimum_ml_stack']:
        status_icon = "✅" if available else "❌"
        logger.info(f"   {status_icon} {component}: {available}")

logger.info("🎯 Общие возможности:")
logger.info(f"   {'✅' if ml_status['basic_ml'] else '❌'} Базовые ML возможности: {ml_status['basic_ml']}")
logger.info(f"   {'✅' if ml_status['advanced_ml'] else '❌'} Продвинутые ML возможности: {ml_status['advanced_ml']}")
logger.info(f"   {'✅' if ml_status['full_ml_stack'] else '❌'} Полный ML стек: {ml_status['full_ml_stack']}")
logger.info(f"   {'✅' if ml_status['minimum_ml_stack'] else '❌'} Минимальный ML стек: {ml_status['minimum_ml_stack']}")

logger.info("🔍 Проверка требований:")
logger.info(f"   {'✅' if requirements['critical_met'] else '❌'} Критические требования: {requirements['critical_met']}")
logger.info(f"   {'✅' if requirements['recommended_met'] else '❌'} Рекомендуемые требования: {requirements['recommended_met']}")
logger.info(f"   {'✅' if requirements['optional_met'] else '❌'} Опциональные требования: {requirements['optional_met']}")
logger.info(f"   {'✅' if requirements['ready_for_production'] else '❌'} Готовность к production: {requirements['ready_for_production']}")

# Итоговое сообщение
if ml_status['full_ml_stack']:
    logger.info("🚀 Полный ML стек доступен - все возможности активны!")
elif ml_status['minimum_ml_stack']:
    logger.info("✅ Минимальный ML стек доступен - основные функции работают")
elif ml_status['basic_ml']:
    logger.info("⚠️ Базовые ML возможности доступны - ограниченная функциональность")
else:
    logger.warning("❌ ML функциональность серьезно ограничена - работа в режиме заглушек")

logger.info("✅ ML модуль полностью инициализирован")

# =================================================================
# ЭКСПОРТ
# =================================================================

__all__ = [
    # Основные классы
    'FeatureEngineer',
    'FeatureEngineering',  # Алиас для совместимости
    'FeatureConfig',
    'DirectionClassifier',
    'DirectionClassifierLight',
    'PriceLevelRegressor',
    'TradingRLAgent',
    'TradingEnvironment',
    'TradingAction',
    'AutoStrategySelector',
    'MLTrainer',
    
    # Утилиты
    'get_ml_status',
    'create_ml_pipeline',
    'get_feature_engineer',
    'check_ml_requirements',
    'check_ml_capabilities',
    
    # Библиотеки (если доступны)
    'np',
    'pd',
    
    # Статусы доступности
    'NUMPY_AVAILABLE',
    'PANDAS_AVAILABLE',
    'SKLEARN_AVAILABLE',
    'TENSORFLOW_AVAILABLE',
    'TORCH_AVAILABLE',
    'FEATURE_ENGINEERING_AVAILABLE',
    'DIRECTION_CLASSIFIER_AVAILABLE',
    'PRICE_REGRESSOR_AVAILABLE',
    'RL_AGENT_AVAILABLE',
    'STRATEGY_SELECTION_AVAILABLE',
    'ML_TRAINER_AVAILABLE'
]