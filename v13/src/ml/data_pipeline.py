"""
Data Pipeline для подготовки данных для ML моделей
Файл: src/ml/data_pipeline.py
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Any, Union
from datetime import datetime, timedelta
import asyncio
from collections import defaultdict
import json

from sqlalchemy import and_, or_, func
from sqlalchemy.orm import Session

from ..core.database import SessionLocal
from ..core.models import Trade, Signal, MarketData
from ..logging.smart_logger import SmartLogger
from .features.feature_engineering import FeatureEngineering


class DataPipeline:
    """
    Централизованный pipeline для подготовки данных
    """
    
    def __init__(self, symbols: List[str], timeframes: List[str] = ['5m', '15m', '1h', '4h']):
        self.symbols = symbols
        self.timeframes = timeframes
        self.feature_engineering = FeatureEngineering()
        self.logger = SmartLogger(__name__)
        
        # Кеширование данных
        self.cache = {
            'market_data': {},
            'features': {},
            'labels': {},
            'last_update': {}
        }
        
        # Параметры pipeline
        self.params = {
            'min_history_candles': 500,
            'feature_window': 100,
            'label_window': 20,
            'validation_split': 0.2,
            'test_split': 0.1,
            'outlier_threshold': 3.0,  # стандартных отклонений
            'missing_data_threshold': 0.1  # максимум 10% пропущенных данных
        }
        
    async def fetch_market_data(self, symbol: str, timeframe: str, 
                               start_date: Optional[datetime] = None,
                               end_date: Optional[datetime] = None) -> pd.DataFrame:
        """
        Загружает рыночные данные из БД
        
        Args:
            symbol: Торговая пара
            timeframe: Таймфрейм
            start_date: Начальная дата
            end_date: Конечная дата
            
        Returns:
            DataFrame с рыночными данными
        """
        cache_key = f"{symbol}_{timeframe}"
        
        # Проверяем кеш
        if cache_key in self.cache['market_data']:
            last_update = self.cache['last_update'].get(cache_key, datetime.min)
            if (datetime.now() - last_update).seconds < 300:  # 5 минут
                return self.cache['market_data'][cache_key]
        
        db = SessionLocal()
        try:
            query = db.query(MarketData).filter(
                and_(
                    MarketData.symbol == symbol,
                    MarketData.timeframe == timeframe
                )
            )
            
            if start_date:
                query = query.filter(MarketData.timestamp >= start_date)
            if end_date:
                query = query.filter(MarketData.timestamp <= end_date)
            
            query = query.order_by(MarketData.timestamp.asc())
            
            data = query.all()
            
            if not data:
                self.logger.warning(
                    f"Нет данных для {symbol} {timeframe}",
                    category='data',
                    symbol=symbol,
                    timeframe=timeframe
                )
                return pd.DataFrame()
            
            # Преобразуем в DataFrame
            df = pd.DataFrame([{
                'timestamp': d.timestamp,
                'open': d.open,
                'high': d.high,
                'low': d.low,
                'close': d.close,
                'volume': d.volume
            } for d in data])
            
            df.set_index('timestamp', inplace=True)
            
            # Кешируем
            self.cache['market_data'][cache_key] = df
            self.cache['last_update'][cache_key] = datetime.now()
            
            self.logger.info(
                f"Загружено {len(df)} свечей для {symbol} {timeframe}",
                category='data',
                symbol=symbol,
                timeframe=timeframe,
                candles=len(df)
            )
            
            return df
            
        except Exception as e:
            self.logger.error(
                f"Ошибка загрузки данных: {str(e)}",
                category='data',
                error=str(e)
            )
            return pd.DataFrame()
        finally:
            db.close()
    
    def clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Очистка и валидация данных
        
        Args:
            df: Исходные данные
            
        Returns:
            Очищенные данные
        """
        if df.empty:
            return df
        
        original_len = len(df)
        
        # 1. Удаляем дубликаты
        df = df[~df.index.duplicated(keep='first')]
        
        # 2. Проверяем на пропущенные значения
        missing_ratio = df.isnull().sum() / len(df)
        if missing_ratio.max() > self.params['missing_data_threshold']:
            self.logger.warning(
                f"Много пропущенных данных: {missing_ratio.max():.2%}",
                category='data',
                columns=missing_ratio[missing_ratio > 0.1].to_dict()
            )
        
        # 3. Заполняем пропуски
        df['volume'].fillna(0, inplace=True)
        df[['open', 'high', 'low', 'close']] = df[['open', 'high', 'low', 'close']].fillna(method='ffill')
        
        # 4. Удаляем строки с оставшимися пропусками
        df.dropna(inplace=True)
        
        # 5. Проверяем логическую целостность OHLC
        invalid_ohlc = (
            (df['high'] < df['low']) |
            (df['high'] < df['open']) |
            (df['high'] < df['close']) |
            (df['low'] > df['open']) |
            (df['low'] > df['close'])
        )
        
        if invalid_ohlc.any():
            self.logger.warning(
                f"Найдено {invalid_ohlc.sum()} некорректных OHLC свечей",
                category='data'
            )
            df = df[~invalid_ohlc]
        
        # 6. Удаляем выбросы
        df = self._remove_outliers(df)
        
        # 7. Проверяем временные интервалы
        df = self._check_time_consistency(df)
        
        cleaned_len = len(df)
        self.logger.info(
            f"Очистка данных: {original_len} -> {cleaned_len} "
            f"(удалено {original_len - cleaned_len})",
            category='data',
            original=original_len,
            cleaned=cleaned_len
        )
        
        return df
    
    def _remove_outliers(self, df: pd.DataFrame) -> pd.DataFrame:
        """Удаляет выбросы из данных"""
        # Z-score метод для цен
        price_cols = ['open', 'high', 'low', 'close']
        
        for col in price_cols:
            z_scores = np.abs((df[col] - df[col].mean()) / df[col].std())
            df = df[z_scores < self.params['outlier_threshold']]
        
        # IQR метод для объема
        Q1 = df['volume'].quantile(0.25)
        Q3 = df['volume'].quantile(0.75)
        IQR = Q3 - Q1
        volume_filter = (df['volume'] >= Q1 - 1.5 * IQR) & (df['volume'] <= Q3 + 1.5 * IQR)
        df = df[volume_filter]
        
        return df
    
    def _check_time_consistency(self, df: pd.DataFrame) -> pd.DataFrame:
        """Проверяет консистентность временных интервалов"""
        if len(df) < 2:
            return df
        
        # Вычисляем интервалы между свечами
        time_diffs = df.index.to_series().diff()
        
        # Находим медианный интервал
        median_interval = time_diffs.median()
        
        # Проверяем на большие пропуски
        large_gaps = time_diffs > median_interval * 2
        
        if large_gaps.any():
            gap_count = large_gaps.sum()
            self.logger.warning(
                f"Обнаружено {gap_count} больших временных пропусков",
                category='data',
                max_gap=time_diffs.max()
            )
        
        return df
    
    async def prepare_features(self, symbol: str, timeframe: str) -> pd.DataFrame:
        """
        Подготавливает признаки для ML моделей
        
        Args:
            symbol: Торговая пара
            timeframe: Таймфрейм
            
        Returns:
            DataFrame с признаками
        """
        # Загружаем рыночные данные
        market_data = await self.fetch_market_data(symbol, timeframe)
        
        if market_data.empty:
            return pd.DataFrame()
        
        # Очищаем данные
        market_data = self.clean_data(market_data)
        
        # Проверяем достаточность данных
        if len(market_data) < self.params['min_history_candles']:
            self.logger.warning(
                f"Недостаточно данных для {symbol} {timeframe}: "
                f"{len(market_data)} < {self.params['min_history_candles']}",
                category='data'
            )
            return pd.DataFrame()
        
        # Извлекаем признаки
        features = self.feature_engineering.extract_features(market_data)
        
        # Кешируем
        cache_key = f"{symbol}_{timeframe}"
        self.cache['features'][cache_key] = features
        
        return features
    
    def create_labels(self, market_data: pd.DataFrame, 
                     label_type: str = 'classification') -> pd.Series:
        """
        Создает метки для обучения
        
        Args:
            market_data: Рыночные данные
            label_type: Тип меток ('classification', 'regression')
            
        Returns:
            Series с метками
        """
        if label_type == 'classification':
            # Метки для классификации направления
            labels = []
            
            for i in range(len(market_data) - self.params['label_window']):
                current_price = market_data.iloc[i]['close']
                future_prices = market_data.iloc[i+1:i+self.params['label_window']+1]['close']
                
                # Среднее изменение цены
                avg_change = (future_prices.mean() - current_price) / current_price
                
                # Классификация: 0 - down, 1 - neutral, 2 - up
                if avg_change < -0.002:  # < -0.2%
                    labels.append(0)
                elif avg_change > 0.002:  # > 0.2%
                    labels.append(2)
                else:
                    labels.append(1)
            
            # Дополняем последние значения
            for _ in range(self.params['label_window']):
                labels.append(1)  # neutral
                
        elif label_type == 'regression':
            # Метки для регрессии (процентное изменение)
            labels = []
            
            for i in range(len(market_data) - self.params['label_window']):
                current_price = market_data.iloc[i]['close']
                future_price = market_data.iloc[i + self.params['label_window']]['close']
                
                pct_change = (future_price - current_price) / current_price * 100
                labels.append(pct_change)
            
            # Дополняем последние значения
            for _ in range(self.params['label_window']):
                labels.append(0.0)
        
        return pd.Series(labels, index=market_data.index)
    
    async def prepare_training_data(self, symbols: Optional[List[str]] = None,
                                   timeframes: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Подготавливает полный набор данных для обучения
        
        Args:
            symbols: Список символов (если None, используются все)
            timeframes: Список таймфреймов
            
        Returns:
            Словарь с подготовленными данными
        """
        if symbols is None:
            symbols = self.symbols
        if timeframes is None:
            timeframes = self.timeframes
        
        all_data = {
            'features': {},
            'labels': {},
            'market_data': {},
            'metadata': {}
        }
        
        for symbol in symbols:
            all_data['features'][symbol] = {}
            all_data['labels'][symbol] = {}
            all_data['market_data'][symbol] = {}
            
            for timeframe in timeframes:
                self.logger.info(
                    f"Подготовка данных для {symbol} {timeframe}",
                    category='data'
                )
                
                # Загружаем и подготавливаем признаки
                features = await self.prepare_features(symbol, timeframe)
                
                if features.empty:
                    continue
                
                # Загружаем рыночные данные
                market_data = self.cache['market_data'].get(f"{symbol}_{timeframe}")
                
                # Создаем метки
                classification_labels = self.create_labels(market_data, 'classification')
                regression_labels = self.create_labels(market_data, 'regression')
                
                # Выравниваем размеры
                min_len = min(len(features), len(classification_labels))
                features = features.iloc[:min_len]
                classification_labels = classification_labels.iloc[:min_len]
                regression_labels = regression_labels.iloc[:min_len]
                market_data = market_data.iloc[:min_len]
                
                # Разделяем на train/val/test
                train_size = int(len(features) * (1 - self.params['validation_split'] - 
                                                  self.params['test_split']))
                val_size = int(len(features) * self.params['validation_split'])
                
                all_data['features'][symbol][timeframe] = {
                    'train': features.iloc[:train_size],
                    'val': features.iloc[train_size:train_size+val_size],
                    'test': features.iloc[train_size+val_size:]
                }
                
                all_data['labels'][symbol][timeframe] = {
                    'classification': {
                        'train': classification_labels.iloc[:train_size],
                        'val': classification_labels.iloc[train_size:train_size+val_size],
                        'test': classification_labels.iloc[train_size+val_size:]
                    },
                    'regression': {
                        'train': regression_labels.iloc[:train_size],
                        'val': regression_labels.iloc[train_size:train_size+val_size],
                        'test': regression_labels.iloc[train_size+val_size:]
                    }
                }
                
                all_data['market_data'][symbol][timeframe] = market_data
        
        # Добавляем метаданные
        all_data['metadata'] = {
            'prepared_at': datetime.now().isoformat(),
            'symbols': symbols,
            'timeframes': timeframes,
            'total_samples': sum(
                len(all_data['features'][s][tf]['train']) 
                for s in symbols 
                for tf in timeframes 
                if s in all_data['features'] and tf in all_data['features'][s]
            ),
            'feature_names': list(features.columns) if not features.empty else [],
            'params': self.params
        }
        
        self.logger.info(
            f"Подготовка данных завершена",
            category='data',
            metadata=all_data['metadata']
        )
        
        return all_data
    
    async def prepare_realtime_features(self, symbol: str, 
                                      timeframe: str) -> pd.DataFrame:
        """
        Подготавливает признаки для real-time предсказаний
        
        Args:
            symbol: Торговая пара
            timeframe: Таймфрейм
            
        Returns:
            DataFrame с последними признаками
        """
        # Загружаем последние данные
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)  # Достаточно для расчета индикаторов
        
        market_data = await self.fetch_market_data(
            symbol, timeframe, start_date, end_date
        )
        
        if market_data.empty or len(market_data) < self.params['feature_window']:
            self.logger.error(
                f"Недостаточно данных для real-time features: {symbol} {timeframe}",
                category='data'
            )
            return pd.DataFrame()
        
        # Очищаем данные
        market_data = self.clean_data(market_data)
        
        # Извлекаем признаки
        features = self.feature_engineering.extract_features(market_data)
        
        # Возвращаем последнюю строку
        return features.iloc[[-1]]
    
    def augment_data(self, features: pd.DataFrame, labels: pd.Series,
                    augmentation_factor: int = 2) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Аугментация данных для улучшения обучения
        
        Args:
            features: Исходные признаки
            labels: Исходные метки
            augmentation_factor: Во сколько раз увеличить данные
            
        Returns:
            Аугментированные признаки и метки
        """
        augmented_features = [features]
        augmented_labels = [labels]
        
        for i in range(augmentation_factor - 1):
            # Добавляем шум к признакам
            noise_level = 0.01 * (i + 1)  # Увеличиваем шум с каждой итерацией
            noisy_features = features + np.random.normal(
                0, noise_level, features.shape
            ) * features.std()
            
            augmented_features.append(noisy_features)
            augmented_labels.append(labels)
        
        # Объединяем
        final_features = pd.concat(augmented_features, ignore_index=True)
        final_labels = pd.concat(augmented_labels, ignore_index=True)
        
        # Перемешиваем
        shuffle_idx = np.random.permutation(len(final_features))
        final_features = final_features.iloc[shuffle_idx]
        final_labels = final_labels.iloc[shuffle_idx]
        
        self.logger.info(
            f"Аугментация данных: {len(features)} -> {len(final_features)}",
            category='data',
            original_size=len(features),
            augmented_size=len(final_features)
        )
        
        return final_features, final_labels
    
    def create_time_series_sequences(self, features: pd.DataFrame, 
                                   labels: pd.Series,
                                   sequence_length: int = 20) -> Tuple[np.ndarray, np.ndarray]:
        """
        Создает последовательности для RNN/LSTM моделей
        
        Args:
            features: Признаки
            labels: Метки
            sequence_length: Длина последовательности
            
        Returns:
            3D массив последовательностей и соответствующие метки
        """
        sequences = []
        sequence_labels = []
        
        for i in range(len(features) - sequence_length):
            seq = features.iloc[i:i+sequence_length].values
            label = labels.iloc[i+sequence_length]
            
            sequences.append(seq)
            sequence_labels.append(label)
        
        X = np.array(sequences)
        y = np.array(sequence_labels)
        
        self.logger.info(
            f"Создано последовательностей: {X.shape}",
            category='data',
            shape=X.shape
        )
        
        return X, y
    
    async def get_trade_statistics(self, symbol: str, 
                                  days_back: int = 30) -> Dict[str, Any]:
        """
        Получает статистику по сделкам для обогащения данных
        
        Args:
            symbol: Торговая пара
            days_back: Количество дней для анализа
            
        Returns:
            Статистика по сделкам
        """
        db = SessionLocal()
        try:
            start_date = datetime.now() - timedelta(days=days_back)
            
            # Получаем сделки
            trades = db.query(Trade).filter(
                and_(
                    Trade.symbol == symbol,
                    Trade.created_at >= start_date
                )
            ).all()
            
            if not trades:
                return {}
            
            # Рассчитываем статистику
            profits = [t.profit for t in trades if t.status == 'CLOSED']
            win_trades = [p for p in profits if p > 0]
            loss_trades = [p for p in profits if p < 0]
            
            stats = {
                'total_trades': len(trades),
                'closed_trades': len(profits),
                'win_rate': len(win_trades) / len(profits) if profits else 0,
                'avg_profit': np.mean(profits) if profits else 0,
                'avg_win': np.mean(win_trades) if win_trades else 0,
                'avg_loss': np.mean(loss_trades) if loss_trades else 0,
                'profit_factor': abs(sum(win_trades) / sum(loss_trades)) if loss_trades else 0,
                'max_drawdown': min(profits) if profits else 0,
                'total_profit': sum(profits),
                'strategies_used': list(set(t.strategy for t in trades))
            }
            
            return stats
            
        except Exception as e:
            self.logger.error(
                f"Ошибка получения статистики: {str(e)}",
                category='data'
            )
            return {}
        finally:
            db.close()
    
    def validate_data_quality(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Валидирует качество подготовленных данных
        
        Args:
            data: Подготовленные данные
            
        Returns:
            Отчет о качестве данных
        """
        report = {
            'total_symbols': len(data['features']),
            'total_timeframes': len(data['features'].get(list(data['features'].keys())[0], {})),
            'issues': [],
            'warnings': [],
            'data_quality_score': 100.0
        }
        
        for symbol in data['features']:
            for timeframe in data['features'][symbol]:
                # Проверяем размеры
                train_features = data['features'][symbol][timeframe]['train']
                train_labels = data['labels'][symbol][timeframe]['classification']['train']
                
                if len(train_features) != len(train_labels):
                    report['issues'].append(
                        f"{symbol} {timeframe}: Несоответствие размеров features/labels"
                    )
                    report['data_quality_score'] -= 10
                
                # Проверяем на NaN
                if train_features.isnull().any().any():
                    nan_cols = train_features.columns[train_features.isnull().any()].tolist()
                    report['warnings'].append(
                        f"{symbol} {timeframe}: NaN в колонках {nan_cols}"
                    )
                    report['data_quality_score'] -= 5
                
                # Проверяем дисбаланс классов
                if 'classification' in data['labels'][symbol][timeframe]:
                    class_counts = train_labels.value_counts()
                    min_class = class_counts.min()
                    max_class = class_counts.max()
                    
                    if max_class / min_class > 10:
                        report['warnings'].append(
                            f"{symbol} {timeframe}: Сильный дисбаланс классов {class_counts.to_dict()}"
                        )
                        report['data_quality_score'] -= 3
        
        report['data_quality_score'] = max(0, report['data_quality_score'])
        
        return report
    
    def save_prepared_data(self, data: Dict[str, Any], path: str):
        """Сохраняет подготовленные данные"""
        # Преобразуем DataFrame в словари для сериализации
        serializable_data = {
            'features': {},
            'labels': {},
            'metadata': data['metadata']
        }
        
        for symbol in data['features']:
            serializable_data['features'][symbol] = {}
            serializable_data['labels'][symbol] = {}
            
            for timeframe in data['features'][symbol]:
                serializable_data['features'][symbol][timeframe] = {
                    split: df.to_dict() 
                    for split, df in data['features'][symbol][timeframe].items()
                }
                
                serializable_data['labels'][symbol][timeframe] = {
                    label_type: {
                        split: labels.tolist()
                        for split, labels in label_data.items()
                    }
                    for label_type, label_data in data['labels'][symbol][timeframe].items()
                }
        
        # Сохраняем
        import joblib
        joblib.dump(serializable_data, path)
        
        self.logger.info(
            f"Данные сохранены: {path}",
            category='data',
            size_mb=os.path.getsize(path) / 1024 / 1024
        )
    
    def load_prepared_data(self, path: str) -> Dict[str, Any]:
        """Загружает подготовленные данные"""
        import joblib
        data = joblib.load(path)
        
        # Преобразуем обратно в DataFrame
        restored_data = {
            'features': {},
            'labels': {},
            'metadata': data['metadata']
        }
        
        for symbol in data['features']:
            restored_data['features'][symbol] = {}
            restored_data['labels'][symbol] = {}
            
            for timeframe in data['features'][symbol]:
                restored_data['features'][symbol][timeframe] = {
                    split: pd.DataFrame(df_dict)
                    for split, df_dict in data['features'][symbol][timeframe].items()
                }
                
                restored_data['labels'][symbol][timeframe] = {
                    label_type: {
                        split: pd.Series(labels_list)
                        for split, labels_list in label_data.items()
                    }
                    for label_type, label_data in data['labels'][symbol][timeframe].items()
                }
        
        self.logger.info(
            f"Данные загружены: {path}",
            category='data'
        )
        
        return restored_data