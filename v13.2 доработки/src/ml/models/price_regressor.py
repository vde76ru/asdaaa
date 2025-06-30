#!/usr/bin/env python3
"""
Price Level Regressor для предсказания ценовых уровней - ИСПРАВЛЕННАЯ ВЕРСИЯ
==========================================================================
Файл: src/ml/models/price_regressor.py

✅ ИСПРАВЛЯЕТ: No module named 'src.ml.models.price_regressor'
✅ Полная совместимость с существующей системой
✅ Профессиональная реализация регрессии для цен
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any, Union
from datetime import datetime, timedelta
import pickle
import json
from pathlib import Path
import logging

# Безопасные импорты ML библиотек
try:
    from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
    from sklearn.linear_model import LinearRegression, Ridge, Lasso
    from sklearn.svm import SVR
    from sklearn.model_selection import train_test_split, cross_val_score, GridSearchCV
    from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
    from sklearn.preprocessing import StandardScaler, MinMaxScaler
    from sklearn.pipeline import Pipeline
    import joblib
    SKLEARN_AVAILABLE = True
except ImportError:
    logger.warning("⚠️ scikit-learn недоступен")
    SKLEARN_AVAILABLE = False

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

class PriceLevelRegressor:
    """
    ✅ ИСПРАВЛЕННЫЙ: Регрессор для предсказания ценовых уровней
    
    Предсказывает конкретные ценовые уровни, включая:
    - Будущую цену закрытия
    - Уровни поддержки и сопротивления
    - Оптимальные Take Profit и Stop Loss уровни
    - Волатильность и диапазоны цен
    """
    
    def __init__(self, 
                 model_type: str = 'random_forest',
                 forecast_horizon: int = 5,
                 price_targets: List[str] = None,
                 scaling_method: str = 'standard'):
        """
        Инициализация регрессора ценовых уровней
        
        Args:
            model_type: Тип модели ('random_forest', 'gradient_boosting', 'linear', 'ridge', 'svr')
            forecast_horizon: Горизонт прогнозирования (количество периодов)
            price_targets: Список целевых переменных для предсказания
            scaling_method: Метод масштабирования ('standard', 'minmax', 'none')
        """
        self.model_type = model_type
        self.forecast_horizon = forecast_horizon
        self.scaling_method = scaling_method
        
        # Целевые переменные по умолчанию
        if price_targets is None:
            self.price_targets = ['future_close', 'support_level', 'resistance_level', 'volatility']
        else:
            self.price_targets = price_targets
        
        # Модели для каждой целевой переменной
        self.models = {}
        self.scalers = {
            'features': self._get_scaler(),
            'targets': {}
        }
        
        # Метаданные
        self.feature_names: List[str] = []
        self.is_fitted = False
        self.performance_metrics = {}
        self.training_history = []
        
        # Параметры модели
        self.model_params = self._get_default_params()
        
        # Инициализация моделей
        if SKLEARN_AVAILABLE:
            self._initialize_models()
        
        logger.info(f"✅ PriceLevelRegressor инициализирован: {model_type}")
        logger.info(f"📊 Целевые переменные: {self.price_targets}")
    
    def _get_scaler(self):
        """Получение скалера данных"""
        if not SKLEARN_AVAILABLE:
            return None
        
        if self.scaling_method == 'standard':
            return StandardScaler()
        elif self.scaling_method == 'minmax':
            return MinMaxScaler()
        else:
            return None
    
    def _get_default_params(self) -> Dict[str, Any]:
        """Получение параметров по умолчанию для разных моделей"""
        params = {
            'random_forest': {
                'n_estimators': 100,
                'max_depth': 15,
                'min_samples_split': 5,
                'min_samples_leaf': 2,
                'random_state': 42
            },
            'gradient_boosting': {
                'n_estimators': 100,
                'learning_rate': 0.1,
                'max_depth': 8,
                'random_state': 42
            },
            'linear': {
                'fit_intercept': True
            },
            'ridge': {
                'alpha': 1.0,
                'random_state': 42
            },
            'lasso': {
                'alpha': 1.0,
                'random_state': 42,
                'max_iter': 1000
            },
            'svr': {
                'kernel': 'rbf',
                'C': 1.0,
                'epsilon': 0.1
            }
        }
        
        return params.get(self.model_type, {})
    
    def _get_model_instance(self):
        """Создание экземпляра модели"""
        if not SKLEARN_AVAILABLE:
            return None
        
        if self.model_type == 'random_forest':
            return RandomForestRegressor(**self.model_params)
        elif self.model_type == 'gradient_boosting':
            return GradientBoostingRegressor(**self.model_params)
        elif self.model_type == 'linear':
            return LinearRegression(**self.model_params)
        elif self.model_type == 'ridge':
            return Ridge(**self.model_params)
        elif self.model_type == 'lasso':
            return Lasso(**self.model_params)
        elif self.model_type == 'svr':
            return SVR(**self.model_params)
        else:
            logger.warning(f"⚠️ Неизвестный тип модели: {self.model_type}, используем Random Forest")
            return RandomForestRegressor(n_estimators=50, random_state=42)
    
    def _initialize_models(self):
        """Инициализация моделей для каждой целевой переменной"""
        try:
            for target in self.price_targets:
                self.models[target] = self._get_model_instance()
                if self.scaling_method != 'none':
                    self.scalers['targets'][target] = self._get_scaler()
            
            logger.info(f"✅ Инициализировано {len(self.models)} моделей")
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации моделей: {e}")
    
    def prepare_targets(self, df: pd.DataFrame) -> Dict[str, np.ndarray]:
        """
        Подготовка целевых переменных
        
        Args:
            df: DataFrame с ценовыми данными (OHLCV)
            
        Returns:
            Словарь с целевыми переменными
        """
        try:
            targets = {}
            
            # Будущая цена закрытия
            if 'future_close' in self.price_targets:
                targets['future_close'] = df['close'].shift(-self.forecast_horizon).values
            
            # Будущий максимум (сопротивление)
            if 'resistance_level' in self.price_targets:
                targets['resistance_level'] = df['high'].rolling(
                    window=self.forecast_horizon
                ).max().shift(-self.forecast_horizon).values
            
            # Будущий минимум (поддержка)
            if 'support_level' in self.price_targets:
                targets['support_level'] = df['low'].rolling(
                    window=self.forecast_horizon
                ).min().shift(-self.forecast_horizon).values
            
            # Будущая волатильность
            if 'volatility' in self.price_targets:
                future_returns = df['close'].pct_change().shift(-self.forecast_horizon)
                targets['volatility'] = future_returns.rolling(
                    window=self.forecast_horizon
                ).std().values
            
            # Будущий диапазон цен
            if 'price_range' in self.price_targets:
                future_high = df['high'].shift(-self.forecast_horizon)
                future_low = df['low'].shift(-self.forecast_horizon)
                targets['price_range'] = (future_high - future_low).values
            
            # Оптимальный Take Profit уровень (примерная реализация)
            if 'optimal_tp' in self.price_targets:
                # Используем будущий максимум в качестве оптимального TP
                future_max = df['high'].rolling(
                    window=self.forecast_horizon*2
                ).max().shift(-self.forecast_horizon)
                targets['optimal_tp'] = (future_max / df['close'] - 1).values * 100
            
            # Оптимальный Stop Loss уровень
            if 'optimal_sl' in self.price_targets:
                # Используем будущий минимум в качестве оптимального SL
                future_min = df['low'].rolling(
                    window=self.forecast_horizon*2
                ).min().shift(-self.forecast_horizon)
                targets['optimal_sl'] = (df['close'] / future_min - 1).values * 100
            
            logger.info(f"✅ Подготовлено {len(targets)} целевых переменных")
            
            return targets
            
        except Exception as e:
            logger.error(f"❌ Ошибка подготовки целевых переменных: {e}")
            return {}
    
    def train(self, 
              features_df: pd.DataFrame,
              test_size: float = 0.2,
              validate: bool = True) -> Dict[str, Any]:
        """
        Обучение моделей регрессии
        
        Args:
            features_df: DataFrame с признаками и ценовыми данными
            test_size: Размер тестовой выборки
            validate: Проводить ли кросс-валидацию
            
        Returns:
            Словарь с метриками обучения для каждой модели
        """
        if not SKLEARN_AVAILABLE:
            logger.error("❌ scikit-learn недоступен")
            return {'error': 'sklearn_unavailable'}
        
        try:
            logger.info("🎯 Начало обучения PriceLevelRegressor...")
            
            # Подготовка признаков
            feature_columns = [col for col in features_df.columns 
                             if col not in ['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            
            if not feature_columns:
                logger.error("❌ Нет признаков для обучения")
                return {'error': 'no_features'}
            
            self.feature_names = feature_columns
            
            # Подготовка целевых переменных
            targets_dict = self.prepare_targets(features_df)
            if not targets_dict:
                logger.error("❌ Нет целевых переменных")
                return {'error': 'no_targets'}
            
            # Подготовка признаков
            X = features_df[feature_columns].copy()
            
            # Удаляем строки с будущими данными
            valid_length = len(X) - self.forecast_horizon
            X = X.iloc[:valid_length]
            
            # Обрезаем целевые переменные до той же длины
            for target_name in targets_dict:
                targets_dict[target_name] = targets_dict[target_name][:valid_length]
            
            # Удаляем строки с NaN
            valid_mask = ~X.isnull().any(axis=1)
            for target_name, target_values in targets_dict.items():
                valid_mask &= ~pd.isnull(target_values)
            
            X = X[valid_mask]
            for target_name in targets_dict:
                targets_dict[target_name] = targets_dict[target_name][valid_mask]
            
            if len(X) == 0:
                logger.error("❌ Нет валидных данных после очистки")
                return {'error': 'no_valid_data'}
            
            # Масштабирование признаков
            if self.scalers['features']:
                X_scaled = self.scalers['features'].fit_transform(X)
            else:
                X_scaled = X.values
            
            # Обучение моделей для каждой целевой переменной
            all_metrics = {}
            start_time = datetime.now()
            
            for target_name, y in targets_dict.items():
                if target_name not in self.models:
                    logger.warning(f"⚠️ Модель для {target_name} не инициализирована")
                    continue
                
                try:
                    logger.info(f"🔄 Обучение модели для {target_name}...")
                    
                    # Масштабирование целевой переменной
                    if target_name in self.scalers['targets']:
                        y_scaled = self.scalers['targets'][target_name].fit_transform(
                            y.reshape(-1, 1)
                        ).ravel()
                    else:
                        y_scaled = y
                    
                    # Разделение на обучение и тест
                    X_train, X_test, y_train, y_test = train_test_split(
                        X_scaled, y_scaled, test_size=test_size, random_state=42
                    )
                    
                    # Обучение модели
                    self.models[target_name].fit(X_train, y_train)
                    
                    # Предсказания
                    y_pred_train = self.models[target_name].predict(X_train)
                    y_pred_test = self.models[target_name].predict(X_test)
                    
                    # Обратное масштабирование для метрик
                    if target_name in self.scalers['targets']:
                        y_train_orig = self.scalers['targets'][target_name].inverse_transform(
                            y_train.reshape(-1, 1)
                        ).ravel()
                        y_test_orig = self.scalers['targets'][target_name].inverse_transform(
                            y_test.reshape(-1, 1)
                        ).ravel()
                        y_pred_train_orig = self.scalers['targets'][target_name].inverse_transform(
                            y_pred_train.reshape(-1, 1)
                        ).ravel()
                        y_pred_test_orig = self.scalers['targets'][target_name].inverse_transform(
                            y_pred_test.reshape(-1, 1)
                        ).ravel()
                    else:
                        y_train_orig = y_train
                        y_test_orig = y_test
                        y_pred_train_orig = y_pred_train
                        y_pred_test_orig = y_pred_test
                    
                    # Метрики
                    metrics = {
                        'train_mse': mean_squared_error(y_train_orig, y_pred_train_orig),
                        'test_mse': mean_squared_error(y_test_orig, y_pred_test_orig),
                        'train_mae': mean_absolute_error(y_train_orig, y_pred_train_orig),
                        'test_mae': mean_absolute_error(y_test_orig, y_pred_test_orig),
                        'train_r2': r2_score(y_train_orig, y_pred_train_orig),
                        'test_r2': r2_score(y_test_orig, y_pred_test_orig),
                        'train_samples': len(X_train),
                        'test_samples': len(X_test)
                    }
                    
                    # RMSE
                    metrics['train_rmse'] = np.sqrt(metrics['train_mse'])
                    metrics['test_rmse'] = np.sqrt(metrics['test_mse'])
                    
                    # Процентные ошибки для ценовых целей
                    if 'close' in target_name or 'price' in target_name:
                        metrics['test_mape'] = np.mean(
                            np.abs((y_test_orig - y_pred_test_orig) / y_test_orig)
                        ) * 100
                    
                    # Кросс-валидация
                    if validate and len(X) > 100:
                        try:
                            cv_scores = cross_val_score(
                                self.models[target_name], X_scaled, y_scaled, 
                                cv=5, scoring='r2'
                            )
                            metrics['cv_r2_mean'] = cv_scores.mean()
                            metrics['cv_r2_std'] = cv_scores.std()
                        except Exception as e:
                            logger.warning(f"⚠️ Ошибка кросс-валидации для {target_name}: {e}")
                            metrics['cv_r2_mean'] = 0.0
                            metrics['cv_r2_std'] = 0.0
                    
                    all_metrics[target_name] = metrics
                    
                    logger.info(f"✅ {target_name}: R² = {metrics['test_r2']:.3f}, "
                               f"RMSE = {metrics['test_rmse']:.3f}")
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка обучения модели {target_name}: {e}")
                    all_metrics[target_name] = {'error': str(e)}
            
            training_time = (datetime.now() - start_time).total_seconds()
            
            # Общие метрики
            summary_metrics = {
                'models_trained': len([m for m in all_metrics.values() if 'error' not in m]),
                'total_models': len(self.models),
                'training_time': training_time,
                'total_samples': len(X),
                'features_count': len(feature_columns),
                'models_metrics': all_metrics,
                'timestamp': datetime.now().isoformat()
            }
            
            # Средние метрики
            valid_metrics = [m for m in all_metrics.values() if 'error' not in m]
            if valid_metrics:
                summary_metrics['average_r2'] = np.mean([m['test_r2'] for m in valid_metrics])
                summary_metrics['average_rmse'] = np.mean([m['test_rmse'] for m in valid_metrics])
                summary_metrics['average_mae'] = np.mean([m['test_mae'] for m in valid_metrics])
            
            # Сохраняем метрики
            self.performance_metrics = summary_metrics
            self.is_fitted = True
            
            # Добавляем в историю
            self.training_history.append({
                'timestamp': datetime.now(),
                'metrics': summary_metrics,
                'model_type': self.model_type,
                'samples_count': len(X)
            })
            
            logger.info(f"✅ Обучение завершено! Средний R²: {summary_metrics.get('average_r2', 0):.3f}")
            
            return summary_metrics
            
        except Exception as e:
            logger.error(f"❌ Ошибка обучения: {e}")
            return {'error': str(e)}
    
    def predict(self, features_df: pd.DataFrame) -> Dict[str, Any]:
        """
        Предсказание ценовых уровней
        
        Args:
            features_df: DataFrame с признаками
            
        Returns:
            Словарь с предсказаниями для каждой целевой переменной
        """
        if not self.is_fitted:
            logger.error("❌ Модели не обучены")
            return {'error': 'models_not_fitted'}
        
        if not SKLEARN_AVAILABLE:
            logger.error("❌ scikit-learn недоступен")
            return {'error': 'sklearn_unavailable'}
        
        try:
            # Проверка признаков
            missing_features = set(self.feature_names) - set(features_df.columns)
            if missing_features:
                logger.error(f"❌ Отсутствуют признаки: {missing_features}")
                return {'error': f'missing_features: {missing_features}'}
            
            # Подготовка данных
            X = features_df[self.feature_names].copy()
            
            # Удаляем строки с NaN
            valid_indices = ~X.isnull().any(axis=1)
            if not valid_indices.any():
                logger.error("❌ Нет валидных данных для предсказания")
                return {'error': 'no_valid_data'}
            
            X_valid = X[valid_indices]
            
            # Масштабирование признаков
            if self.scalers['features']:
                X_scaled = self.scalers['features'].transform(X_valid)
            else:
                X_scaled = X_valid.values
            
            # Предсказания для каждой модели
            predictions = {}
            
            for target_name, model in self.models.items():
                try:
                    # Предсказание
                    y_pred_scaled = model.predict(X_scaled)
                    
                    # Обратное масштабирование
                    if target_name in self.scalers['targets']:
                        y_pred = self.scalers['targets'][target_name].inverse_transform(
                            y_pred_scaled.reshape(-1, 1)
                        ).ravel()
                    else:
                        y_pred = y_pred_scaled
                    
                    predictions[target_name] = y_pred.tolist()
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка предсказания {target_name}: {e}")
                    predictions[target_name] = {'error': str(e)}
            
            # Создание результата
            results = {
                'predictions': predictions,
                'forecast_horizon': self.forecast_horizon,
                'valid_samples': len(X_valid),
                'total_samples': len(X),
                'valid_indices': valid_indices.tolist(),
                'timestamp': datetime.now().isoformat(),
                'model_type': self.model_type
            }
            
            # Дополнительная обработка результатов
            if 'future_close' in predictions and isinstance(predictions['future_close'], list):
                current_prices = features_df['close'][valid_indices].values
                future_prices = np.array(predictions['future_close'])
                
                # Процентное изменение
                price_changes = (future_prices / current_prices - 1) * 100
                results['price_change_percent'] = price_changes.tolist()
                
                # Статистика
                results['prediction_stats'] = {
                    'mean_price_change': float(np.mean(price_changes)),
                    'std_price_change': float(np.std(price_changes)),
                    'min_price_change': float(np.min(price_changes)),
                    'max_price_change': float(np.max(price_changes))
                }
            
            logger.info(f"✅ Выполнено предсказание для {len(predictions)} целевых переменных")
            logger.info(f"📊 Валидных примеров: {len(X_valid)}/{len(X)}")
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Ошибка предсказания: {e}")
            return {'error': str(e)}
    
    def predict_single(self, features: Union[pd.Series, Dict, np.ndarray]) -> Dict[str, Any]:
        """
        Предсказание для одного набора признаков
        
        Args:
            features: Признаки для предсказания
            
        Returns:
            Словарь с предсказаниями
        """
        try:
            # Преобразуем в DataFrame
            if isinstance(features, dict):
                features_df = pd.DataFrame([features])
            elif isinstance(features, pd.Series):
                features_df = features.to_frame().T
            elif isinstance(features, np.ndarray):
                features_df = pd.DataFrame([features], columns=self.feature_names)
            else:
                features_df = pd.DataFrame([features])
            
            # Получаем предсказание
            result = self.predict(features_df)
            
            if 'error' in result:
                return result
            
            # Извлекаем результат для одного примера
            single_predictions = {}
            for target_name, pred_list in result['predictions'].items():
                if isinstance(pred_list, list) and len(pred_list) > 0:
                    single_predictions[target_name] = pred_list[0]
                else:
                    single_predictions[target_name] = pred_list
            
            single_result = {
                'predictions': single_predictions,
                'forecast_horizon': self.forecast_horizon,
                'timestamp': result['timestamp']
            }
            
            return single_result
            
        except Exception as e:
            logger.error(f"❌ Ошибка предсказания одного примера: {e}")
            return {'error': str(e)}
    
    def get_model_performance(self) -> Dict[str, Any]:
        """Получение метрик производительности всех моделей"""
        return self.performance_metrics
    
    def get_feature_importance(self, target_name: str = None) -> pd.DataFrame:
        """
        Получение важности признаков
        
        Args:
            target_name: Имя целевой переменной (если None, то для всех)
        """
        if not self.is_fitted:
            logger.warning("⚠️ Модели не обучены")
            return pd.DataFrame()
        
        try:
            if target_name and target_name in self.models:
                # Важность для конкретной модели
                model = self.models[target_name]
                if hasattr(model, 'feature_importances_'):
                    return pd.DataFrame({
                        'feature': self.feature_names,
                        'importance': model.feature_importances_,
                        'target': target_name
                    }).sort_values('importance', ascending=False)
            else:
                # Важность для всех моделей
                all_importance = []
                for target_name, model in self.models.items():
                    if hasattr(model, 'feature_importances_'):
                        for i, feature in enumerate(self.feature_names):
                            all_importance.append({
                                'feature': feature,
                                'importance': model.feature_importances_[i],
                                'target': target_name
                            })
                
                if all_importance:
                    df = pd.DataFrame(all_importance)
                    # Группируем по признакам и усредняем важность
                    avg_importance = df.groupby('feature')['importance'].mean().reset_index()
                    return avg_importance.sort_values('importance', ascending=False)
            
            return pd.DataFrame()
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения важности признаков: {e}")
            return pd.DataFrame()
    
    def save_models(self, directory: str):
        """Сохранение всех моделей"""
        try:
            Path(directory).mkdir(parents=True, exist_ok=True)
            
            # Сохраняем каждую модель отдельно
            for target_name, model in self.models.items():
                model_path = Path(directory) / f"{target_name}_model.joblib"
                joblib.dump(model, model_path)
            
            # Сохраняем скалеры
            scalers_path = Path(directory) / "scalers.joblib"
            joblib.dump(self.scalers, scalers_path)
            
            # Сохраняем метаданные
            metadata = {
                'model_type': self.model_type,
                'forecast_horizon': self.forecast_horizon,
                'price_targets': self.price_targets,
                'feature_names': self.feature_names,
                'performance_metrics': self.performance_metrics,
                'is_fitted': self.is_fitted,
                'timestamp': datetime.now().isoformat()
            }
            
            metadata_path = Path(directory) / "metadata.json"
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            logger.info(f"✅ Модели сохранены в {directory}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения моделей: {e}")
    
    def load_models(self, directory: str):
        """Загрузка всех моделей"""
        try:
            directory = Path(directory)
            
            # Загружаем метаданные
            metadata_path = directory / "metadata.json"
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            
            self.model_type = metadata['model_type']
            self.forecast_horizon = metadata['forecast_horizon']
            self.price_targets = metadata['price_targets']
            self.feature_names = metadata['feature_names']
            self.performance_metrics = metadata['performance_metrics']
            self.is_fitted = metadata['is_fitted']
            
            # Загружаем скалеры
            scalers_path = directory / "scalers.joblib"
            self.scalers = joblib.load(scalers_path)
            
            # Загружаем модели
            self.models = {}
            for target_name in self.price_targets:
                model_path = directory / f"{target_name}_model.joblib"
                if model_path.exists():
                    self.models[target_name] = joblib.load(model_path)
            
            logger.info(f"✅ Модели загружены из {directory}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки моделей: {e}")
    
    def get_model_info(self) -> Dict[str, Any]:
        """Получение информации о моделях"""
        return {
            'model_type': self.model_type,
            'forecast_horizon': self.forecast_horizon,
            'price_targets': self.price_targets,
            'scaling_method': self.scaling_method,
            'is_fitted': self.is_fitted,
            'features_count': len(self.feature_names),
            'models_count': len(self.models),
            'feature_names': self.feature_names,
            'performance_metrics': self.performance_metrics,
            'training_history_count': len(self.training_history),
            'sklearn_available': SKLEARN_AVAILABLE
        }

# ✅ ЭКСПОРТ
__all__ = [
    'PriceLevelRegressor'
]