"""
Модуль для работы с признаками ML
"""
try:
    from .feature_engineering import (
        FeatureEngineer, 
        FeatureEngineering,  # Алиас
        FeatureConfig,
        FeatureExtractor  # Если используется
    )
    _features_available = True
except ImportError as e:
    print(f"Ошибка импорта feature_engineering: {e}")
    _features_available = False
    
    # Заглушки на случай ошибки
    class FeatureConfig:
        def __init__(self, **kwargs):
            pass
    
    class FeatureEngineer:
        def __init__(self, config=None):
            self.config = config
            self.is_fitted = False
            self.feature_names = []
        
        def create_features(self, df, symbol="BTCUSDT"):
            return df
        
        def extract_features(self, *args, **kwargs):
            import pandas as pd
            return pd.DataFrame()
        
        def transform(self, df, symbol="BTCUSDT"):
            return df
    
    # Алиас
    FeatureEngineering = FeatureEngineer
    
    class FeatureExtractor:
        def __init__(self):
            pass
        
        def extract(self, *args, **kwargs):
            return []

__all__ = ['FeatureEngineer', 'FeatureEngineering', 'FeatureConfig', 'FeatureExtractor']