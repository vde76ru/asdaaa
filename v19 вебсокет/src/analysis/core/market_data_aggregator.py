"""
Market Data Aggregator для агрегации рыночных данных
Файл: src/analysis/core/market_data_aggregator.py
"""
import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class MarketDataAggregator:
    """Агрегатор рыночных данных"""
    
    def __init__(self):
        self.data_cache = {}
        logger.info("✅ MarketDataAggregator инициализирован")
    
    def aggregate_data(self, symbol: str, timeframe: str) -> Dict:
        """Агрегация данных по символу"""
        return {
            'symbol': symbol,
            'timeframe': timeframe,
            'timestamp': datetime.utcnow(),
            'aggregated': True
        }
    
    def get_market_summary(self, symbols: List[str]) -> Dict:
        """Получение сводки по рынку"""
        return {
            'symbols_count': len(symbols),
            'status': 'active',
            'last_update': datetime.utcnow()
        }
    
    def cache_data(self, symbol: str, data: Dict):
        """Кэширование данных"""
        self.data_cache[symbol] = {
            'data': data,
            'timestamp': datetime.utcnow()
        }
    
    def get_cached_data(self, symbol: str) -> Optional[Dict]:
        """Получение кэшированных данных"""
        return self.data_cache.get(symbol)