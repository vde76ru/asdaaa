#!/usr/bin/env python3
"""
ML Models модуль - ПОЛНАЯ ВЕРСИЯ
===============================
Файл: src/ml/models/__init__.py

✅ Полная интеграция всех ML моделей
✅ Импорты новых модулей: direction_classifier, price_regressor, rl_agent
✅ Импорты существующих core моделей из БД
✅ Безопасные импорты с заглушками
✅ Фабрики и утилиты для работы с моделями
"""

import logging

logger = logging.getLogger(__name__)

# =================================================================
# ИМПОРТЫ CORE МОДЕЛЕЙ БД (существующие)
# =================================================================

try:
    from ...core.models import (
        MLModel,
        MLPrediction,
        TradeMLPrediction,
        TradingLog
    )
    CORE_MODELS_AVAILABLE = True
    logger.info("✅ Core модели БД импортированы успешно")
except ImportError as e:
    logger.warning(f"⚠️ Core модели БД недоступны: {e}")
    CORE_MODELS_AVAILABLE = False
    
    # Заглушки для core моделей
    class MLModel:
        def __init__(self, **kwargs):
            self.id = kwargs.get('id')
            self.name = kwargs.get('name', 'test_model')
            self.model_type = kwargs.get('model_type', 'classification')
    
    class MLPrediction:
        def __init__(self, **kwargs):
            self.id = kwargs.get('id')
            self.model_id = kwargs.get('model_id')
            self.prediction_value = kwargs.get('prediction_value', 0.5)
    
    class TradeMLPrediction:
        def __init__(self, **kwargs):
            self.id = kwargs.get('id')
            self.trade_id = kwargs.get('trade_id')
            self.prediction_id = kwargs.get('prediction_id')
    
    class TradingLog:
        def __init__(self, **kwargs):
            self.id = kwargs.get('id')
            self.message = kwargs.get('message', '')
            self.level = kwargs.get('level', 'INFO')

# =================================================================
# ИМПОРТЫ НОВЫХ ML МОДЕЛЕЙ
# =================================================================

# Direction Classifier - НОВЫЙ МОДУЛЬ
try:
    from .direction_classifier import DirectionClassifier, DirectionClassifierLight
    DIRECTION_CLASSIFIER_AVAILABLE = True
    logger.info("✅ DirectionClassifier импортирован из direction_classifier.py")
except ImportError as e:
    logger.warning(f"⚠️ DirectionClassifier недоступен: {e}")
    DIRECTION_CLASSIFIER_AVAILABLE = False
    
    # Заглушка с полным API
    class DirectionClassifier:
        def __init__(self, 
                     model_type='random_forest',
                     forecast_horizon=5,
                     threshold=0.01,
                     confidence_threshold=0.6):
            self.model_type = model_type
            self.forecast_horizon = forecast_horizon
            self.threshold = threshold
            self.confidence_threshold = confidence_threshold
            self.is_fitted = False
            self.feature_names = []
            self.performance_metrics = {}
            self.training_history = []
        
        def prepare_labels(self, df, price_column='close'):
            """Подготовка меток для обучения"""
            import numpy as np
            size = len(df) - self.forecast_horizon
            return np.array([1] * size)  # SIDEWAYS
        
        def train(self, features_df, price_column='close', test_size=0.2, validate=True):
            """Обучение модели (заглушка)"""
            self.is_fitted = True
            metrics = {
                'train_accuracy': 0.65,
                'test_accuracy': 0.62,
                'precision': 0.60,
                'recall': 0.63,
                'f1_score': 0.61,
                'confidence': 0.58,
                'training_time': 10.5,
                'train_samples': 800,
                'test_samples': 200,
                'features_count': 15,
                'class_distribution': {'UP': 250, 'SIDEWAYS': 500, 'DOWN': 250},
                'test_mode': True
            }
            self.performance_metrics = metrics
            return metrics
        
        def predict(self, features_df):
            """Предсказание направления (заглушка)"""
            if not self.is_fitted:
                return {'error': 'model_not_fitted'}
            
            size = len(features_df) if hasattr(features_df, '__len__') else 1
            return {
                'predictions': [1] * size,
                'direction_labels': ['SIDEWAYS'] * size,
                'confidence': [0.6] * size,
                'probabilities': [[0.2, 0.6, 0.2]] * size,
                'high_confidence_count': size,
                'total_predictions': size,
                'forecast_horizon': self.forecast_horizon,
                'threshold': self.threshold,
                'test_mode': True
            }
        
        def predict_single(self, features):
            """Предсказание для одного примера (заглушка)"""
            return {
                'prediction': 1,
                'direction': 'SIDEWAYS',
                'confidence': 0.6,
                'probabilities': [0.2, 0.6, 0.2],
                'test_mode': True
            }
        
        def evaluate(self, features_df, price_column='close'):
            """Оценка модели (заглушка)"""
            return {
                'accuracy': 0.62,
                'precision': 0.60,
                'recall': 0.63,
                'f1_score': 0.61,
                'samples_count': len(features_df) if hasattr(features_df, '__len__') else 0,
                'test_mode': True
            }
        
        def get_feature_importance(self):
            """Получение важности признаков (заглушка)"""
            try:
                import pandas as pd
                return pd.DataFrame()
            except ImportError:
                return None
        
        def save_model(self, filepath):
            """Сохранение модели (заглушка)"""
            logger.info(f"Заглушка: сохранение DirectionClassifier в {filepath}")
        
        def load_model(self, filepath):
            """Загрузка модели (заглушка)"""
            logger.info(f"Заглушка: загрузка DirectionClassifier из {filepath}")
            self.is_fitted = True
        
        def get_model_info(self):
            """Информация о модели"""
            return {
                'model_type': self.model_type,
                'forecast_horizon': self.forecast_horizon,
                'threshold': self.threshold,
                'confidence_threshold': self.confidence_threshold,
                'is_fitted': self.is_fitted,
                'features_count': len(self.feature_names),
                'test_mode': True
            }
    
    # Легкая версия - алиас
    DirectionClassifierLight = DirectionClassifier

# Price Level Regressor - НОВЫЙ МОДУЛЬ
try:
    from .price_regressor import PriceLevelRegressor
    PRICE_REGRESSOR_AVAILABLE = True
    logger.info("✅ PriceLevelRegressor импортирован из price_regressor.py")
except ImportError as e:
    logger.warning(f"⚠️ PriceLevelRegressor недоступен: {e}")
    PRICE_REGRESSOR_AVAILABLE = False
    
    # Заглушка с полным API
    class PriceLevelRegressor:
        def __init__(self, 
                     model_type='random_forest',
                     forecast_horizon=5,
                     price_targets=None,
                     scaling_method='standard'):
            self.model_type = model_type
            self.forecast_horizon = forecast_horizon
            self.price_targets = price_targets or ['future_close', 'support_level', 'resistance_level', 'volatility']
            self.scaling_method = scaling_method
            self.is_fitted = False
            self.feature_names = []
            self.performance_metrics = {}
            self.training_history = []
            self.models = {}
            self.scalers = {}
        
        def prepare_targets(self, df):
            """Подготовка целевых переменных (заглушка)"""
            import numpy as np
            size = len(df) - self.forecast_horizon
            targets = {}
            for target in self.price_targets:
                if target == 'future_close':
                    targets[target] = np.array([100.0] * size)
                elif target == 'support_level':
                    targets[target] = np.array([95.0] * size)
                elif target == 'resistance_level':
                    targets[target] = np.array([105.0] * size)
                elif target == 'volatility':
                    targets[target] = np.array([0.02] * size)
                else:
                    targets[target] = np.array([50.0] * size)
            return targets
        
        def train(self, features_df, test_size=0.2, validate=True):
            """Обучение моделей (заглушка)"""
            self.is_fitted = True
            summary_metrics = {
                'models_trained': len(self.price_targets),
                'total_models': len(self.price_targets),
                'training_time': 25.3,
                'total_samples': 800,
                'features_count': 20,
                'average_r2': 0.75,
                'average_rmse': 2.5,
                'average_mae': 1.8,
                'models_metrics': {
                    target: {
                        'train_r2': 0.80,
                        'test_r2': 0.75,
                        'train_rmse': 2.0,
                        'test_rmse': 2.5,
                        'train_mae': 1.5,
                        'test_mae': 1.8
                    } for target in self.price_targets
                },
                'test_mode': True
            }
            self.performance_metrics = summary_metrics
            return summary_metrics
        
        def predict(self, features_df):
            """Предсказание ценовых уровней (заглушка)"""
            if not self.is_fitted:
                return {'error': 'models_not_fitted'}
            
            size = len(features_df) if hasattr(features_df, '__len__') else 1
            predictions = {}
            
            for target in self.price_targets:
                if target == 'future_close':
                    predictions[target] = [100.0] * size
                elif target == 'support_level':
                    predictions[target] = [95.0] * size
                elif target == 'resistance_level':
                    predictions[target] = [105.0] * size
                elif target == 'volatility':
                    predictions[target] = [0.02] * size
                else:
                    predictions[target] = [50.0] * size
            
            return {
                'predictions': predictions,
                'forecast_horizon': self.forecast_horizon,
                'valid_samples': size,
                'total_samples': size,
                'model_type': self.model_type,
                'test_mode': True
            }
        
        def predict_single(self, features):
            """Предсказание для одного примера (заглушка)"""
            single_predictions = {}
            for target in self.price_targets:
                if target == 'future_close':
                    single_predictions[target] = 100.0
                elif target == 'support_level':
                    single_predictions[target] = 95.0
                elif target == 'resistance_level':
                    single_predictions[target] = 105.0
                elif target == 'volatility':
                    single_predictions[target] = 0.02
                else:
                    single_predictions[target] = 50.0
            
            return {
                'predictions': single_predictions,
                'forecast_horizon': self.forecast_horizon,
                'test_mode': True
            }
        
        def get_model_performance(self):
            """Получение метрик производительности"""
            return self.performance_metrics
        
        def get_feature_importance(self, target_name=None):
            """Получение важности признаков (заглушка)"""
            try:
                import pandas as pd
                return pd.DataFrame()
            except ImportError:
                return None
        
        def save_models(self, directory):
            """Сохранение всех моделей (заглушка)"""
            logger.info(f"Заглушка: сохранение PriceLevelRegressor в {directory}")
        
        def load_models(self, directory):
            """Загрузка всех моделей (заглушка)"""
            logger.info(f"Заглушка: загрузка PriceLevelRegressor из {directory}")
            self.is_fitted = True
        
        def get_model_info(self):
            """Информация о моделях"""
            return {
                'model_type': self.model_type,
                'forecast_horizon': self.forecast_horizon,
                'price_targets': self.price_targets,
                'scaling_method': self.scaling_method,
                'is_fitted': self.is_fitted,
                'features_count': len(self.feature_names),
                'models_count': len(self.models),
                'test_mode': True
            }

# Trading RL Agent - НОВЫЙ МОДУЛЬ
try:
    from .rl_agent import TradingRLAgent, TradingEnvironment, TradingAction, TradingState, TradingReward
    RL_AGENT_AVAILABLE = True
    logger.info("✅ TradingRLAgent импортирован из rl_agent.py")
except ImportError as e:
    logger.warning(f"⚠️ TradingRLAgent недоступен: {e}")
    RL_AGENT_AVAILABLE = False
    
    # Заглушки с полным API
    class TradingAction:
        SELL = 0
        HOLD = 1
        BUY = 2
    
    class TradingState:
        def __init__(self, **kwargs):
            self.price = kwargs.get('price', 100.0)
            self.volume = kwargs.get('volume', 1000.0)
            self.rsi = kwargs.get('rsi', 50.0)
            self.macd = kwargs.get('macd', 0.0)
            self.bb_position = kwargs.get('bb_position', 0.5)
            self.portfolio_value = kwargs.get('portfolio_value', 10000.0)
            self.position_size = kwargs.get('position_size', 0.0)
            self.timestamp = kwargs.get('timestamp', None)
    
    class TradingReward:
        def __init__(self, **kwargs):
            self.profit = kwargs.get('profit', 0.0)
            self.penalty = kwargs.get('penalty', 0.0)
            self.total_reward = kwargs.get('total_reward', 0.0)
            self.risk_penalty = kwargs.get('risk_penalty', 0.0)
            self.transaction_cost = kwargs.get('transaction_cost', 0.0)
    
    class TradingEnvironment:
        def __init__(self, data, **kwargs):
            self.data = data
            self.initial_balance = kwargs.get('initial_balance', 10000.0)
            self.transaction_cost = kwargs.get('transaction_cost', 0.001)
            self.max_position_size = kwargs.get('max_position_size', 1.0)
            self.current_step = 0
            self.balance = self.initial_balance
            self.position = 0.0
        
        def reset(self):
            """Сброс окружения (заглушка)"""
            self.current_step = 0
            self.balance = self.initial_balance
            self.position = 0.0
            return [0.0] * 8
        
        def step(self, action):
            """Выполнение действия (заглушка)"""
            self.current_step += 1
            new_state = [0.0] * 8
            reward = 0.1 if action == 1 else -0.05  # Поощряем HOLD
            done = self.current_step >= 100
            info = {
                'portfolio_value': self.initial_balance + 100,
                'balance': self.balance,
                'position': self.position,
                'total_trades': 5,
                'win_rate': 0.6
            }
            return new_state, reward, done, info
    
    class TradingRLAgent:
        def __init__(self, **kwargs):
            self.state_size = kwargs.get('state_size', 8)
            self.action_size = kwargs.get('action_size', 3)
            self.learning_rate = kwargs.get('learning_rate', 0.001)
            self.epsilon = kwargs.get('epsilon', 1.0)
            self.epsilon_decay = kwargs.get('epsilon_decay', 0.995)
            self.epsilon_min = kwargs.get('epsilon_min', 0.01)
            self.gamma = kwargs.get('gamma', 0.95)
            self.is_trained = False
            self.training_history = []
            self.q_table = {}
        
        def get_action(self, state, training=True):
            """Выбор действия (заглушка)"""
            return 1  # HOLD
        
        def remember(self, state, action, reward, next_state, done):
            """Запоминание опыта (заглушка)"""
            pass
        
        def replay(self, batch_size=32):
            """Обучение на батче (заглушка)"""
            pass
        
        def train(self, data, episodes=100, **kwargs):
            """Обучение RL агента (заглушка)"""
            self.is_trained = True
            training_results = {
                'episodes_completed': episodes,
                'final_epsilon': self.epsilon_min,
                'q_table_size': 150,
                'avg_episode_reward': 125.5,
                'final_portfolio_value': 11250.0,
                'total_return': 12.5,
                'validation_results': {
                    'total_reward': 200.0,
                    'final_portfolio_value': 11000.0,
                    'total_return': 10.0,
                    'total_trades': 25,
                    'win_rate': 0.64,
                    'actions_distribution': {'SELL': 8, 'HOLD': 12, 'BUY': 5}
                },
                'test_mode': True
            }
            self.training_history.append({
                'timestamp': None,
                'results': training_results,
                'episodes': episodes
            })
            return training_results
        
        def predict(self, state):
            """Предсказание действия (заглушка)"""
            return {
                'action': 1,
                'action_name': 'HOLD',
                'confidence': 0.6,
                'q_values': [0.3, 0.6, 0.1],
                'state_known': True,
                'test_mode': True
            }
        
        def save_model(self, filepath):
            """Сохранение модели (заглушка)"""
            logger.info(f"Заглушка: сохранение TradingRLAgent в {filepath}")
        
        def load_model(self, filepath):
            """Загрузка модели (заглушка)"""
            logger.info(f"Заглушка: загрузка TradingRLAgent из {filepath}")
            self.is_trained = True
        
        def get_model_info(self):
            """Информация о модели"""
            return {
                'model_type': 'Q-Learning',
                'state_size': self.state_size,
                'action_size': self.action_size,
                'learning_rate': self.learning_rate,
                'epsilon': self.epsilon,
                'gamma': self.gamma,
                'q_table_size': len(self.q_table),
                'is_trained': self.is_trained,
                'test_mode': True
            }

# Ensemble Model - для совместимости с trainer.py
try:
    # ✅ ИСПРАВЛЕНО: EnsembleModel находится в trainer.py, импортируем оттуда
    from ..training.trainer import EnsembleModel
    ENSEMBLE_AVAILABLE = True
    logger.info("✅ EnsembleModel импортирован из training.trainer")
except ImportError as e:
    logger.warning(f"⚠️ EnsembleModel недоступен: {e}, создаем заглушку")
    ENSEMBLE_AVAILABLE = False
    
    # Заглушка для EnsembleModel
    class EnsembleModel:
        def __init__(self, models=None, weights=None, name="ensemble"):
            self.models = models or {}
            self.weights = weights or []
            self.name = name
            self.feature_columns = []
            logger.warning("⚠️ Используется заглушка EnsembleModel")
        
        def predict(self, X):
            """Предсказание ансамбля (заглушка)"""
            size = len(X) if hasattr(X, '__len__') else 1
            return [1] * size  # SIDEWAYS/HOLD
        
        def predict_proba(self, X):
            """Предсказание вероятностей (заглушка)"""
            size = len(X) if hasattr(X, '__len__') else 1
            return [[0.2, 0.6, 0.2]] * size
        
        def get_confidence(self, X):
            """Получение уверенности (заглушка)"""
            size = len(X) if hasattr(X, '__len__') else 1
            return [0.6] * size

# =================================================================
# УТИЛИТЫ И ФАБРИКИ
# =================================================================

def get_models_status():
    """Получение статуса всех ML моделей"""
    return {
        # Core модели БД
        'core_models': CORE_MODELS_AVAILABLE,
        
        # ML модели
        'direction_classifier': DIRECTION_CLASSIFIER_AVAILABLE,
        'price_regressor': PRICE_REGRESSOR_AVAILABLE,
        'rl_agent': RL_AGENT_AVAILABLE,
        'ensemble': ENSEMBLE_AVAILABLE,
        
        # Статистика
        'ml_models_count': 4,
        'available_ml_models': sum([
            DIRECTION_CLASSIFIER_AVAILABLE,
            PRICE_REGRESSOR_AVAILABLE,
            RL_AGENT_AVAILABLE,
            ENSEMBLE_AVAILABLE
        ]),
        
        # Готовность
        'critical_models_available': all([
            DIRECTION_CLASSIFIER_AVAILABLE,
            PRICE_REGRESSOR_AVAILABLE
        ]),
        'all_models_available': all([
            CORE_MODELS_AVAILABLE,
            DIRECTION_CLASSIFIER_AVAILABLE,
            PRICE_REGRESSOR_AVAILABLE,
            RL_AGENT_AVAILABLE,
            ENSEMBLE_AVAILABLE
        ]),
        'production_ready': CORE_MODELS_AVAILABLE and DIRECTION_CLASSIFIER_AVAILABLE and PRICE_REGRESSOR_AVAILABLE
    }

def create_model_by_type(model_type, **kwargs):
    """Фабрика для создания моделей по типу"""
    model_type = model_type.lower()
    
    if model_type in ['direction', 'direction_classifier', 'classifier', 'classification']:
        return DirectionClassifier(**kwargs)
    elif model_type in ['price', 'price_regressor', 'regressor', 'regression']:
        return PriceLevelRegressor(**kwargs)
    elif model_type in ['rl', 'rl_agent', 'reinforcement', 'q_learning']:
        return TradingRLAgent(**kwargs)
    elif model_type in ['ensemble']:
        return EnsembleModel(**kwargs)
    else:
        raise ValueError(f"Неизвестный тип модели: {model_type}")

def create_ml_pipeline(pipeline_type='full', **kwargs):
    """Создание ML pipeline"""
    pipeline = {}
    
    if pipeline_type in ['full', 'classification', 'all']:
        pipeline['direction_classifier'] = DirectionClassifier(**kwargs)
    
    if pipeline_type in ['full', 'regression', 'all']:
        pipeline['price_regressor'] = PriceLevelRegressor(**kwargs)
    
    if pipeline_type in ['full', 'reinforcement', 'all']:
        pipeline['rl_agent'] = TradingRLAgent(**kwargs)
    
    if pipeline_type in ['ensemble']:
        pipeline['ensemble'] = EnsembleModel(**kwargs)
    
    return pipeline

def get_available_models():
    """Получение списка доступных моделей"""
    models = {}
    
    if DIRECTION_CLASSIFIER_AVAILABLE:
        models['DirectionClassifier'] = DirectionClassifier
        models['DirectionClassifierLight'] = DirectionClassifierLight
    
    if PRICE_REGRESSOR_AVAILABLE:
        models['PriceLevelRegressor'] = PriceLevelRegressor
    
    if RL_AGENT_AVAILABLE:
        models['TradingRLAgent'] = TradingRLAgent
    
    if ENSEMBLE_AVAILABLE:
        models['EnsembleModel'] = EnsembleModel
    
    return models

def validate_model_compatibility(model, data_format='pandas'):
    """Проверка совместимости модели с данными"""
    required_methods = ['train', 'predict']
    
    for method in required_methods:
        if not hasattr(model, method):
            return False, f"Модель не имеет метода '{method}'"
    
    return True, "Модель совместима"

# =================================================================
# ИНИЦИАЛИЗАЦИЯ И СТАТУС
# =================================================================

logger.info("🤖 Инициализация ML Models модуля...")

# Проверяем статус всех моделей
status = get_models_status()

logger.info("📊 Статус ML моделей:")
logger.info(f"   {'✅' if status['core_models'] else '❌'} Core модели БД: {status['core_models']}")
logger.info(f"   {'✅' if status['direction_classifier'] else '❌'} DirectionClassifier: {status['direction_classifier']}")
logger.info(f"   {'✅' if status['price_regressor'] else '❌'} PriceLevelRegressor: {status['price_regressor']}")
logger.info(f"   {'✅' if status['rl_agent'] else '❌'} TradingRLAgent: {status['rl_agent']}")
logger.info(f"   {'✅' if status['ensemble'] else '❌'} EnsembleModel: {status['ensemble']}")

logger.info(f"📈 Доступно ML моделей: {status['available_ml_models']}/{status['ml_models_count']}")

# Статус готовности
if status['all_models_available']:
    logger.info("🚀 Все модели доступны - полная функциональность!")
elif status['production_ready']:
    logger.info("✅ Критические модели доступны - готово к production")
elif status['critical_models_available']:
    logger.info("⚠️ Основные ML модели доступны - базовая функциональность")
else:
    logger.warning("❌ Критические модели недоступны - работа в режиме заглушек")

available_models = get_available_models()
logger.info(f"🎯 Доступные модели: {list(available_models.keys())}")

logger.info("✅ ML Models модуль полностью инициализирован")

# =================================================================
# ЭКСПОРТ
# =================================================================

__all__ = [
    # Core модели БД
    'MLModel',
    'MLPrediction', 
    'TradeMLPrediction',
    'TradingLog',
    
    # ML модели - классификация
    'DirectionClassifier',
    'DirectionClassifierLight',
    
    # ML модели - регрессия
    'PriceLevelRegressor',
    
    # ML модели - обучение с подкреплением
    'TradingRLAgent',
    'TradingEnvironment',
    'TradingAction',
    'TradingState',
    'TradingReward',
    
    # Ансамбли
    'EnsembleModel',
    
    # Утилиты и фабрики
    'get_models_status',
    'create_model_by_type',
    'create_ml_pipeline',
    'get_available_models',
    'validate_model_compatibility',
    
    # Статусы доступности
    'CORE_MODELS_AVAILABLE',
    'DIRECTION_CLASSIFIER_AVAILABLE',
    'PRICE_REGRESSOR_AVAILABLE',
    'RL_AGENT_AVAILABLE',
    'ENSEMBLE_AVAILABLE'
]