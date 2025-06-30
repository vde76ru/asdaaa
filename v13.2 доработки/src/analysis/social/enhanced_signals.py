"""
Улучшенная система социальных сигналов
Файл: src/analysis/social/enhanced_signals.py
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass

from ...core.database import SessionLocal
from ...core.models import SocialSignal

logger = logging.getLogger(__name__)

@dataclass
class EnhancedSocialSignal:
    """Улучшенный социальный сигнал"""
    source: str
    symbol: str
    sentiment: str  # positive, negative, neutral
    confidence: float
    content: str
    author: str
    timestamp: datetime
    engagement: int
    influence_score: float

class EnhancedSocialSignalsManager:
    """Улучшенный менеджер социальных сигналов"""
    
    def __init__(self):
        self.active_sources = ['twitter', 'reddit', 'telegram']
        
    async def get_signals_for_symbol(self, symbol: str, limit: int = 20) -> List[EnhancedSocialSignal]:
        """Получение сигналов для конкретного символа"""
        try:
            # Используем существующий signal_extractor
            from .signal_extractor import signal_extractor
            
            # Получаем сигналы
            signals = await signal_extractor.extract_signals()
            
            # Фильтруем по символу
            filtered_signals = []
            for signal in signals:
                if symbol.upper() in signal.get('mentioned_coins', []):
                    enhanced_signal = EnhancedSocialSignal(
                        source=signal.get('source', 'unknown'),
                        symbol=symbol,
                        sentiment=self._determine_sentiment(signal.get('text', '')),
                        confidence=signal.get('quality_score', 0.5),
                        content=signal.get('text', '')[:200],
                        author=signal.get('author', 'unknown'),
                        timestamp=signal.get('timestamp', datetime.now()),
                        engagement=signal.get('engagement', 0),
                        influence_score=self._calculate_influence(signal)
                    )
                    filtered_signals.append(enhanced_signal)
            
            return filtered_signals[:limit]
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения социальных сигналов: {e}")
            return []
    
    def _determine_sentiment(self, text: str) -> str:
        """Простое определение настроения"""
        text_lower = text.lower()
        
        positive_words = ['buy', 'long', 'bullish', 'moon', 'pump', 'rocket']
        negative_words = ['sell', 'short', 'bearish', 'dump', 'crash', 'drop']
        
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)
        
        if positive_count > negative_count:
            return 'positive'
        elif negative_count > positive_count:
            return 'negative'
        else:
            return 'neutral'
    
    def _calculate_influence(self, signal: Dict) -> float:
        """Расчет влияния сигнала"""
        base_score = 0.5
        
        # Увеличиваем за подписчиков
        followers = signal.get('author_followers', 0)
        if followers > 100000:
            base_score += 0.3
        elif followers > 10000:
            base_score += 0.2
        elif followers > 1000:
            base_score += 0.1
        
        # Увеличиваем за вовлеченность
        engagement = signal.get('engagement', 0)
        if engagement > 1000:
            base_score += 0.2
        elif engagement > 100:
            base_score += 0.1
        
        return min(base_score, 1.0)

# Создаем глобальный экземпляр
enhanced_social_manager = EnhancedSocialSignalsManager()