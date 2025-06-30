"""
Оптимизатор гиперпараметров для ML моделей
Файл: src/ml/training/optimizer.py
"""
import optuna
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Tuple, Optional, Callable
from datetime import datetime, timedelta
import json
import asyncio
from concurrent.futures import ProcessPoolExecutor
import joblib

from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
import xgboost as xgb
from tensorflow.keras import backend as K

from ..models.classifier import DirectionClassifier
from ..models.regressor import PriceLevelRegressor
from ..features.feature_engineering import FeatureEngineer
from .trainer import MLTrainer
from .backtester import MLBacktester
from ...core.database import SessionLocal
from ...logging.smart_logger import SmartLogger


logger = SmartLogger(__name__)


class HyperparameterOptimizer:
    """
    Оптимизатор гиперпараметров с использованием Optuna
    """
    
    def __init__(self, model_type: str = 'classifier'):
        self.model_type = model_type
        self.study = None
        self.best_params = None
        self.optimization_history = []
        
        # Настройки оптимизации
        self.n_trials = 100
        self.n_jobs = 4
        self.timeout = 3600  # 1 час
        
        # Настройки валидации
        self.n_splits = 5
        self.test_size = 0.2
        
        # Пул процессов для параллельной оптимизации
        self.executor = ProcessPoolExecutor(max_workers=self.n_jobs)
    
    def get_search_space(self, trial: optuna.Trial) -> Dict[str, Any]:
        """
        Определяет пространство поиска гиперпараметров
        """
        if self.model_type == 'classifier':
            return self._get_classifier_search_space(trial)
        elif self.model_type == 'regressor':
            return self._get_regressor_search_space(trial)
        elif self.model_type == 'xgboost':
            return self._get_xgboost_search_space(trial)
        elif self.model_type == 'neural_network':
            return self._get_nn_search_space(trial)
        else:
            raise ValueError(f"Unknown model type: {self.model_type}")
    
    def _get_classifier_search_space(self, trial: optuna.Trial) -> Dict[str, Any]:
        """Пространство поиска для классификатора"""
        return {
            # Random Forest параметры
            'n_estimators': trial.suggest_int('n_estimators', 50, 300),
            'max_depth': trial.suggest_int('max_depth', 3, 20),
            'min_samples_split': trial.suggest_int('min_samples_split', 2, 20),
            'min_samples_leaf': trial.suggest_int('min_samples_leaf', 1, 10),
            'max_features': trial.suggest_categorical('max_features', ['sqrt', 'log2', None]),
            
            # Feature engineering параметры
            'rsi_period': trial.suggest_int('rsi_period', 7, 21),
            'macd_fast': trial.suggest_int('macd_fast', 8, 15),
            'macd_slow': trial.suggest_int('macd_slow', 20, 30),
            'bb_period': trial.suggest_int('bb_period', 15, 25),
            'atr_period': trial.suggest_int('atr_period', 10, 20),
            
            # Параметры обучения
            'lookback_period': trial.suggest_int('lookback_period', 50, 200),
            'prediction_horizon': trial.suggest_int('prediction_horizon', 1, 10),
            'min_price_change': trial.suggest_float('min_price_change', 0.001, 0.01),
            
            # Балансировка классов
            'class_weight': trial.suggest_categorical('class_weight', ['balanced', None]),
            
            # Порог уверенности
            'confidence_threshold': trial.suggest_float('confidence_threshold', 0.5, 0.9)
        }
    
    def _get_regressor_search_space(self, trial: optuna.Trial) -> Dict[str, Any]:
        """Пространство поиска для регрессора"""
        return {
            # Gradient Boosting параметры
            'n_estimators': trial.suggest_int('n_estimators', 50, 300),
            'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
            'max_depth': trial.suggest_int('max_depth', 3, 15),
            'min_samples_split': trial.suggest_int('min_samples_split', 2, 20),
            'min_samples_leaf': trial.suggest_int('min_samples_leaf', 1, 10),
            'subsample': trial.suggest_float('subsample', 0.5, 1.0),
            
            # Feature параметры
            'use_volume_features': trial.suggest_categorical('use_volume_features', [True, False]),
            'use_market_features': trial.suggest_categorical('use_market_features', [True, False]),
            'feature_selection_k': trial.suggest_int('feature_selection_k', 10, 50),
            
            # Регуляризация
            'alpha': trial.suggest_float('alpha', 0.0, 1.0),
            'l1_ratio': trial.suggest_float('l1_ratio', 0.0, 1.0),
            
            # TP/SL параметры
            'tp_multiplier': trial.suggest_float('tp_multiplier', 1.5, 4.0),
            'sl_multiplier': trial.suggest_float('sl_multiplier', 0.5, 2.0),
            'use_atr_levels': trial.suggest_categorical('use_atr_levels', [True, False])
        }
    
    def _get_xgboost_search_space(self, trial: optuna.Trial) -> Dict[str, Any]:
        """Пространство поиска для XGBoost"""
        return {
            'n_estimators': trial.suggest_int('n_estimators', 100, 1000),
            'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
            'max_depth': trial.suggest_int('max_depth', 3, 10),
            'min_child_weight': trial.suggest_int('min_child_weight', 1, 10),
            'gamma': trial.suggest_float('gamma', 0.0, 1.0),
            'subsample': trial.suggest_float('subsample', 0.5, 1.0),
            'colsample_bytree': trial.suggest_float('colsample_bytree', 0.5, 1.0),
            'reg_alpha': trial.suggest_float('reg_alpha', 0.0, 1.0),
            'reg_lambda': trial.suggest_float('reg_lambda', 0.0, 1.0),
            'scale_pos_weight': trial.suggest_float('scale_pos_weight', 0.5, 2.0),
            
            # Booster specific
            'booster': trial.suggest_categorical('booster', ['gbtree', 'dart']),
            'tree_method': trial.suggest_categorical('tree_method', ['auto', 'hist', 'gpu_hist'])
        }
    
    def _get_nn_search_space(self, trial: optuna.Trial) -> Dict[str, Any]:
        """Пространство поиска для нейронной сети"""
        return {
            # Архитектура
            'n_layers': trial.suggest_int('n_layers', 2, 5),
            'n_units': trial.suggest_int('n_units', 32, 256),
            'activation': trial.suggest_categorical('activation', ['relu', 'tanh', 'elu']),
            
            # Регуляризация
            'dropout_rate': trial.suggest_float('dropout_rate', 0.0, 0.5),
            'l2_regularization': trial.suggest_float('l2_regularization', 1e-5, 1e-2, log=True),
            
            # Обучение
            'learning_rate': trial.suggest_float('learning_rate', 1e-4, 1e-2, log=True),
            'batch_size': trial.suggest_categorical('batch_size', [32, 64, 128, 256]),
            'epochs': trial.suggest_int('epochs', 50, 200),
            
            # Оптимизатор
            'optimizer': trial.suggest_categorical('optimizer', ['adam', 'sgd', 'rmsprop']),
            
            # Early stopping
            'patience': trial.suggest_int('patience', 5, 20)
        }
    
    def objective(self, trial: optuna.Trial, data: pd.DataFrame, 
                  feature_engineer: FeatureEngineer) -> float:
        """
        Целевая функция для оптимизации
        """
        try:
            # Получаем гиперпараметры
            params = self.get_search_space(trial)
            
            # Логируем попытку
            logger.info(
                f"Оптимизация trial #{trial.number}",
                category='ml',
                params=params
            )
            
            # Временная валидация с TimeSeriesSplit
            tscv = TimeSeriesSplit(n_splits=self.n_splits)
            scores = []
            
            for train_idx, val_idx in tscv.split(data):
                train_data = data.iloc[train_idx]
                val_data = data.iloc[val_idx]
                
                # Извлекаем признаки с оптимизированными параметрами
                feature_params = {k: v for k, v in params.items() 
                                if k in ['rsi_period', 'macd_fast', 'macd_slow', 
                                        'bb_period', 'atr_period']}
                
                # Обновляем параметры feature engineer
                for param, value in feature_params.items():
                    setattr(feature_engineer, param, value)
                
                # Подготавливаем данные
                X_train, y_train = self._prepare_data(train_data, feature_engineer, params)
                X_val, y_val = self._prepare_data(val_data, feature_engineer, params)
                
                # Обучаем модель
                model = self._create_model(params)
                model = self._train_model(model, X_train, y_train, X_val, y_val, params)
                
                # Оцениваем производительность
                score = self._evaluate_model(model, X_val, y_val, params)
                scores.append(score)
                
                # Освобождаем память
                del model
                if self.model_type == 'neural_network':
                    K.clear_session()
            
            # Средний score по всем фолдам
            avg_score = np.mean(scores)
            
            # Сохраняем результат
            self.optimization_history.append({
                'trial': trial.number,
                'params': params,
                'score': avg_score,
                'timestamp': datetime.utcnow()
            })
            
            logger.info(
                f"Trial #{trial.number} завершен",
                category='ml',
                score=avg_score,
                std=np.std(scores)
            )
            
            return avg_score
            
        except Exception as e:
            logger.error(
                f"Ошибка в trial #{trial.number}: {str(e)}",
                category='ml',
                error=str(e)
            )
            return 0.0
    
    def _prepare_data(self, data: pd.DataFrame, feature_engineer: FeatureEngineer,
                     params: Dict) -> Tuple[np.ndarray, np.ndarray]:
        """Подготовка данных для обучения"""
        # Извлекаем признаки
        features = feature_engineer.extract_features(
            data,
            include_volume=params.get('use_volume_features', True),
            include_market=params.get('use_market_features', True)
        )
        
        # Создаем целевую переменную
        if self.model_type in ['classifier', 'xgboost']:
            min_change = params.get('min_price_change', 0.002)
            y = feature_engineer.create_labels(
                data,
                min_price_change=min_change,
                horizon=params.get('prediction_horizon', 5)
            )
        else:
            # Для регрессора - предсказываем уровни цен
            y = feature_engineer.create_price_targets(
                data,
                horizon=params.get('prediction_horizon', 5)
            )
        
        # Убираем NaN
        mask = ~(np.isnan(features).any(axis=1) | np.isnan(y))
        
        return features[mask], y[mask]
    
    def _create_model(self, params: Dict):
        """Создает модель с заданными параметрами"""
        if self.model_type == 'classifier':
            from sklearn.ensemble import RandomForestClassifier
            return RandomForestClassifier(
                n_estimators=params['n_estimators'],
                max_depth=params['max_depth'],
                min_samples_split=params['min_samples_split'],
                min_samples_leaf=params['min_samples_leaf'],
                max_features=params['max_features'],
                class_weight=params['class_weight'],
                n_jobs=-1,
                random_state=42
            )
        
        elif self.model_type == 'regressor':
            from sklearn.ensemble import GradientBoostingRegressor
            return GradientBoostingRegressor(
                n_estimators=params['n_estimators'],
                learning_rate=params['learning_rate'],
                max_depth=params['max_depth'],
                min_samples_split=params['min_samples_split'],
                min_samples_leaf=params['min_samples_leaf'],
                subsample=params['subsample'],
                alpha=params['alpha'],
                random_state=42
            )
        
        elif self.model_type == 'xgboost':
            return xgb.XGBClassifier(
                n_estimators=params['n_estimators'],
                learning_rate=params['learning_rate'],
                max_depth=params['max_depth'],
                min_child_weight=params['min_child_weight'],
                gamma=params['gamma'],
                subsample=params['subsample'],
                colsample_bytree=params['colsample_bytree'],
                reg_alpha=params['reg_alpha'],
                reg_lambda=params['reg_lambda'],
                scale_pos_weight=params['scale_pos_weight'],
                booster=params['booster'],
                tree_method=params['tree_method'],
                use_label_encoder=False,
                eval_metric='logloss',
                random_state=42
            )
        
        elif self.model_type == 'neural_network':
            return self._create_neural_network(params)
    
    def _create_neural_network(self, params: Dict):
        """Создает нейронную сеть"""
        from tensorflow.keras.models import Sequential
        from tensorflow.keras.layers import Dense, Dropout, BatchNormalization
        from tensorflow.keras.regularizers import l2
        
        model = Sequential()
        
        # Входной слой
        model.add(Dense(
            params['n_units'],
            activation=params['activation'],
            kernel_regularizer=l2(params['l2_regularization'])
        ))
        model.add(BatchNormalization())
        model.add(Dropout(params['dropout_rate']))
        
        # Скрытые слои
        for _ in range(params['n_layers'] - 1):
            model.add(Dense(
                params['n_units'],
                activation=params['activation'],
                kernel_regularizer=l2(params['l2_regularization'])
            ))
            model.add(BatchNormalization())
            model.add(Dropout(params['dropout_rate']))
        
        # Выходной слой
        if self.model_type == 'classifier':
            model.add(Dense(3, activation='softmax'))  # 3 класса: up, down, neutral
            loss = 'sparse_categorical_crossentropy'
            metrics = ['accuracy']
        else:
            model.add(Dense(2))  # TP и SL уровни
            loss = 'mse'
            metrics = ['mae']
        
        # Компиляция
        model.compile(
            optimizer=params['optimizer'],
            loss=loss,
            metrics=metrics
        )
        
        return model
    
    def _train_model(self, model, X_train: np.ndarray, y_train: np.ndarray,
                    X_val: np.ndarray, y_val: np.ndarray, params: Dict):
        """Обучает модель"""
        if self.model_type == 'neural_network':
            from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
            
            callbacks = [
                EarlyStopping(
                    monitor='val_loss',
                    patience=params['patience'],
                    restore_best_weights=True
                ),
                ReduceLROnPlateau(
                    monitor='val_loss',
                    factor=0.5,
                    patience=params['patience'] // 2,
                    min_lr=1e-6
                )
            ]
            
            model.fit(
                X_train, y_train,
                validation_data=(X_val, y_val),
                epochs=params['epochs'],
                batch_size=params['batch_size'],
                callbacks=callbacks,
                verbose=0
            )
        
        elif self.model_type == 'xgboost':
            model.fit(
                X_train, y_train,
                eval_set=[(X_val, y_val)],
                early_stopping_rounds=10,
                verbose=False
            )
        
        else:
            model.fit(X_train, y_train)
        
        return model
    
    def _evaluate_model(self, model, X_val: np.ndarray, y_val: np.ndarray,
                       params: Dict) -> float:
        """Оценивает производительность модели"""
        if self.model_type in ['classifier', 'xgboost']:
            # Предсказания
            y_pred = model.predict(X_val)
            
            # Применяем порог уверенности для классификатора
            if hasattr(model, 'predict_proba'):
                y_proba = model.predict_proba(X_val)
                confidence_threshold = params.get('confidence_threshold', 0.6)
                
                # Фильтруем предсказания с низкой уверенностью
                max_proba = np.max(y_proba, axis=1)
                confident_mask = max_proba >= confidence_threshold
                
                if confident_mask.sum() > 0:
                    # F1-score только для уверенных предсказаний
                    return f1_score(
                        y_val[confident_mask],
                        y_pred[confident_mask],
                        average='weighted'
                    )
            
            # Если нет уверенных предсказаний - используем accuracy
            return accuracy_score(y_val, y_pred)
        
        else:
            # Для регрессора - используем отрицательный MAE
            from sklearn.metrics import mean_absolute_error
            y_pred = model.predict(X_val)
            return -mean_absolute_error(y_val, y_pred)
    
    async def optimize(self, data: pd.DataFrame, feature_engineer: FeatureEngineer,
                      n_trials: Optional[int] = None) -> Dict[str, Any]:
        """
        Запускает процесс оптимизации
        """
        logger.info(
            f"Запуск оптимизации гиперпараметров для {self.model_type}",
            category='ml',
            n_trials=n_trials or self.n_trials
        )
        
        # Создаем исследование Optuna
        self.study = optuna.create_study(
            direction='maximize',
            sampler=optuna.samplers.TPESampler(seed=42),
            pruner=optuna.pruners.MedianPruner(
                n_startup_trials=10,
                n_warmup_steps=5
            )
        )
        
        # Оптимизация
        self.study.optimize(
            lambda trial: self.objective(trial, data, feature_engineer),
            n_trials=n_trials or self.n_trials,
            timeout=self.timeout,
            n_jobs=1  # Параллелизм внутри objective
        )
        
        # Сохраняем лучшие параметры
        self.best_params = self.study.best_params
        
        # Результаты
        results = {
            'best_params': self.best_params,
            'best_score': self.study.best_value,
            'n_trials': len(self.study.trials),
            'optimization_history': self.optimization_history,
            'feature_importance': self._analyze_feature_importance()
        }
        
        # Сохраняем результаты
        await self._save_optimization_results(results)
        
        logger.info(
            "Оптимизация завершена",
            category='ml',
            best_score=self.study.best_value,
            best_params=self.best_params
        )
        
        return results
    
    def _analyze_feature_importance(self) -> Dict[str, float]:
        """Анализирует важность гиперпараметров"""
        if not self.study:
            return {}
        
        # Получаем важность параметров из Optuna
        importance = optuna.importance.get_param_importances(self.study)
        
        return importance
    
    async def _save_optimization_results(self, results: Dict[str, Any]):
        """Сохраняет результаты оптимизации"""
        db = SessionLocal()
        try:
            # Сохраняем в файл
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            filename = f"optimization_{self.model_type}_{timestamp}.json"
            
            with open(f"models/optimization/{filename}", 'w') as f:
                json.dump(results, f, indent=2, default=str)
            
            # Обновляем БД с лучшими параметрами
            from ..models import MLModel
            
            model_record = MLModel(
                name=f"{self.model_type}_optimized",
                model_type=self.model_type,
                version=timestamp,
                parameters=results['best_params'],
                accuracy=results['best_score'],
                is_active=True
            )
            
            db.add(model_record)
            db.commit()
            
        except Exception as e:
            logger.error(f"Ошибка сохранения результатов оптимизации: {e}")
            db.rollback()
        finally:
            db.close()
    
    def parallel_optimize(self, datasets: List[pd.DataFrame],
                         feature_engineers: List[FeatureEngineer]) -> List[Dict]:
        """
        Параллельная оптимизация на нескольких датасетах
        """
        futures = []
        
        for data, fe in zip(datasets, feature_engineers):
            future = self.executor.submit(
                self._optimize_single,
                data, fe
            )
            futures.append(future)
        
        # Собираем результаты
        results = []
        for future in futures:
            try:
                result = future.result(timeout=self.timeout)
                results.append(result)
            except Exception as e:
                logger.error(f"Ошибка параллельной оптимизации: {e}")
                results.append(None)
        
        return results
    
    def _optimize_single(self, data: pd.DataFrame,
                        feature_engineer: FeatureEngineer) -> Dict:
        """Оптимизация на одном датасете (для параллельного выполнения)"""
        # Создаем новый event loop для процесса
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            return loop.run_until_complete(
                self.optimize(data, feature_engineer)
            )
        finally:
            loop.close()
    
    def get_optimization_report(self) -> Dict[str, Any]:
        """Генерирует отчет по оптимизации"""
        if not self.study:
            return {}
        
        report = {
            'summary': {
                'model_type': self.model_type,
                'n_trials': len(self.study.trials),
                'best_score': self.study.best_value,
                'best_params': self.best_params,
                'optimization_time': sum(t.duration.total_seconds() 
                                       for t in self.study.trials)
            },
            'parameter_importance': self._analyze_feature_importance(),
            'convergence': self._analyze_convergence(),
            'parameter_distributions': self._analyze_parameter_distributions()
        }
        
        return report
    
    def _analyze_convergence(self) -> Dict[str, Any]:
        """Анализирует сходимость оптимизации"""
        if not self.study:
            return {}
        
        values = [t.value for t in self.study.trials if t.value is not None]
        
        return {
            'best_values_over_time': values,
            'converged': len(values) > 20 and np.std(values[-10:]) < 0.01,
            'convergence_trial': self._find_convergence_point(values)
        }
    
    def _find_convergence_point(self, values: List[float]) -> Optional[int]:
        """Находит точку сходимости"""
        if len(values) < 20:
            return None
        
        # Скользящее окно для определения стабилизации
        window_size = 10
        threshold = 0.01
        
        for i in range(window_size, len(values)):
            window = values[i-window_size:i]
            if np.std(window) < threshold:
                return i
        
        return None
    
    def _analyze_parameter_distributions(self) -> Dict[str, Any]:
        """Анализирует распределения параметров"""
        if not self.study:
            return {}
        
        distributions = {}
        
        for param_name in self.best_params.keys():
            values = [t.params.get(param_name) for t in self.study.trials
                     if param_name in t.params]
            
            if values and isinstance(values[0], (int, float)):
                distributions[param_name] = {
                    'mean': np.mean(values),
                    'std': np.std(values),
                    'min': min(values),
                    'max': max(values),
                    'best': self.best_params[param_name]
                }
        
        return distributions
    
    def __del__(self):
        """Cleanup"""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=False)


# Класс для автоматической оптимизации всех моделей
class AutoOptimizer:
    """
    Автоматический оптимизатор для всех типов моделей
    """
    
    def __init__(self):
        self.optimizers = {
            'classifier': HyperparameterOptimizer('classifier'),
            'regressor': HyperparameterOptimizer('regressor'),
            'xgboost': HyperparameterOptimizer('xgboost')
        }
        self.results = {}
    
    async def optimize_all(self, data: pd.DataFrame,
                          feature_engineer: FeatureEngineer,
                          n_trials_per_model: int = 50):
        """
        Оптимизирует все модели
        """
        logger.info(
            "Запуск полной оптимизации всех моделей",
            category='ml',
            models=list(self.optimizers.keys())
        )
        
        for model_type, optimizer in self.optimizers.items():
            logger.info(f"Оптимизация {model_type}")
            
            try:
                result = await optimizer.optimize(
                    data, feature_engineer, n_trials_per_model
                )
                self.results[model_type] = result
                
            except Exception as e:
                logger.error(
                    f"Ошибка оптимизации {model_type}: {e}",
                    category='ml'
                )
                self.results[model_type] = {'error': str(e)}
        
        # Выбираем лучшую модель
        best_model = self._select_best_model()
        
        logger.info(
            "Оптимизация всех моделей завершена",
            category='ml',
            best_model=best_model
        )
        
        return {
            'results': self.results,
            'best_model': best_model,
            'comparison': self._compare_models()
        }
    
    def _select_best_model(self) -> Dict[str, Any]:
        """Выбирает лучшую модель"""
        best_score = -float('inf')
        best_model = None
        
        for model_type, result in self.results.items():
            if 'error' not in result and result.get('best_score', -float('inf')) > best_score:
                best_score = result['best_score']
                best_model = {
                    'type': model_type,
                    'score': best_score,
                    'params': result.get('best_params', {})
                }
        
        return best_model
    
    def _compare_models(self) -> pd.DataFrame:
        """Сравнивает производительность моделей"""
        comparison_data = []
        
        for model_type, result in self.results.items():
            if 'error' not in result:
                comparison_data.append({
                    'model': model_type,
                    'best_score': result.get('best_score', 0),
                    'n_trials': result.get('n_trials', 0),
                    'n_params': len(result.get('best_params', {}))
                })
        
        return pd.DataFrame(comparison_data).sort_values(
            'best_score', ascending=False
        )