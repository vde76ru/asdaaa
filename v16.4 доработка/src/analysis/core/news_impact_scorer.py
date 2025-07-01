"""
News Impact Scorer для анализа влияния новостей
Файл: src/analysis/core/news_impact_scorer.py
"""
import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class NewsImpactScorer:
    """Оценка влияния новостей на рынок"""
    
    def __init__(self):
        self.impact_weights = {
            'regulation': 0.8,
            'partnership': 0.6,
            'technology': 0.5,
            'market': 0.7,
            'default': 0.3
        }
        logger.info("✅ NewsImpactScorer инициализирован")
    
    def calculate_impact(self, news_item: Dict) -> float:
        """Расчет влияния новости"""
        try:
            category = news_item.get('category', 'default')
            base_score = self.impact_weights.get(category, 0.3)
            
            if news_item.get('is_breaking', False):
                base_score *= 1.5
            
            if news_item.get('source_reliability', 0) > 0.8:
                base_score *= 1.2
            
            return min(1.0, max(0.0, base_score))
            
        except Exception as e:
            logger.error(f"Ошибка расчета влияния: {e}")
            return 0.3
    
    def analyze_sentiment(self, text: str) -> float:
        """Анализ тональности текста"""
        try:
            positive_words = ['growth', 'surge', 'bullish', 'adoption', 'partnership']
            negative_words = ['crash', 'ban', 'hack', 'bearish', 'lawsuit']
            
            text_lower = text.lower()
            
            positive_count = sum(1 for word in positive_words if word in text_lower)
            negative_count = sum(1 for word in negative_words if word in text_lower)
            
            if positive_count > negative_count:
                return 0.7
            elif negative_count > positive_count:
                return 0.3
            else:
                return 0.5
                
        except Exception as e:
            logger.error(f"Ошибка анализа тональности: {e}")
            return 0.5

    def score_news_impact(self, news_text: str, title: str = "", source: str = "unknown", symbol: str = None):
        """Главный метод для оценки влияния новости"""
        try:
            sentiment_score = self.analyze_sentiment(news_text + " " + title)
            
            class NewsImpact:
                def __init__(self):
                    self.impact_score = sentiment_score
                    self.sentiment = "positive" if sentiment_score > 0.6 else "negative" if sentiment_score < 0.4 else "neutral"
                    self.confidence = 0.5
                    self.affected_symbols = [symbol] if symbol else []
                    self.impact_duration = "short"
                    self.timestamp = datetime.utcnow()
            
            return NewsImpact()
            
        except Exception as e:
            logger.error(f"Ошибка анализа новости: {e}")
            class NeutralImpact:
                def __init__(self):
                    self.impact_score = 0.5
                    self.sentiment = "neutral"
                    self.confidence = 0.3
                    self.affected_symbols = []
                    self.impact_duration = "short"
                    self.timestamp = datetime.utcnow()
            
            return NeutralImpact()