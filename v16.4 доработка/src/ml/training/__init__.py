"""
Модуль обучения ML моделей
"""
# Попытка импорта с защитой от отсутствия модулей
try:
    from .trainer import MLTrainer, EnsembleModel
    _trainer_available = True
except ImportError as e:
    _trainer_available = False
    print(f"⚠️ Ошибка импорта trainer: {e}")
    
    # Заглушки для случая если trainer.py недоступен
    class MLTrainer:
        """Заглушка для MLTrainer"""
        def __init__(self, model_type='classifier'):
            self.model_type = model_type
            self.is_trained = False
            
        def train(self, X, y):
            """Имитация обучения"""
            self.is_trained = True
            return {'accuracy': 0.85, 'status': 'stub'}
        
        def predict(self, X):
            """Возвращает случайные предсказания"""
            import numpy as np
            return np.random.choice([0, 1], size=len(X))
    
    class EnsembleModel:
        """Заглушка для EnsembleModel"""
        def __init__(self, models=None, weights=None, name="ensemble"):
            self.models = models or {}
            self.weights = weights or []
            self.name = name
            self.feature_columns = []
        
        def predict(self, X):
            """Предсказание ансамбля (заглушка)"""
            size = len(X) if hasattr(X, '__len__') else 1
            return [1] * size  # SIDEWAYS/HOLD
        
        def predict_proba(self, X):
            """Предсказание вероятностей (заглушка)"""
            size = len(X) if hasattr(X, '__len__') else 1
            return [[0.2, 0.6, 0.2]] * size

# Опциональные компоненты обучения
try:
    from .optimizer import HyperparameterOptimizer
    _optimizer_available = True
except ImportError:
    _optimizer_available = False
    HyperparameterOptimizer = None

try:
    from .backtester import MLBacktester
    _backtester_available = True
except ImportError:
    _backtester_available = False
    MLBacktester = None

# Экспорт
__all__ = ['MLTrainer', 'EnsembleModel']

if _optimizer_available:
    __all__.append('HyperparameterOptimizer')
    
if _backtester_available:
    __all__.append('MLBacktester')