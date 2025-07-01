#!/usr/bin/env python3
"""
Direction Classifier для предсказания направления цены - ИСПРАВЛЕННАЯ ВЕРСИЯ
==========================================================================
Файл: src/ml/models/direction_classifier.py

✅ ИСПРАВЛЯЕТ: No module named 'src.ml.models.direction_classifier'
✅ Полная совместимость с существующей системой
✅ Профессиональная реализация с несколькими алгоритмами
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
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.svm import SVC
    from sklearn.naive_bayes import GaussianNB
    from sklearn.model_selection import train_test_split, cross_val_score, GridSearchCV
    from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, classification_report, confusion_matrix
    from sklearn.preprocessing import StandardScaler, LabelEncoder
    from sklearn.pipeline import Pipeline
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

class DirectionClassifier:
    """
    ✅ ИСПРАВЛЕННЫЙ: Классификатор направления движения цены
    
    Предсказывает будущее направление движения цены (UP/DOWN/SIDEWAYS)
    на основе технических индикаторов и рыночных данных.
    """
    
    def __init__(self, 
                 model_type: str = 'random_forest',
                 forecast_horizon: int = 5,
                 threshold: float = 0.01,
                 confidence_threshold: float = 0.6):
        """
        Инициализация классификатора направления
        
        Args:
            model_type: Тип модели ('random_forest', 'gradient_boosting', 'logistic', 'svm', 'ensemble')
            forecast_horizon: Горизонт прогнозирования (количество периодов)
            threshold: Минимальное движение цены для UP/DOWN (в процентах)
            confidence_threshold: Минимальная уверенность для принятия решений
        """
        self.model_type = model_type
        self.forecast_horizon = forecast_horizon
        self.threshold = threshold
        self.confidence_threshold = confidence_threshold
        
        # Инициализация модели
        self.model = None
        self.scaler = StandardScaler() if SKLEARN_AVAILABLE else None
        self.label_encoder = LabelEncoder() if SKLEARN_AVAILABLE else None
        self.feature_names: List[str] = []
        self.is_fitted = False
        
        # Метрики производительности
        self.performance_metrics = {}
        self.training_history = []
        
        # Параметры модели
        self.model_params = self._get_default_params()
        
        # Инициализация модели
        if SKLEARN_AVAILABLE:
            self._initialize_model()
        
        logger.info(f"✅ DirectionClassifier инициализирован: {model_type}")
    
    def _get_default_params(self) -> Dict[str, Any]:
        """Получение параметров по умолчанию для разных моделей"""
        params = {
            'random_forest': {
                'n_estimators': 100,
                'max_depth': 10,
                'min_samples_split': 5,
                'min_samples_leaf': 2,
                'random_state': 42
            },
            'gradient_boosting': {
                'n_estimators': 100,
                'learning_rate': 0.1,
                'max_depth': 6,
                'random_state': 42
            },
            'logistic': {
                'max_iter': 1000,
                'random_state': 42,
                'solver': 'liblinear'
            },
            'svm': {
                'kernel': 'rbf',
                'probability': True,
                'random_state': 42
            },
            'naive_bayes': {}
        }
        
        return params.get(self.model_type, {})
    
    def _initialize_model(self):
        """Инициализация модели ML"""
        if not SKLEARN_AVAILABLE:
            logger.error("❌ scikit-learn недоступен")
            return
        
        try:
            if self.model_type == 'random_forest':
                self.model = RandomForestClassifier(**self.model_params)
            elif self.model_type == 'gradient_boosting':
                self.model = GradientBoostingClassifier(**self.model_params)
            elif self.model_type == 'logistic':
                self.model = LogisticRegression(**self.model_params)
            elif self.model_type == 'svm':
                self.model = SVC(**self.model_params)
            elif self.model_type == 'naive_bayes':
                self.model = GaussianNB(**self.model_params)
            elif self.model_type == 'ensemble':
                self._initialize_ensemble()
            else:
                logger.warning(f"⚠️ Неизвестный тип модели: {self.model_type}, используем Random Forest")
                self.model = RandomForestClassifier(**self.model_params['random_forest'])
                self.model_type = 'random_forest'
            
            logger.info(f"✅ Модель {self.model_type} инициализирована")
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации модели: {e}")
            # Fallback на простую модель
            self.model = RandomForestClassifier(n_estimators=50, random_state=42)
    
    def _initialize_ensemble(self):
        """Инициализация ансамбля моделей"""
        try:
            from sklearn.ensemble import VotingClassifier
            
            # Создаем базовые модели
            models = [
                ('rf', RandomForestClassifier(n_estimators=50, random_state=42)),
                ('gb', GradientBoostingClassifier(n_estimators=50, random_state=42)),
                ('lr', LogisticRegression(max_iter=1000, random_state=42))
            ]
            
            self.model = VotingClassifier(
                estimators=models,
                voting='soft'  # Используем вероятности
            )
            
            logger.info("✅ Ансамбль моделей инициализирован")
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания ансамбля: {e}")
            self.model = RandomForestClassifier(n_estimators=50, random_state=42)
    
    def prepare_labels(self, df: pd.DataFrame, price_column: str = 'close') -> np.ndarray:
        """
        Подготовка меток для обучения
        
        Args:
            df: DataFrame с ценовыми данными
            price_column: Название колонки с ценой
            
        Returns:
            Массив меток (0=DOWN, 1=SIDEWAYS, 2=UP)
        """
        try:
            # Вычисляем будущее изменение цены
            future_returns = df[price_column].pct_change(periods=self.forecast_horizon).shift(-self.forecast_horizon)
            
            # Создаем метки классов
            labels = np.where(
                future_returns > self.threshold, 2,  # UP
                np.where(future_returns < -self.threshold, 0, 1)  # DOWN или SIDEWAYS
            )
            
            # Удаляем последние строки где нет будущих данных
            valid_labels = labels[:-self.forecast_horizon]
            
            logger.info(f"✅ Подготовлено {len(valid_labels)} меток")
            logger.info(f"📊 Распределение классов: UP={np.sum(valid_labels==2)}, "
                       f"SIDEWAYS={np.sum(valid_labels==1)}, DOWN={np.sum(valid_labels==0)}")
            
            return valid_labels
            
        except Exception as e:
            logger.error(f"❌ Ошибка подготовки меток: {e}")
            return np.array([])
    
    def train(self, 
              features_df: pd.DataFrame, 
              price_column: str = 'close',
              test_size: float = 0.2,
              validate: bool = True) -> Dict[str, Any]:
        """
        Обучение модели
        
        Args:
            features_df: DataFrame с признаками и ценами
            price_column: Название колонки с ценой
            test_size: Размер тестовой выборки
            validate: Проводить ли валидацию
            
        Returns:
            Словарь с метриками обучения
        """
        if not SKLEARN_AVAILABLE:
            logger.error("❌ scikit-learn недоступен")
            return {'error': 'sklearn_unavailable'}
        
        try:
            logger.info("🎯 Начало обучения DirectionClassifier...")
            
            # Подготовка признаков
            feature_columns = [col for col in features_df.columns 
                             if col not in ['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            
            if not feature_columns:
                logger.error("❌ Нет признаков для обучения")
                return {'error': 'no_features'}
            
            self.feature_names = feature_columns
            
            # Подготовка данных
            X = features_df[feature_columns].copy()
            y = self.prepare_labels(features_df, price_column)
            
            if len(y) == 0:
                logger.error("❌ Нет меток для обучения")
                return {'error': 'no_labels'}
            
            # Убираем строки с будущими данными из признаков
            X = X.iloc[:-self.forecast_horizon]
            
            # Проверяем совпадение размеров
            if len(X) != len(y):
                min_len = min(len(X), len(y))
                X = X.iloc[:min_len]
                y = y[:min_len]
            
            # Удаляем строки с NaN
            valid_indices = ~(X.isnull().any(axis=1) | pd.isnull(y))
            X = X[valid_indices]
            y = y[valid_indices]
            
            if len(X) == 0:
                logger.error("❌ Нет валидных данных после очистки")
                return {'error': 'no_valid_data'}
            
            # Масштабирование признаков
            X_scaled = self.scaler.fit_transform(X)
            
            # Разделение на обучение и тест
            X_train, X_test, y_train, y_test = train_test_split(
                X_scaled, y, test_size=test_size, random_state=42, stratify=y
            )
            
            # Обучение модели
            start_time = datetime.now()
            self.model.fit(X_train, y_train)
            training_time = (datetime.now() - start_time).total_seconds()
            
            # Предсказания
            y_pred_train = self.model.predict(X_train)
            y_pred_test = self.model.predict(X_test)
            
            # Вероятности для оценки уверенности
            if hasattr(self.model, 'predict_proba'):
                y_proba_test = self.model.predict_proba(X_test)
                confidence = np.max(y_proba_test, axis=1).mean()
            else:
                confidence = 0.0
            
            # Метрики
            train_accuracy = accuracy_score(y_train, y_pred_train)
            test_accuracy = accuracy_score(y_test, y_pred_test)
            
            metrics = {
                'train_accuracy': train_accuracy,
                'test_accuracy': test_accuracy,
                'precision': precision_score(y_test, y_pred_test, average='weighted', zero_division=0),
                'recall': recall_score(y_test, y_pred_test, average='weighted', zero_division=0),
                'f1_score': f1_score(y_test, y_pred_test, average='weighted', zero_division=0),
                'confidence': confidence,
                'training_time': training_time,
                'train_samples': len(X_train),
                'test_samples': len(X_test),
                'features_count': len(feature_columns),
                'class_distribution': {
                    'UP': int(np.sum(y == 2)),
                    'SIDEWAYS': int(np.sum(y == 1)),
                    'DOWN': int(np.sum(y == 0))
                }
            }
            
            # Кросс-валидация
            if validate and len(X) > 100:
                try:
                    cv_scores = cross_val_score(self.model, X_scaled, y, cv=5, scoring='accuracy')
                    metrics['cv_mean'] = cv_scores.mean()
                    metrics['cv_std'] = cv_scores.std()
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка кросс-валидации: {e}")
                    metrics['cv_mean'] = 0.0
                    metrics['cv_std'] = 0.0
            
            # Сохраняем метрики
            self.performance_metrics = metrics
            self.is_fitted = True
            
            # Добавляем в историю
            self.training_history.append({
                'timestamp': datetime.now(),
                'metrics': metrics,
                'model_type': self.model_type,
                'samples_count': len(X)
            })
            
            logger.info(f"✅ Обучение завершено!")
            logger.info(f"📊 Точность на тесте: {test_accuracy:.3f}")
            logger.info(f"📊 F1-score: {metrics['f1_score']:.3f}")
            logger.info(f"📊 Уверенность: {confidence:.3f}")
            
            return metrics
            
        except Exception as e:
            logger.error(f"❌ Ошибка обучения: {e}")
            return {'error': str(e)}
    
    def predict(self, features_df: pd.DataFrame) -> Dict[str, Any]:
        """
        Предсказание направления движения цены
        
        Args:
            features_df: DataFrame с признаками
            
        Returns:
            Словарь с предсказаниями и вероятностями
        """
        if not self.is_fitted:
            logger.error("❌ Модель не обучена")
            return {'error': 'model_not_fitted'}
        
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
            
            # Масштабирование
            X_scaled = self.scaler.transform(X_valid)
            
            # Предсказания
            predictions = self.model.predict(X_scaled)
            
            # Вероятности
            if hasattr(self.model, 'predict_proba'):
                probabilities = self.model.predict_proba(X_scaled)
                confidence = np.max(probabilities, axis=1)
            else:
                probabilities = None
                confidence = np.ones(len(predictions)) * 0.5
            
            # Интерпретация результатов
            direction_names = {0: 'DOWN', 1: 'SIDEWAYS', 2: 'UP'}
            direction_labels = [direction_names[pred] for pred in predictions]
            
            # Фильтрация по уверенности
            high_confidence_mask = confidence >= self.confidence_threshold
            
            results = {
                'predictions': predictions.tolist(),
                'direction_labels': direction_labels,
                'confidence': confidence.tolist(),
                'probabilities': probabilities.tolist() if probabilities is not None else None,
                'high_confidence_count': int(np.sum(high_confidence_mask)),
                'total_predictions': len(predictions),
                'forecast_horizon': self.forecast_horizon,
                'threshold': self.threshold,
                'timestamp': datetime.now().isoformat(),
                'valid_indices': valid_indices.tolist()
            }
            
            # Сводная статистика
            unique, counts = np.unique(predictions, return_counts=True)
            direction_distribution = {direction_names[label]: int(count) 
                                   for label, count in zip(unique, counts)}
            results['direction_distribution'] = direction_distribution
            
            logger.info(f"✅ Сделано {len(predictions)} предсказаний")
            logger.info(f"📊 Распределение: {direction_distribution}")
            logger.info(f"📊 Высокая уверенность: {int(np.sum(high_confidence_mask))}/{len(predictions)}")
            
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
            Словарь с предсказанием
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
            single_result = {
                'prediction': result['predictions'][0],
                'direction': result['direction_labels'][0],
                'confidence': result['confidence'][0],
                'probabilities': result['probabilities'][0] if result['probabilities'] else None,
                'timestamp': result['timestamp']
            }
            
            return single_result
            
        except Exception as e:
            logger.error(f"❌ Ошибка предсказания одного примера: {e}")
            return {'error': str(e)}
    
    def evaluate(self, features_df: pd.DataFrame, price_column: str = 'close') -> Dict[str, Any]:
        """
        Оценка модели на новых данных
        
        Args:
            features_df: DataFrame с признаками и ценами
            price_column: Название колонки с ценой
            
        Returns:
            Словарь с метриками оценки
        """
        if not self.is_fitted:
            logger.error("❌ Модель не обучена")
            return {'error': 'model_not_fitted'}
        
        try:
            # Подготовка данных
            X = features_df[self.feature_names].copy()
            y_true = self.prepare_labels(features_df, price_column)
            
            if len(y_true) == 0:
                return {'error': 'no_labels'}
            
            # Убираем строки с будущими данными
            X = X.iloc[:-self.forecast_horizon]
            
            # Проверяем размеры
            min_len = min(len(X), len(y_true))
            X = X.iloc[:min_len]
            y_true = y_true[:min_len]
            
            # Удаляем NaN
            valid_indices = ~(X.isnull().any(axis=1) | pd.isnull(y_true))
            X = X[valid_indices]
            y_true = y_true[valid_indices]
            
            if len(X) == 0:
                return {'error': 'no_valid_data'}
            
            # Предсказания
            X_scaled = self.scaler.transform(X)
            y_pred = self.model.predict(X_scaled)
            
            # Метрики
            metrics = {
                'accuracy': accuracy_score(y_true, y_pred),
                'precision': precision_score(y_true, y_pred, average='weighted', zero_division=0),
                'recall': recall_score(y_true, y_pred, average='weighted', zero_division=0),
                'f1_score': f1_score(y_true, y_pred, average='weighted', zero_division=0),
                'samples_count': len(X),
                'timestamp': datetime.now().isoformat()
            }
            
            # Матрица ошибок
            try:
                cm = confusion_matrix(y_true, y_pred)
                metrics['confusion_matrix'] = cm.tolist()
            except Exception:
                pass
            
            logger.info(f"✅ Оценка завершена: точность {metrics['accuracy']:.3f}")
            return metrics
            
        except Exception as e:
            logger.error(f"❌ Ошибка оценки: {e}")
            return {'error': str(e)}
    
    def get_feature_importance(self) -> pd.DataFrame:
        """Получение важности признаков"""
        if not self.is_fitted:
            logger.warning("⚠️ Модель не обучена")
            return pd.DataFrame()
        
        try:
            if hasattr(self.model, 'feature_importances_'):
                importance = pd.DataFrame({
                    'feature': self.feature_names,
                    'importance': self.model.feature_importances_
                }).sort_values('importance', ascending=False)
                
                return importance
            else:
                logger.warning("⚠️ Модель не поддерживает feature_importances_")
                return pd.DataFrame()
                
        except Exception as e:
            logger.error(f"❌ Ошибка получения важности признаков: {e}")
            return pd.DataFrame()
    
    def save_model(self, filepath: str):
        """Сохранение модели"""
        try:
            model_data = {
                'model': self.model,
                'scaler': self.scaler,
                'feature_names': self.feature_names,
                'model_type': self.model_type,
                'forecast_horizon': self.forecast_horizon,
                'threshold': self.threshold,
                'confidence_threshold': self.confidence_threshold,
                'performance_metrics': self.performance_metrics,
                'training_history': self.training_history,
                'is_fitted': self.is_fitted,
                'timestamp': datetime.now().isoformat()
            }
            
            with open(filepath, 'wb') as f:
                pickle.dump(model_data, f)
            
            logger.info(f"✅ Модель сохранена: {filepath}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения модели: {e}")
    
    def load_model(self, filepath: str):
        """Загрузка модели"""
        try:
            with open(filepath, 'rb') as f:
                model_data = pickle.load(f)
            
            self.model = model_data['model']
            self.scaler = model_data['scaler']
            self.feature_names = model_data['feature_names']
            self.model_type = model_data['model_type']
            self.forecast_horizon = model_data['forecast_horizon']
            self.threshold = model_data['threshold']
            self.confidence_threshold = model_data['confidence_threshold']
            self.performance_metrics = model_data.get('performance_metrics', {})
            self.training_history = model_data.get('training_history', [])
            self.is_fitted = model_data.get('is_fitted', True)
            
            logger.info(f"✅ Модель загружена: {filepath}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки модели: {e}")
    
    def get_model_info(self) -> Dict[str, Any]:
        """Получение информации о модели"""
        return {
            'model_type': self.model_type,
            'forecast_horizon': self.forecast_horizon,
            'threshold': self.threshold,
            'confidence_threshold': self.confidence_threshold,
            'is_fitted': self.is_fitted,
            'features_count': len(self.feature_names),
            'feature_names': self.feature_names,
            'performance_metrics': self.performance_metrics,
            'training_history_count': len(self.training_history),
            'sklearn_available': SKLEARN_AVAILABLE
        }

# ✅ ЛЕГКАЯ ВЕРСИЯ ДЛЯ ТЕСТОВОГО РЕЖИМА
class DirectionClassifierLight:
    """Легкая версия классификатора для тестового режима"""
    
    def __init__(self, **kwargs):
        self.is_fitted = False
        self.feature_names = []
        
    def train(self, *args, **kwargs):
        self.is_fitted = True
        return {'accuracy': 0.65, 'test_mode': True}
    
    def predict(self, features_df):
        size = len(features_df)
        return {
            'predictions': [1] * size,
            'direction_labels': ['SIDEWAYS'] * size,
            'confidence': [0.6] * size,
            'test_mode': True
        }
    
    def predict_single(self, features):
        return {
            'prediction': 1,
            'direction': 'SIDEWAYS',
            'confidence': 0.6,
            'test_mode': True
        }

# ✅ ЭКСПОРТ
__all__ = [
    'DirectionClassifier',
    'DirectionClassifierLight'
]