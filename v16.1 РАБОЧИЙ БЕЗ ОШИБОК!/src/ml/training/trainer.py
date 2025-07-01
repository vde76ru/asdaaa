"""
Улучшенный Trainer для обучения и оценки ML моделей
Файл: src/ml/training/trainer.py

Объединяет полную функциональность с практической реализацией
"""
import asyncio
import numpy as np
import pandas as pd
import pickle
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime, timedelta
from sklearn.model_selection import train_test_split, TimeSeriesSplit
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    classification_report, confusion_matrix
)
from sklearn.ensemble import RandomForestClassifier
import json
from pathlib import Path

from sqlalchemy.orm import Session
from ...core.database import SessionLocal
from ...core.models import Trade, Signal
from ...core.unified_config import unified_config as Config
from ...logging.smart_logger import SmartLogger

# ✅ ИСПРАВЛЕНО: правильный путь к FeatureEngineer
try:
    from ..features.feature_engineering import FeatureEngineer
except ImportError:
    try:
        # Запасной вариант
        from ..feature_engineering import FeatureEngineer
    except ImportError:
        logger.warning("⚠️ FeatureEngineer недоступен")
        FeatureEngineer = None

# ✅ ИСПРАВЛЕНО: правильный путь к DirectionClassifier        
from ..models.direction_classifier import DirectionClassifier


class EnsembleModel:
    """
    Ансамбль ML моделей с взвешенным голосованием
    """
    
    def __init__(self, models: Dict, weights: Optional[List[float]] = None, name: str = "ensemble"):
        self.models = models
        self.weights = weights or [1/len(models)] * len(models)
        self.name = name
        self.feature_columns = None
        
        # Нормализуем веса
        total_weight = sum(self.weights)
        self.weights = [w / total_weight for w in self.weights]
    
    def predict_proba(self, X):
        """Предсказание вероятностей с взвешенным усреднением"""
        predictions = []
        model_names = list(self.models.keys())
        
        for i, (name, model) in enumerate(self.models.items()):
            try:
                if hasattr(model, 'predict_proba'):
                    pred = model.predict_proba(X)
                else:
                    # Для моделей без predict_proba создаем one-hot
                    pred_classes = model.predict(X)
                    unique_classes = np.unique(pred_classes)
                    pred = np.zeros((len(pred_classes), len(unique_classes)))
                    for j, cls in enumerate(unique_classes):
                        pred[pred_classes == cls, j] = 1.0
                
                predictions.append(pred * self.weights[i])
            except Exception as e:
                # Если модель сломана, пропускаем её
                continue
        
        if not predictions:
            raise ValueError("Все модели в ансамбле недоступны")
        
        # Суммируем взвешенные предсказания
        ensemble_pred = np.sum(predictions, axis=0)
        return ensemble_pred
    
    def predict(self, X):
        """Предсказание классов"""
        proba = self.predict_proba(X)
        return np.argmax(proba, axis=1) - 1  # Возвращаем -1, 0, 1
    
    def get_confidence(self, X):
        """Получение уверенности предсказания"""
        proba = self.predict_proba(X)
        return np.max(proba, axis=1)


class MLTrainer:
    """
    Улучшенный координатор обучения ML моделей
    """
    
    def __init__(self):
        self.logger = SmartLogger("ml.trainer")
        self.feature_engineer = FeatureEngineer()
        self.models = {}
        
        # Директории
        self.reports_dir = Path("reports/ml")
        self.models_dir = Path("models/trained")
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        # Конфигурация обучения
        self.training_config = {
            'min_samples': Config.ML_MIN_TRAINING_DATA or 1000,
            'val_split': 0.2,
            'test_split': 0.1,
            'retrain_interval_hours': Config.RETRAIN_INTERVAL_HOURS or 24,
            'model_types': ['random_forest', 'xgboost', 'lightgbm'],
            'symbols': [],
            'timeframes': ['5m', '15m', '1h'],
            'target_periods': 5,  # Предсказываем на 5 периодов вперед
            'lookback_periods': 2000
        }
        
        # История обучения
        self.training_history = []
        
        # Конфигурация моделей
        self.model_configs = {
            'random_forest': {
                'class': RandomForestClassifier,
                'params': {
                    'n_estimators': 100,
                    'max_depth': 10,
                    'min_samples_split': 5,
                    'min_samples_leaf': 2,
                    'class_weight': 'balanced',
                    'n_jobs': -1,
                    'random_state': 42
                }
            },
            'xgboost': {
                'params': {
                    'n_estimators': 100,
                    'max_depth': 6,
                    'learning_rate': 0.1,
                    'subsample': 0.8,
                    'colsample_bytree': 0.8,
                    'random_state': 42,
                    'eval_metric': 'mlogloss'
                }
            },
            'lightgbm': {
                'params': {
                    'n_estimators': 100,
                    'max_depth': 6,
                    'learning_rate': 0.1,
                    'subsample': 0.8,
                    'colsample_bytree': 0.8,
                    'class_weight': 'balanced',
                    'random_state': 42,
                    'verbose': -1
                }
            }
        }
    
    async def initialize(self):
        """Инициализация тренера"""
        db = SessionLocal()
        try:
            # Загружаем активные символы из конфигурации и БД
            if Config.TRADING_PAIRS:
                self.training_config['symbols'] = Config.TRADING_PAIRS
            else:
                # Получаем уникальные символы из недавних сделок
                recent_trades = db.query(Trade.symbol).distinct().limit(50).all()
                self.training_config['symbols'] = [t[0] for t in recent_trades]
            
            if not self.training_config['symbols']:
                # Если нет данных, используем популярные пары
                self.training_config['symbols'] = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']
            
            self.logger.info(
                "ML Trainer инициализирован",
                category='ml',
                symbols=self.training_config['symbols'][:5],  # Показываем первые 5
                total_symbols=len(self.training_config['symbols']),
                model_types=self.training_config['model_types']
            )
            
        finally:
            db.close()
    
    async def train_symbol_model(self, symbol: str, timeframe: str = '5m') -> Dict[str, Any]:
        """
        РЕАЛЬНОЕ обучение модели для конкретного символа
        """
        try:
            self.logger.info(f"🚀 Начинаем обучение модели для {symbol}", category='ml', symbol=symbol)
            
            # === 1. ПОДГОТОВКА ДАННЫХ ===
            df = await self.feature_engineer.extract_features(
                symbol=symbol,
                timeframe=timeframe,
                lookback_periods=self.training_config['lookback_periods']
            )
            
            if df.empty:
                return {'success': False, 'error': 'Нет данных для обучения'}
            
            X, y = self.feature_engineer.prepare_training_data(
                df,
                target_type='direction',
                target_periods=self.training_config['target_periods']
            )
            
            if len(X) < self.training_config['min_samples']:
                return {
                    'success': False,
                    'error': f'Недостаточно данных: {len(X)} < {self.training_config["min_samples"]}'
                }
            
            # === 2. ВРЕМЕННОЕ РАЗДЕЛЕНИЕ ДАННЫХ ===
            # Важно для временных рядов!
            test_size = int(len(X) * self.training_config['test_split'])
            X_temp, X_test = X[:-test_size], X[-test_size:]
            y_temp, y_test = y[:-test_size], y[-test_size:]
            
            # Валидационная выборка
            val_size = int(len(X_temp) * self.training_config['val_split'])
            X_train, X_val = X_temp[:-val_size], X_temp[-val_size:]
            y_train, y_val = y_temp[:-val_size], y_temp[-val_size:]
            
            self.logger.info(
                f"Данные подготовлены для {symbol}",
                category='ml',
                train_size=len(X_train),
                val_size=len(X_val),
                test_size=len(X_test),
                class_distribution=y_train.value_counts().to_dict()
            )
            
            # === 3. ОБУЧЕНИЕ МОДЕЛЕЙ ===
            trained_models = {}
            results = {}
            
            # Random Forest (всегда доступен)
            try:
                rf_config = self.model_configs['random_forest']
                rf_model = rf_config['class'](**rf_config['params'])
                rf_model.fit(X_train, y_train)
                trained_models['random_forest'] = rf_model
                
                # Оценка
                results['random_forest'] = await self._evaluate_model(
                    rf_model, X_train, y_train, X_val, y_val, X_test, y_test
                )
                
            except Exception as e:
                self.logger.error(f"Ошибка обучения Random Forest: {e}", category='ml')
            
            # XGBoost (опционально)
            try:
                import xgboost as xgb
                xgb_config = self.model_configs['xgboost']
                xgb_model = xgb.XGBClassifier(**xgb_config['params'])
                xgb_model.fit(X_train, y_train)
                trained_models['xgboost'] = xgb_model
                
                results['xgboost'] = await self._evaluate_model(
                    xgb_model, X_train, y_train, X_val, y_val, X_test, y_test
                )
                
            except ImportError:
                self.logger.warning("XGBoost не установлен, пропускаем", category='ml')
            except Exception as e:
                self.logger.error(f"Ошибка обучения XGBoost: {e}", category='ml')
            
            # LightGBM (опционально)
            try:
                import lightgbm as lgb
                lgb_config = self.model_configs['lightgbm']
                lgb_model = lgb.LGBMClassifier(**lgb_config['params'])
                lgb_model.fit(X_train, y_train)
                trained_models['lightgbm'] = lgb_model
                
                results['lightgbm'] = await self._evaluate_model(
                    lgb_model, X_train, y_train, X_val, y_val, X_test, y_test
                )
                
            except ImportError:
                self.logger.warning("LightGBM не установлен, пропускаем", category='ml')
            except Exception as e:
                self.logger.error(f"Ошибка обучения LightGBM: {e}", category='ml')
            
            if not trained_models:
                return {'success': False, 'error': 'Не удалось обучить ни одной модели'}
            
            # === 4. СОЗДАНИЕ АНСАМБЛЯ ===
            # Веса основаны на валидационной точности
            weights = []
            for model_name in trained_models.keys():
                weights.append(results[model_name]['val_accuracy'])
            
            ensemble = EnsembleModel(
                models=trained_models,
                weights=weights,
                name=f"{symbol}_ensemble"
            )
            ensemble.feature_columns = df.columns.tolist()
            
            # Оценка ансамбля
            ensemble_results = await self._evaluate_model(
                ensemble, X_train, y_train, X_val, y_val, X_test, y_test
            )
            results['ensemble'] = ensemble_results
            
            # === 5. ВЫБОР ЛУЧШЕЙ МОДЕЛИ ===
            best_model_name = max(results.keys(), key=lambda k: results[k]['val_accuracy'])
            best_single_model = trained_models.get(best_model_name, list(trained_models.values())[0])
            
            # === 6. СОХРАНЕНИЕ МОДЕЛИ ===
            model_data = {
                'ensemble': ensemble,
                'best_single': best_single_model,
                'trained_models': trained_models,
                'feature_columns': df.columns.tolist(),
                'results': results,
                'training_config': self.training_config,
                'training_date': datetime.utcnow().isoformat(),
                'symbol': symbol,
                'timeframe': timeframe,
                'data_info': {
                    'train_size': len(X_train),
                    'val_size': len(X_val),
                    'test_size': len(X_test),
                    'feature_count': len(df.columns)
                }
            }
            
            model_path = self.models_dir / f"{symbol}_{timeframe}_model.pkl"
            with open(model_path, 'wb') as f:
                pickle.dump(model_data, f)
            
            # Сохраняем в память
            self.models[f"{symbol}_{timeframe}"] = ensemble
            
            # === 7. ГЕНЕРАЦИЯ ОТЧЕТОВ ===
            await self.generate_symbol_report(symbol, timeframe, results, model_data)
            
            self.logger.info(
                f"✅ Модель для {symbol} обучена и сохранена",
                category='ml',
                symbol=symbol,
                best_model=best_model_name,
                best_accuracy=f"{results[best_model_name]['val_accuracy']:.3f}",
                ensemble_accuracy=f"{results['ensemble']['val_accuracy']:.3f}"
            )
            
            return {
                'success': True,
                'symbol': symbol,
                'timeframe': timeframe,
                'best_model': best_model_name,
                'ensemble_accuracy': results['ensemble']['test_accuracy'],
                'models_trained': list(trained_models.keys()),
                'results': {k: {metric: v for metric, v in v.items() if metric not in ['model']} 
                           for k, v in results.items()},
                'model_path': str(model_path)
            }
            
        except Exception as e:
            self.logger.error(
                f"❌ Ошибка обучения модели для {symbol}: {e}",
                category='ml',
                symbol=symbol,
                error=str(e)
            )
            return {'success': False, 'error': str(e)}
    
    async def _evaluate_model(self, model, X_train, y_train, X_val, y_val, X_test, y_test):
        """Оценка модели на всех выборках"""
        try:
            # Предсказания
            train_pred = model.predict(X_train)
            val_pred = model.predict(X_val)
            test_pred = model.predict(X_test)
            
            # Метрики
            return {
                'train_accuracy': accuracy_score(y_train, train_pred),
                'val_accuracy': accuracy_score(y_val, val_pred),
                'test_accuracy': accuracy_score(y_test, test_pred),
                'test_precision': precision_score(y_test, test_pred, average='weighted', zero_division=0),
                'test_recall': recall_score(y_test, test_pred, average='weighted', zero_division=0),
                'test_f1': f1_score(y_test, test_pred, average='weighted', zero_division=0),
                'model': model
            }
        except Exception as e:
            self.logger.error(f"Ошибка оценки модели: {e}", category='ml')
            return {
                'train_accuracy': 0, 'val_accuracy': 0, 'test_accuracy': 0,
                'test_precision': 0, 'test_recall': 0, 'test_f1': 0,
                'model': model
            }
    
    async def train_all_models(self) -> Dict[str, Any]:
        """Обучает модели для всех символов"""
        self.logger.info("🚀 Начинаем массовое обучение моделей", category='ml')
        
        all_results = {}
        successful_models = 0
        
        for symbol in self.training_config['symbols']:
            try:
                result = await self.train_symbol_model(symbol)
                all_results[symbol] = result
                
                if result.get('success'):
                    successful_models += 1
                
                # Небольшая пауза между обучениями
                await asyncio.sleep(1)
                
            except Exception as e:
                self.logger.error(
                    f"Критическая ошибка обучения для {symbol}: {e}",
                    category='ml',
                    symbol=symbol
                )
                all_results[symbol] = {'success': False, 'error': str(e)}
        
        # Общая статистика
        total_symbols = len(self.training_config['symbols'])
        success_rate = successful_models / total_symbols if total_symbols > 0 else 0
        
        summary = {
            'timestamp': datetime.utcnow().isoformat(),
            'total_symbols': total_symbols,
            'successful_models': successful_models,
            'success_rate': success_rate,
            'results': all_results
        }
        
        # Сохраняем историю
        self.training_history.append(summary)
        
        # Генерируем отчет
        await self.generate_training_summary(summary)
        
        self.logger.info(
            f"✅ Массовое обучение завершено",
            category='ml',
            successful_models=successful_models,
            total_symbols=total_symbols,
            success_rate=f"{success_rate:.1%}"
        )
        
        return summary
    
    async def predict(self, symbol: str, current_data: Optional[pd.DataFrame] = None,
                     timeframe: str = '5m', use_ensemble: bool = True) -> Dict[str, Any]:
        """
        Получение предсказания от обученной модели
        """
        try:
            model_key = f"{symbol}_{timeframe}"
            
            # Попытка загрузки из памяти
            if model_key not in self.models:
                # Загрузка с диска
                model_path = self.models_dir / f"{symbol}_{timeframe}_model.pkl"
                if not model_path.exists():
                    return {
                        'success': False,
                        'error': f'Модель для {symbol} не найдена. Требуется обучение.'
                    }
                
                with open(model_path, 'rb') as f:
                    model_data = pickle.load(f)
                
                model_to_use = model_data['ensemble'] if use_ensemble else model_data['best_single']
                self.models[model_key] = model_to_use
                
                # Проверяем возраст модели
                training_date = datetime.fromisoformat(model_data['training_date'])
                model_age_hours = (datetime.utcnow() - training_date).total_seconds() / 3600
                
                if model_age_hours > self.training_config['retrain_interval_hours']:
                    self.logger.warning(
                        f"Модель для {symbol} устарела",
                        category='ml',
                        symbol=symbol,
                        age_hours=model_age_hours
                    )
            
            model = self.models[model_key]
            
            # Подготовка данных для предсказания
            if current_data is None:
                # Извлекаем свежие данные
                features_df = await self.feature_engineer.extract_features(
                    symbol=symbol,
                    timeframe=timeframe,
                    lookback_periods=100  # Меньше данных для предсказания
                )
                
                if features_df.empty:
                    return {'success': False, 'error': 'Нет данных для предсказания'}
                
                # Берем последнюю строку
                X = features_df.iloc[-1:].values
            else:
                X = current_data.values
            
            # Предсказание
            prediction = model.predict(X)[0]
            prediction_proba = model.predict_proba(X)[0]
            confidence = model.get_confidence(X)[0] if hasattr(model, 'get_confidence') else max(prediction_proba)
            
            # Интерпретация
            direction_map = {-1: 'SELL', 0: 'HOLD', 1: 'BUY'}
            direction = direction_map.get(prediction, 'HOLD')
            
            result = {
                'success': True,
                'symbol': symbol,
                'direction': direction,
                'confidence': float(confidence),
                'prediction_value': int(prediction),
                'probabilities': {
                    'bearish': float(prediction_proba[0]) if len(prediction_proba) > 0 else 0.0,
                    'neutral': float(prediction_proba[1]) if len(prediction_proba) > 1 else 0.0,
                    'bullish': float(prediction_proba[2]) if len(prediction_proba) > 2 else 0.0
                },
                'model_type': 'ensemble' if use_ensemble else 'single',
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # Логируем важные предсказания
            if confidence > 0.7:
                self.logger.info(
                    f"Сильный сигнал ML для {symbol}",
                    category='ml',
                    symbol=symbol,
                    direction=direction,
                    confidence=f"{confidence:.3f}"
                )
            
            return result
            
        except Exception as e:
            self.logger.error(
                f"❌ Ошибка предсказания для {symbol}: {e}",
                category='ml',
                symbol=symbol,
                error=str(e)
            )
            return {'success': False, 'error': str(e)}
    
    async def generate_symbol_report(self, symbol: str, timeframe: str, 
                                   results: Dict, model_data: Dict):
        """Генерирует отчет по обучению символа"""
        try:
            report = {
                'symbol': symbol,
                'timeframe': timeframe,
                'timestamp': datetime.utcnow().isoformat(),
                'training_info': model_data['data_info'],
                'model_performance': {
                    name: {k: v for k, v in metrics.items() if k != 'model'}
                    for name, metrics in results.items()
                },
                'best_model': max(results.keys(), key=lambda k: results[k]['val_accuracy']),
                'ensemble_vs_best': {
                    'ensemble_accuracy': results['ensemble']['test_accuracy'],
                    'best_single_accuracy': max(
                        results[k]['test_accuracy'] for k in results.keys() if k != 'ensemble'
                    ),
                    'improvement': results['ensemble']['test_accuracy'] - max(
                        results[k]['test_accuracy'] for k in results.keys() if k != 'ensemble'
                    )
                }
            }
            
            # Сохраняем отчет
            report_path = self.reports_dir / f"{symbol}_{timeframe}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(report_path, 'w') as f:
                json.dump(report, f, indent=2)
            
        except Exception as e:
            self.logger.error(f"Ошибка генерации отчета для {symbol}: {e}", category='ml')
    
    async def generate_training_summary(self, summary: Dict):
        """Генерирует общий отчет по массовому обучению"""
        try:
            # Анализируем результаты
            successful_results = {k: v for k, v in summary['results'].items() if v.get('success')}
            
            if successful_results:
                accuracies = [r.get('ensemble_accuracy', 0) for r in successful_results.values()]
                performance_summary = {
                    'mean_accuracy': np.mean(accuracies),
                    'median_accuracy': np.median(accuracies),
                    'best_accuracy': max(accuracies),
                    'worst_accuracy': min(accuracies),
                    'std_accuracy': np.std(accuracies)
                }
            else:
                performance_summary = {'error': 'Нет успешных результатов'}
            
            # Полный отчет
            full_summary = {
                **summary,
                'performance_summary': performance_summary,
                'failed_symbols': [k for k, v in summary['results'].items() if not v.get('success')],
                'training_config': self.training_config
            }
            
            # Сохраняем
            summary_path = self.reports_dir / f"training_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(summary_path, 'w') as f:
                json.dump(full_summary, f, indent=2)
            
        except Exception as e:
            self.logger.error(f"Ошибка генерации общего отчета: {e}", category='ml')
    
    async def auto_retrain_loop(self):
        """Автоматический цикл переобучения"""
        self.logger.info("🔄 Запуск автоматического цикла переобучения", category='ml')
        
        while True:
            try:
                self.logger.info("Начинаем плановое переобучение", category='ml')
                
                # Обучаем все модели
                results = await self.train_all_models()
                
                # Краткий анализ результатов
                success_rate = results['success_rate']
                if success_rate < 0.5:
                    self.logger.warning(
                        f"Низкий процент успешного обучения: {success_rate:.1%}",
                        category='ml'
                    )
                
                # Ждем до следующего переобучения
                interval_hours = self.training_config['retrain_interval_hours']
                self.logger.info(
                    f"Переобучение завершено. Следующее через {interval_hours}ч",
                    category='ml',
                    success_rate=f"{success_rate:.1%}"
                )
                
                await asyncio.sleep(interval_hours * 3600)
                
            except Exception as e:
                self.logger.error(
                    f"Ошибка в цикле переобучения: {e}",
                    category='ml',
                    error=str(e)
                )
                # При ошибке ждем час и пробуем снова
                await asyncio.sleep(3600)
    
    def get_model_info(self, symbol: str, timeframe: str = '5m') -> Dict[str, Any]:
        """Получение информации о модели"""
        try:
            model_path = self.models_dir / f"{symbol}_{timeframe}_model.pkl"
            if not model_path.exists():
                return {'exists': False}
            
            with open(model_path, 'rb') as f:
                model_data = pickle.load(f)
            
            training_date = datetime.fromisoformat(model_data['training_date'])
            age_hours = (datetime.utcnow() - training_date).total_seconds() / 3600
            
            return {
                'exists': True,
                'symbol': symbol,
                'timeframe': timeframe,
                'training_date': model_data['training_date'],
                'age_hours': age_hours,
                'models_included': list(model_data['trained_models'].keys()),
                'performance': model_data['results']['ensemble']['test_accuracy'],
                'data_size': model_data['data_info']['train_size'],
                'feature_count': model_data['data_info']['feature_count']
            }
            
        except Exception as e:
            return {'exists': False, 'error': str(e)}
    
    def list_available_models(self) -> List[Dict[str, Any]]:
        """Список всех доступных моделей"""
        models = []
        for model_file in self.models_dir.glob("*.pkl"):
            try:
                # Парсим имя файла
                parts = model_file.stem.split('_')
                if len(parts) >= 3:
                    symbol = '_'.join(parts[:-2])
                    timeframe = parts[-2]
                    
                    model_info = self.get_model_info(symbol, timeframe)
                    if model_info.get('exists'):
                        models.append(model_info)
            except:
                continue
        
        return sorted(models, key=lambda x: x.get('age_hours', float('inf')))


# Глобальный экземпляр тренера
ml_trainer = MLTrainer()

# Экспорт
__all__ = ['MLTrainer', 'EnsembleModel', 'ml_trainer']