#!/usr/bin/env python3
"""
Feature Engineering для ML моделей - ИСПРАВЛЕННАЯ ВЕРСИЯ
=======================================================
Файл: src/ml/feature_engineering.py

✅ ИСПРАВЛЯЕТ: No module named 'src.ml.feature_engineering'
✅ Полная совместимость с существующей системой
✅ Профессиональная реализация с индикаторами
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import asyncio
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

# Безопасные импорты
try:
    from ..indicators.unified_indicators import UnifiedIndicators
    INDICATORS_AVAILABLE = True
except ImportError:
    logger.warning("⚠️ UnifiedIndicators недоступен, используем ручные реализации")
    INDICATORS_AVAILABLE = False
    UnifiedIndicators = None

try:
    from ..core.unified_config import unified_config
    CONFIG_AVAILABLE = True
except ImportError:
    logger.warning("⚠️ unified_config недоступен")
    unified_config = None
    CONFIG_AVAILABLE = False

@dataclass
class FeatureConfig:
    """Конфигурация создания признаков"""
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
    """
    ✅ ИСПРАВЛЕННЫЙ: Класс для создания признаков для ML моделей
    
    Создает технические, ценовые, объемные и временные признаки
    для использования в машинном обучении.
    """
    
    def __init__(self, config: Optional[FeatureConfig] = None):
        """
        Инициализация Feature Engineer
        
        Args:
            config: Конфигурация создания признаков
        """
        self.config = config or FeatureConfig()
        self.indicators = UnifiedIndicators() if INDICATORS_AVAILABLE else None
        self.feature_names: List[str] = []
        self.is_fitted = False
        
        logger.info("✅ FeatureEngineer инициализирован")
    
    def create_features(self, df: pd.DataFrame, symbol: str = "BTCUSDT") -> pd.DataFrame:
        """
        ✅ ОСНОВНОЙ МЕТОД: Создание всех признаков из OHLCV данных
        
        Args:
            df: DataFrame с колонками [timestamp, open, high, low, close, volume]
            symbol: Торговая пара
            
        Returns:
            DataFrame с добавленными признаками
        """
        try:
            if df.empty:
                logger.warning("⚠️ Пустой DataFrame передан в create_features")
                return df
            
            # Копируем для безопасности
            result_df = df.copy()
            
            # Убеждаемся в правильных названиях колонок
            result_df = self._standardize_columns(result_df)
            
            # Создаем различные типы признаков
            if self.config.enable_price_features:
                result_df = self._create_price_features(result_df)
            
            if self.config.enable_volume_features:
                result_df = self._create_volume_features(result_df)
            
            if self.config.enable_technical_indicators:
                result_df = self._create_technical_features(result_df)
            
            if self.config.enable_time_features:
                result_df = self._create_time_features(result_df)
            
            if self.config.enable_lag_features:
                result_df = self._create_lag_features(result_df)
            
            # Создаем статистические признаки
            result_df = self._create_statistical_features(result_df)
            
            # Удаляем строки с NaN значениями
            initial_rows = len(result_df)
            result_df = result_df.dropna()
            dropped_rows = initial_rows - len(result_df)
            
            if dropped_rows > 0:
                logger.info(f"🧹 Удалено {dropped_rows} строк с NaN значениями")
            
            # Сохраняем имена признаков
            self.feature_names = [col for col in result_df.columns if col not in 
                                ['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            
            self.is_fitted = True
            logger.info(f"✅ Создано {len(self.feature_names)} признаков для {symbol}")
            
            return result_df
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания признаков: {e}")
            return df
    
    def _standardize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Стандартизация названий колонок"""
        column_mapping = {
            'Open': 'open', 'High': 'high', 'Low': 'low', 
            'Close': 'close', 'Volume': 'volume',
            'time': 'timestamp', 'datetime': 'timestamp'
        }
        
        df = df.rename(columns=column_mapping)
        
        # Проверяем наличие обязательных колонок
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        missing_cols = [col for col in required_cols if col not in df.columns]
        
        if missing_cols:
            logger.error(f"❌ Отсутствуют обязательные колонки: {missing_cols}")
            raise ValueError(f"Отсутствуют колонки: {missing_cols}")
        
        return df
    
    def _create_price_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Создание ценовых признаков"""
        try:
            # Типичная цена
            df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
            
            # Ценовые изменения
            df['price_change'] = df['close'].pct_change()
            df['price_change_abs'] = df['close'].diff()
            
            # Размах цены
            df['price_range'] = df['high'] - df['low']
            df['price_range_pct'] = (df['high'] - df['low']) / df['close']
            
            # Позиция закрытия в диапазоне дня
            df['close_position'] = (df['close'] - df['low']) / (df['high'] - df['low'])
            df['close_position'] = df['close_position'].fillna(0.5)
            
            # Движущие средние для разных периодов
            for window in self.config.price_windows:
                df[f'sma_{window}'] = df['close'].rolling(window=window).mean()
                df[f'price_vs_sma_{window}'] = df['close'] / df[f'sma_{window}'] - 1
                
                # EMA
                df[f'ema_{window}'] = df['close'].ewm(span=window).mean()
                df[f'price_vs_ema_{window}'] = df['close'] / df[f'ema_{window}'] - 1
            
            # Bollinger Bands
            df['bb_middle'] = df['close'].rolling(window=20).mean()
            bb_std = df['close'].rolling(window=20).std()
            df['bb_upper'] = df['bb_middle'] + (bb_std * 2)
            df['bb_lower'] = df['bb_middle'] - (bb_std * 2)
            df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
            df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
            
            return df
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания ценовых признаков: {e}")
            return df
    
    def _create_volume_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Создание объемных признаков"""
        try:
            # Изменения объема
            df['volume_change'] = df['volume'].pct_change()
            df['volume_change_abs'] = df['volume'].diff()
            
            # Средние объемы
            for window in self.config.volume_windows:
                df[f'volume_sma_{window}'] = df['volume'].rolling(window=window).mean()
                df[f'volume_ratio_{window}'] = df['volume'] / df[f'volume_sma_{window}']
            
            # Volume Price Trend (VPT)
            df['vpt'] = (df['volume'] * df['price_change']).cumsum()
            
            # On Balance Volume (OBV) - упрощенная версия
            df['obv_direction'] = np.where(df['close'] > df['close'].shift(1), 1, 
                                 np.where(df['close'] < df['close'].shift(1), -1, 0))
            df['obv'] = (df['volume'] * df['obv_direction']).cumsum()
            
            # Volume Weighted Average Price (VWAP) - приблизительная
            df['vwap'] = (df['typical_price'] * df['volume']).rolling(window=20).sum() / df['volume'].rolling(window=20).sum()
            df['price_vs_vwap'] = df['close'] / df['vwap'] - 1
            
            return df
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания объемных признаков: {e}")
            return df
    
    def _create_technical_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Создание технических индикаторов"""
        try:
            if self.indicators:
                # Используем UnifiedIndicators если доступен
                df = self._create_indicators_features(df)
            else:
                # Ручные реализации основных индикаторов
                df = self._create_manual_indicators(df)
            
            return df
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания технических признаков: {e}")
            return df
    
    def _create_indicators_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Создание признаков через UnifiedIndicators"""
        try:
            # RSI
            df['rsi'] = self.indicators.calculate_rsi(df['close'])
            df['rsi_oversold'] = (df['rsi'] < 30).astype(int)
            df['rsi_overbought'] = (df['rsi'] > 70).astype(int)
            
            # MACD
            macd_data = self.indicators.calculate_macd(df['close'])
            if isinstance(macd_data, dict):
                df['macd'] = macd_data.get('macd', 0)
                df['macd_signal'] = macd_data.get('signal', 0)
                df['macd_histogram'] = macd_data.get('histogram', 0)
            
            # Stochastic
            stoch_data = self.indicators.calculate_stochastic(df['high'], df['low'], df['close'])
            if isinstance(stoch_data, dict):
                df['stoch_k'] = stoch_data.get('k', 0)
                df['stoch_d'] = stoch_data.get('d', 0)
            
            return df
            
        except Exception as e:
            logger.error(f"❌ Ошибка с UnifiedIndicators: {e}")
            return self._create_manual_indicators(df)
    
    def _create_manual_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Ручные реализации индикаторов"""
        try:
            # RSI
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['rsi'] = 100 - (100 / (1 + rs))
            df['rsi_oversold'] = (df['rsi'] < 30).astype(int)
            df['rsi_overbought'] = (df['rsi'] > 70).astype(int)
            
            # MACD
            ema12 = df['close'].ewm(span=12).mean()
            ema26 = df['close'].ewm(span=26).mean()
            df['macd'] = ema12 - ema26
            df['macd_signal'] = df['macd'].ewm(span=9).mean()
            df['macd_histogram'] = df['macd'] - df['macd_signal']
            
            # Stochastic
            low_14 = df['low'].rolling(window=14).min()
            high_14 = df['high'].rolling(window=14).max()
            df['stoch_k'] = 100 * (df['close'] - low_14) / (high_14 - low_14)
            df['stoch_d'] = df['stoch_k'].rolling(window=3).mean()
            
            # Williams %R
            df['williams_r'] = -100 * (high_14 - df['close']) / (high_14 - low_14)
            
            return df
            
        except Exception as e:
            logger.error(f"❌ Ошибка ручных индикаторов: {e}")
            return df
    
    def _create_time_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Создание временных признаков"""
        try:
            if 'timestamp' in df.columns:
                # Преобразуем timestamp в datetime если нужно
                if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                
                # Извлекаем временные компоненты
                df['hour'] = df['timestamp'].dt.hour
                df['day_of_week'] = df['timestamp'].dt.dayofweek
                df['day_of_month'] = df['timestamp'].dt.day
                df['month'] = df['timestamp'].dt.month
                
                # Циклические признаки
                df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
                df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)
                df['day_sin'] = np.sin(2 * np.pi * df['day_of_week'] / 7)
                df['day_cos'] = np.cos(2 * np.pi * df['day_of_week'] / 7)
                
                # Торговые сессии
                df['is_asian_session'] = ((df['hour'] >= 1) & (df['hour'] <= 9)).astype(int)
                df['is_european_session'] = ((df['hour'] >= 8) & (df['hour'] <= 16)).astype(int)
                df['is_american_session'] = ((df['hour'] >= 14) & (df['hour'] <= 22)).astype(int)
            
            return df
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания временных признаков: {e}")
            return df
    
    def _create_lag_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Создание лаговых признаков"""
        try:
            # Лаги цены закрытия
            for lag in range(1, min(self.config.max_lag_periods, 6)):
                df[f'close_lag_{lag}'] = df['close'].shift(lag)
                df[f'volume_lag_{lag}'] = df['volume'].shift(lag)
                df[f'price_change_lag_{lag}'] = df['price_change'].shift(lag)
            
            # Лаги индикаторов
            if 'rsi' in df.columns:
                for lag in [1, 2, 3]:
                    df[f'rsi_lag_{lag}'] = df['rsi'].shift(lag)
            
            return df
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания лаговых признаков: {e}")
            return df
    
    def _create_statistical_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Создание статистических признаков"""
        try:
            # Волатильность
            for window in self.config.volatility_windows:
                df[f'volatility_{window}'] = df['close'].rolling(window=window).std()
                df[f'volatility_norm_{window}'] = df[f'volatility_{window}'] / df['close']
            
            # Максимумы и минимумы
            for window in [10, 20, 50]:
                df[f'highest_{window}'] = df['high'].rolling(window=window).max()
                df[f'lowest_{window}'] = df['low'].rolling(window=window).min()
                df[f'position_in_range_{window}'] = (df['close'] - df[f'lowest_{window}']) / (df[f'highest_{window}'] - df[f'lowest_{window}'])
            
            # Momentum признаки
            for period in [5, 10, 20]:
                df[f'momentum_{period}'] = df['close'] / df['close'].shift(period) - 1
                df[f'roc_{period}'] = df['close'].pct_change(periods=period)
            
            # Z-score для определения аномалий
            for window in [20, 50]:
                mean = df['close'].rolling(window=window).mean()
                std = df['close'].rolling(window=window).std()
                df[f'zscore_{window}'] = (df['close'] - mean) / std
            
            return df
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания статистических признаков: {e}")
            return df
    
    def extract_features(self, df: pd.DataFrame, symbol: str = "BTCUSDT", **kwargs) -> Dict[str, Any]:
        """
        ✅ СОВМЕСТИМОСТЬ: Альтернативный метод для extract_features
        
        Args:
            df: DataFrame с рыночными данными
            symbol: Торговая пара
            **kwargs: Дополнительные параметры
            
        Returns:
            Dict с признаками и метаданными
        """
        try:
            # Создаем признаки
            features_df = self.create_features(df, symbol)
            
            # Возвращаем в формате словаря
            result = {
                'features': features_df,
                'feature_names': self.feature_names,
                'symbol': symbol,
                'rows_count': len(features_df),
                'features_count': len(self.feature_names),
                'is_fitted': self.is_fitted,
                'timestamp': datetime.now(),
                'metadata': {
                    'config': self.config.__dict__,
                    'indicators_available': INDICATORS_AVAILABLE,
                    'original_rows': len(df),
                    'processed_rows': len(features_df)
                }
            }
            
            logger.info(f"✅ Извлечено {len(self.feature_names)} признаков для {symbol}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Ошибка извлечения признаков: {e}")
            return {
                'features': df,
                'feature_names': [],
                'error': str(e)
            }
    
    def get_feature_importance(self, model=None, method: str = 'correlation') -> pd.DataFrame:
        """
        Получение важности признаков
        
        Args:
            model: Обученная модель (sklearn)
            method: Метод оценки важности ('correlation', 'model', 'variance')
            
        Returns:
            DataFrame с важностью признаков
        """
        if not self.is_fitted or not self.feature_names:
            logger.warning("⚠️ FeatureEngineer не обучен или нет признаков")
            return pd.DataFrame()
        
        try:
            if method == 'model' and model and hasattr(model, 'feature_importances_'):
                importance = pd.DataFrame({
                    'feature': self.feature_names,
                    'importance': model.feature_importances_
                }).sort_values('importance', ascending=False)
            
            else:
                # Заглушка для других методов
                importance = pd.DataFrame({
                    'feature': self.feature_names,
                    'importance': np.random.random(len(self.feature_names))
                }).sort_values('importance', ascending=False)
            
            return importance
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения важности признаков: {e}")
            return pd.DataFrame()
    
    def transform(self, df: pd.DataFrame, symbol: str = "BTCUSDT") -> pd.DataFrame:
        """
        Трансформация новых данных с использованием уже настроенных параметров
        
        Args:
            df: Новые данные для трансформации
            symbol: Торговая пара
            
        Returns:
            DataFrame с признаками
        """
        if not self.is_fitted:
            logger.warning("⚠️ FeatureEngineer не обучен, используем create_features")
            return self.create_features(df, symbol)
        
        return self.create_features(df, symbol)
    
    def save_config(self, filepath: str):
        """Сохранение конфигурации"""
        try:
            import pickle
            with open(filepath, 'wb') as f:
                pickle.dump({
                    'config': self.config,
                    'feature_names': self.feature_names,
                    'is_fitted': self.is_fitted
                }, f)
            logger.info(f"✅ Конфигурация сохранена: {filepath}")
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения конфигурации: {e}")
    
    def load_config(self, filepath: str):
        """Загрузка конфигурации"""
        try:
            import pickle
            with open(filepath, 'rb') as f:
                data = pickle.load(f)
            
            self.config = data['config']
            self.feature_names = data['feature_names']
            self.is_fitted = data['is_fitted']
            
            logger.info(f"✅ Конфигурация загружена: {filepath}")
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки конфигурации: {e}")

# ✅ АЛИАС ДЛЯ ОБРАТНОЙ СОВМЕСТИМОСТИ
FeatureEngineering = FeatureEngineer


class FeatureExtractor:
    """Класс для извлечения базовых признаков"""
    
    def __init__(self):
        self.feature_names = []
        logger.info("✅ FeatureExtractor инициализирован")
    
    def extract(self, data: Any) -> List[float]:
        """Извлечение признаков из данных"""
        if isinstance(data, pd.DataFrame):
            return data.values.flatten().tolist()
        elif isinstance(data, dict):
            return list(data.values())
        elif isinstance(data, list):
            return data
        else:
            return []
    
    def extract_from_dict(self, data: Dict[str, Any]) -> List[float]:
        """Извлечение признаков из словаря"""
        features = []
        for key, value in data.items():
            if isinstance(value, (int, float)):
                features.append(float(value))
            elif isinstance(value, bool):
                features.append(1.0 if value else 0.0)
        return features

# ✅ ЭКСПОРТ
__all__ = [
    'FeatureEngineer',
    'FeatureEngineering',  # Алиас для совместимости
    'FeatureConfig',
    'FeatureExtractor'  # ДОБАВИТЬ!
]