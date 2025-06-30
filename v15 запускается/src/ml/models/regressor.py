"""
ML Regressor для предсказания уровней Take Profit и Stop Loss
Файл: src/ml/models/regressor.py
"""
import numpy as np
import pandas as pd
from typing import Dict, Tuple, List, Optional, Any
from datetime import datetime
import joblib
import json

from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import xgboost as xgb

from sqlalchemy.orm import Session
from ...core.database import SessionLocal
from ...logging.smart_logger import SmartLogger


class PriceLevelRegressor:
    """
    Регрессор для предсказания оптимальных уровней TP/SL
    """
    
    def __init__(self, model_type: str = 'xgboost'):
        self.model_type = model_type
        self.models = {
            'tp_model': None,
            'sl_model': None
        }
        self.scalers = {
            'features': StandardScaler(),
            'tp_target': StandardScaler(),
            'sl_target': StandardScaler()
        }
        self.feature_names = []
        self.model_params = {}
        self.performance_metrics = {}
        self.logger = SmartLogger(__name__)
        
    def _create_model(self) -> Any:
        """Создает модель выбранного типа"""
        if self.model_type == 'xgboost':
            return xgb.XGBRegressor(
                n_estimators=200,
                max_depth=6,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=42,
                n_jobs=-1
            )
        elif self.model_type == 'random_forest':
            return RandomForestRegressor(
                n_estimators=200,
                max_depth=10,
                min_samples_split=5,
                min_samples_leaf=2,
                random_state=42,
                n_jobs=-1
            )
        elif self.model_type == 'gradient_boosting':
            return GradientBoostingRegressor(
                n_estimators=200,
                max_depth=6,
                learning_rate=0.05,
                subsample=0.8,
                random_state=42
            )
        elif self.model_type == 'neural_network':
            return MLPRegressor(
                hidden_layer_sizes=(100, 50, 25),
                activation='relu',
                solver='adam',
                learning_rate_rate='adaptive',
                max_iter=500,
                early_stopping=True,
                validation_fraction=0.2,
                random_state=42
            )
        else:
            raise ValueError(f"Unknown model type: {self.model_type}")
    
    def prepare_target_data(self, df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
        """
        Подготавливает целевые переменные для обучения
        
        Returns:
            tp_targets: Оптимальные уровни Take Profit (в %)
            sl_targets: Оптимальные уровни Stop Loss (в %)
        """
        # Рассчитываем оптимальные уровни на основе исторических данных
        tp_targets = []
        sl_targets = []
        
        for i in range(len(df) - 100):  # Оставляем место для анализа
            current_price = df.iloc[i]['close']
            future_prices = df.iloc[i+1:i+101]['close'].values
            future_highs = df.iloc[i+1:i+101]['high'].values
            future_lows = df.iloc[i+1:i+101]['low'].values
            
            # Находим максимальное движение вверх
            max_profit = np.max((future_highs - current_price) / current_price) * 100
            
            # Находим максимальное движение вниз
            max_loss = np.min((future_lows - current_price) / current_price) * 100
            
            # Адаптивные уровни на основе волатильности
            volatility = df.iloc[max(0, i-20):i]['close'].pct_change().std() * 100
            
            # TP: 70% от максимального движения с учетом волатильности
            optimal_tp = min(max_profit * 0.7, volatility * 2.5)
            
            # SL: 150% от средней волатильности
            optimal_sl = min(abs(max_loss) * 0.5, volatility * 1.5)
            
            tp_targets.append(optimal_tp)
            sl_targets.append(optimal_sl)
        
        # Дополняем последние значения средними
        avg_tp = np.mean(tp_targets)
        avg_sl = np.mean(sl_targets)
        
        for _ in range(100):
            tp_targets.append(avg_tp)
            sl_targets.append(avg_sl)
        
        return pd.Series(tp_targets), pd.Series(sl_targets)
    
    def train(self, features: pd.DataFrame, market_data: pd.DataFrame,
              validation_split: float = 0.2) -> Dict[str, float]:
        """
        Обучает регрессионные модели для TP и SL
        
        Args:
            features: Признаки для обучения
            market_data: Исходные рыночные данные для расчета targets
            validation_split: Доля валидационной выборки
            
        Returns:
            Метрики обучения
        """
        self.logger.info(
            f"Начало обучения регрессора {self.model_type}",
            category='ml',
            model_type=self.model_type
        )
        
        # Подготавливаем целевые переменные
        tp_targets, sl_targets = self.prepare_target_data(market_data)
        
        # Выравниваем размеры
        min_len = min(len(features), len(tp_targets))
        features = features.iloc[:min_len]
        tp_targets = tp_targets.iloc[:min_len]
        sl_targets = sl_targets.iloc[:min_len]
        
        # Сохраняем названия признаков
        self.feature_names = features.columns.tolist()
        
        # Масштабирование
        X_scaled = self.scalers['features'].fit_transform(features)
        tp_scaled = self.scalers['tp_target'].fit_transform(tp_targets.values.reshape(-1, 1)).ravel()
        sl_scaled = self.scalers['sl_target'].fit_transform(sl_targets.values.reshape(-1, 1)).ravel()
        
        # Разделение на train/validation
        split_idx = int(len(X_scaled) * (1 - validation_split))
        
        X_train, X_val = X_scaled[:split_idx], X_scaled[split_idx:]
        tp_train, tp_val = tp_scaled[:split_idx], tp_scaled[split_idx:]
        sl_train, sl_val = sl_scaled[:split_idx], sl_scaled[split_idx:]
        
        # Обучение модели для TP
        self.logger.info("Обучение модели Take Profit", category='ml')
        self.models['tp_model'] = self._create_model()
        self.models['tp_model'].fit(X_train, tp_train)
        
        # Обучение модели для SL
        self.logger.info("Обучение модели Stop Loss", category='ml')
        self.models['sl_model'] = self._create_model()
        self.models['sl_model'].fit(X_train, sl_train)
        
        # Оценка на валидации
        tp_pred_val = self.models['tp_model'].predict(X_val)
        sl_pred_val = self.models['sl_model'].predict(X_val)
        
        # Обратное масштабирование для метрик
        tp_pred_original = self.scalers['tp_target'].inverse_transform(tp_pred_val.reshape(-1, 1)).ravel()
        tp_val_original = self.scalers['tp_target'].inverse_transform(tp_val.reshape(-1, 1)).ravel()
        
        sl_pred_original = self.scalers['sl_target'].inverse_transform(sl_pred_val.reshape(-1, 1)).ravel()
        sl_val_original = self.scalers['sl_target'].inverse_transform(sl_val.reshape(-1, 1)).ravel()
        
        # Расчет метрик
        metrics = {
            'tp_mse': mean_squared_error(tp_val_original, tp_pred_original),
            'tp_mae': mean_absolute_error(tp_val_original, tp_pred_original),
            'tp_r2': r2_score(tp_val_original, tp_pred_original),
            'sl_mse': mean_squared_error(sl_val_original, sl_pred_original),
            'sl_mae': mean_absolute_error(sl_val_original, sl_pred_original),
            'sl_r2': r2_score(sl_val_original, sl_pred_original),
            'avg_tp_predicted': float(np.mean(tp_pred_original)),
            'avg_sl_predicted': float(np.mean(sl_pred_original)),
            'std_tp_predicted': float(np.std(tp_pred_original)),
            'std_sl_predicted': float(np.std(sl_pred_original))
        }
        
        self.performance_metrics = metrics
        
        # Кросс-валидация для надежности
        if self.model_type != 'neural_network':  # MLP не поддерживает negative MSE
            cv_scores_tp = cross_val_score(
                self.models['tp_model'], X_scaled, tp_scaled,
                cv=5, scoring='neg_mean_squared_error'
            )
            cv_scores_sl = cross_val_score(
                self.models['sl_model'], X_scaled, sl_scaled,
                cv=5, scoring='neg_mean_squared_error'
            )
            
            metrics['tp_cv_mse_mean'] = float(-np.mean(cv_scores_tp))
            metrics['tp_cv_mse_std'] = float(np.std(cv_scores_tp))
            metrics['sl_cv_mse_mean'] = float(-np.mean(cv_scores_sl))
            metrics['sl_cv_mse_std'] = float(np.std(cv_scores_sl))
        
        # Важность признаков
        if hasattr(self.models['tp_model'], 'feature_importances_'):
            feature_importance = dict(zip(
                self.feature_names,
                self.models['tp_model'].feature_importances_
            ))
            metrics['feature_importance_tp'] = feature_importance
        
        self.logger.info(
            f"Обучение завершено. TP R²: {metrics['tp_r2']:.3f}, SL R²: {metrics['sl_r2']:.3f}",
            category='ml',
            metrics=metrics
        )
        
        return metrics
    
    def predict(self, features: pd.DataFrame) -> Dict[str, np.ndarray]:
        """
        Предсказывает оптимальные уровни TP и SL
        
        Args:
            features: Признаки для предсказания
            
        Returns:
            Dict с предсказанными уровнями TP и SL в процентах
        """
        if not self.models['tp_model'] or not self.models['sl_model']:
            raise ValueError("Модели не обучены. Сначала вызовите train()")
        
        # Проверка признаков
        missing_features = set(self.feature_names) - set(features.columns)
        if missing_features:
            raise ValueError(f"Отсутствуют признаки: {missing_features}")
        
        # Упорядочиваем признаки
        features = features[self.feature_names]
        
        # Масштабирование
        X_scaled = self.scalers['features'].transform(features)
        
        # Предсказание
        tp_pred_scaled = self.models['tp_model'].predict(X_scaled)
        sl_pred_scaled = self.models['sl_model'].predict(X_scaled)
        
        # Обратное масштабирование
        tp_pred = self.scalers['tp_target'].inverse_transform(tp_pred_scaled.reshape(-1, 1)).ravel()
        sl_pred = self.scalers['sl_target'].inverse_transform(sl_pred_scaled.reshape(-1, 1)).ravel()
        
        # Ограничения для безопасности
        tp_pred = np.clip(tp_pred, 0.5, 10.0)  # TP от 0.5% до 10%
        sl_pred = np.clip(sl_pred, 0.3, 5.0)   # SL от 0.3% до 5%
        
        return {
            'take_profit_percent': tp_pred,
            'stop_loss_percent': sl_pred
        }
    
    def predict_with_confidence(self, features: pd.DataFrame) -> Dict[str, Any]:
        """
        Предсказание с оценкой уверенности
        
        Returns:
            Предсказания с интервалами уверенности
        """
        base_predictions = self.predict(features)
        
        # Для ансамблевых методов можем оценить неопределенность
        if self.model_type in ['random_forest', 'xgboost']:
            # Используем стандартное отклонение предсказаний деревьев
            X_scaled = self.scalers['features'].transform(features[self.feature_names])
            
            if self.model_type == 'random_forest':
                # Получаем предсказания от каждого дерева
                tp_trees = np.array([tree.predict(X_scaled) for tree in self.models['tp_model'].estimators_])
                sl_trees = np.array([tree.predict(X_scaled) for tree in self.models['sl_model'].estimators_])
                
                tp_std = np.std(tp_trees, axis=0)
                sl_std = np.std(sl_trees, axis=0)
            else:
                # Для XGBoost используем приближение
                tp_std = np.ones(len(features)) * self.performance_metrics.get('std_tp_predicted', 1.0) * 0.2
                sl_std = np.ones(len(features)) * self.performance_metrics.get('std_sl_predicted', 0.5) * 0.2
            
            # Обратное масштабирование std
            tp_std = self.scalers['tp_target'].scale_[0] * tp_std
            sl_std = self.scalers['sl_target'].scale_[0] * sl_std
            
            confidence_intervals = {
                'tp_lower': base_predictions['take_profit_percent'] - 2 * tp_std,
                'tp_upper': base_predictions['take_profit_percent'] + 2 * tp_std,
                'sl_lower': base_predictions['stop_loss_percent'] - 2 * sl_std,
                'sl_upper': base_predictions['stop_loss_percent'] + 2 * sl_std,
                'tp_confidence': 1 / (1 + tp_std),  # Простая метрика уверенности
                'sl_confidence': 1 / (1 + sl_std)
            }
        else:
            # Для других моделей используем эвристику
            confidence_intervals = {
                'tp_lower': base_predictions['take_profit_percent'] * 0.8,
                'tp_upper': base_predictions['take_profit_percent'] * 1.2,
                'sl_lower': base_predictions['stop_loss_percent'] * 0.8,
                'sl_upper': base_predictions['stop_loss_percent'] * 1.2,
                'tp_confidence': np.ones(len(features)) * 0.7,
                'sl_confidence': np.ones(len(features)) * 0.7
            }
        
        return {
            **base_predictions,
            **confidence_intervals
        }
    
    def update_with_results(self, predictions: List[Dict], actual_results: List[Dict]):
        """
        Обновляет модель на основе реальных результатов (для online learning)
        
        Args:
            predictions: Список предсказаний модели
            actual_results: Реальные результаты торговли
        """
        # Собираем данные для дообучения
        feedback_data = []
        
        for pred, result in zip(predictions, actual_results):
            feedback = {
                'predicted_tp': pred['take_profit_percent'],
                'predicted_sl': pred['stop_loss_percent'],
                'actual_max_profit': result.get('max_profit_percent', 0),
                'actual_max_loss': result.get('max_loss_percent', 0),
                'exit_reason': result.get('exit_reason', 'unknown'),
                'profit_realized': result.get('profit_percent', 0)
            }
            feedback_data.append(feedback)
        
        # Анализируем ошибки предсказаний
        tp_errors = []
        sl_errors = []
        
        for fb in feedback_data:
            if fb['exit_reason'] == 'take_profit':
                tp_errors.append(abs(fb['predicted_tp'] - fb['actual_max_profit']))
            elif fb['exit_reason'] == 'stop_loss':
                sl_errors.append(abs(fb['predicted_sl'] - abs(fb['actual_max_loss'])))
        
        if tp_errors:
            avg_tp_error = np.mean(tp_errors)
            self.logger.info(
                f"Средняя ошибка TP: {avg_tp_error:.2f}%",
                category='ml',
                model_type=self.model_type
            )
        
        if sl_errors:
            avg_sl_error = np.mean(sl_errors)
            self.logger.info(
                f"Средняя ошибка SL: {avg_sl_error:.2f}%",
                category='ml',
                model_type=self.model_type
            )
        
        # Сохраняем для будущего переобучения
        self.model_params['feedback_data'] = feedback_data
    
    def save_model(self, path: str):
        """Сохраняет модель и параметры"""
        model_data = {
            'model_type': self.model_type,
            'tp_model': self.models['tp_model'],
            'sl_model': self.models['sl_model'],
            'scalers': self.scalers,
            'feature_names': self.feature_names,
            'performance_metrics': self.performance_metrics,
            'model_params': self.model_params,
            'version': '1.0',
            'created_at': datetime.now().isoformat()
        }
        
        joblib.dump(model_data, path)
        self.logger.info(
            f"Модель сохранена: {path}",
            category='ml',
            model_type=self.model_type
        )
    
    def load_model(self, path: str):
        """Загружает модель и параметры"""
        model_data = joblib.load(path)
        
        self.model_type = model_data['model_type']
        self.models = {
            'tp_model': model_data['tp_model'],
            'sl_model': model_data['sl_model']
        }
        self.scalers = model_data['scalers']
        self.feature_names = model_data['feature_names']
        self.performance_metrics = model_data['performance_metrics']
        self.model_params = model_data.get('model_params', {})
        
        self.logger.info(
            f"Модель загружена: {path}",
            category='ml',
            model_type=self.model_type,
            metrics=self.performance_metrics
        )
    
    def get_adaptive_levels(self, features: pd.DataFrame, 
                           market_conditions: Dict[str, Any]) -> Dict[str, np.ndarray]:
        """
        Получает адаптивные уровни с учетом рыночных условий
        
        Args:
            features: Признаки
            market_conditions: Текущие рыночные условия
            
        Returns:
            Адаптированные уровни TP/SL
        """
        # Базовое предсказание
        base_pred = self.predict_with_confidence(features)
        
        # Адаптация под рыночные условия
        volatility_factor = market_conditions.get('volatility', 1.0)
        trend_strength = market_conditions.get('trend_strength', 0.0)
        volume_ratio = market_conditions.get('volume_ratio', 1.0)
        
        # Корректировка TP
        # В волатильном рынке увеличиваем TP
        tp_adjusted = base_pred['take_profit_percent'] * (1 + 0.2 * (volatility_factor - 1))
        
        # В сильном тренде увеличиваем TP
        tp_adjusted *= (1 + 0.1 * abs(trend_strength))
        
        # При высоком объеме увеличиваем уверенность
        if volume_ratio > 1.5:
            tp_adjusted *= 1.1
        
        # Корректировка SL
        # В волатильном рынке увеличиваем SL
        sl_adjusted = base_pred['stop_loss_percent'] * (1 + 0.3 * (volatility_factor - 1))
        
        # Против тренда - более жесткий SL
        if trend_strength < -0.5:  # Нисходящий тренд
            sl_adjusted *= 0.8
        
        # Применяем ограничения
        tp_adjusted = np.clip(tp_adjusted, 0.5, 15.0)
        sl_adjusted = np.clip(sl_adjusted, 0.3, 7.0)
        
        return {
            'take_profit_percent': tp_adjusted,
            'stop_loss_percent': sl_adjusted,
            'tp_confidence': base_pred['tp_confidence'],
            'sl_confidence': base_pred['sl_confidence'],
            'adjustments': {
                'volatility_factor': volatility_factor,
                'trend_strength': trend_strength,
                'volume_ratio': volume_ratio
            }
        }


class MultiTimeframeRegressor:
    """
    Регрессор, учитывающий несколько таймфреймов
    """
    
    def __init__(self, timeframes: List[str] = ['5m', '15m', '1h', '4h']):
        self.timeframes = timeframes
        self.regressors = {tf: PriceLevelRegressor() for tf in timeframes}
        self.weights = {tf: 1.0 / len(timeframes) for tf in timeframes}
        self.logger = SmartLogger(__name__)
    
    def train_all(self, features_dict: Dict[str, pd.DataFrame],
                  market_data_dict: Dict[str, pd.DataFrame]) -> Dict[str, Dict]:
        """
        Обучает регрессоры для всех таймфреймов
        
        Args:
            features_dict: Словарь с признаками для каждого таймфрейма
            market_data_dict: Словарь с рыночными данными
            
        Returns:
            Метрики для каждого таймфрейма
        """
        all_metrics = {}
        
        for tf in self.timeframes:
            if tf in features_dict and tf in market_data_dict:
                self.logger.info(f"Обучение регрессора для {tf}", category='ml')
                
                metrics = self.regressors[tf].train(
                    features_dict[tf],
                    market_data_dict[tf]
                )
                all_metrics[tf] = metrics
                
                # Обновляем веса на основе производительности
                r2_score = (metrics['tp_r2'] + metrics['sl_r2']) / 2
                self.weights[tf] = max(0.1, r2_score)
        
        # Нормализуем веса
        total_weight = sum(self.weights.values())
        self.weights = {tf: w / total_weight for tf, w in self.weights.items()}
        
        self.logger.info(
            "Обучение multi-timeframe завершено",
            category='ml',
            weights=self.weights,
            metrics=all_metrics
        )
        
        return all_metrics
    
    def predict_ensemble(self, features_dict: Dict[str, pd.DataFrame]) -> Dict[str, np.ndarray]:
        """
        Ансамблевое предсказание с учетом всех таймфреймов
        
        Returns:
            Взвешенные предсказания TP/SL
        """
        all_predictions = []
        weights_used = []
        
        for tf in self.timeframes:
            if tf in features_dict and self.regressors[tf].models['tp_model']:
                pred = self.regressors[tf].predict(features_dict[tf])
                all_predictions.append(pred)
                weights_used.append(self.weights[tf])
        
        if not all_predictions:
            raise ValueError("Нет обученных моделей для предсказания")
        
        # Взвешенное усреднение
        tp_ensemble = np.zeros_like(all_predictions[0]['take_profit_percent'])
        sl_ensemble = np.zeros_like(all_predictions[0]['stop_loss_percent'])
        
        for pred, weight in zip(all_predictions, weights_used):
            tp_ensemble += pred['take_profit_percent'] * weight
            sl_ensemble += pred['stop_loss_percent'] * weight
        
        # Нормализация (weights_used уже нормализованы)
        total_weight = sum(weights_used)
        tp_ensemble /= total_weight
        sl_ensemble /= total_weight
        
        return {
            'take_profit_percent': tp_ensemble,
            'stop_loss_percent': sl_ensemble,
            'timeframes_used': len(all_predictions),
            'weights': dict(zip(self.timeframes, weights_used))
        }