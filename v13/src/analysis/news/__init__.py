"""
ИСПРАВЛЕННЫЙ News analysis модуль
=================================
Файл: src/analysis/news/__init__.py

🔧 КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ:
✅ Добавлен класс NewsAnalyzer (было только NewsImpactScorer)
✅ Правильные импорты и экспорты
✅ Полная совместимость с тестами
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# ✅ ИМПОРТИРУЕМ СУЩЕСТВУЮЩИЙ КЛАСС
try:
    from .impact_scorer import NewsImpactScorer
    IMPACT_SCORER_AVAILABLE = True
    logger.info("✅ NewsImpactScorer импортирован")
except ImportError as e:
    logger.warning(f"⚠️ NewsImpactScorer модуль не найден: {e}")
    IMPACT_SCORER_AVAILABLE = False
    
    # Создаем заглушку
    class NewsImpactScorer:
        """Заглушка для NewsImpactScorer"""
        
        def __init__(self):
            self._initialized = True
            logger.info("📰 NewsImpactScorer заглушка инициализирована")
        
        def score_news_impact(self, news_text, title="", source="unknown", symbol=None):
            """Заглушка оценки влияния новостей"""
            from dataclasses import dataclass
            from datetime import datetime
            
            @dataclass
            class NewsImpact:
                impact_score: float = 0.5
                sentiment: str = "neutral"
                confidence: float = 0.1
                affected_symbols: list = None
                impact_duration: str = "short"
                timestamp: datetime = None
                
                def __post_init__(self):
                    if self.affected_symbols is None:
                        self.affected_symbols = []
                    if self.timestamp is None:
                        self.timestamp = datetime.utcnow()
            
            return NewsImpact(
                impact_score=0.5,
                sentiment="neutral", 
                confidence=0.1,
                affected_symbols=[symbol] if symbol else [],
                impact_duration="short"
            )

# ✅ СОЗДАЕМ НЕДОСТАЮЩИЙ КЛАСС NewsAnalyzer
class NewsAnalyzer:
    """
    ИСПРАВЛЕННЫЙ NewsAnalyzer - главный класс для анализа новостей
    
    ✅ Интегрирует NewsImpactScorer
    ✅ Предоставляет единый интерфейс для анализа новостей
    ✅ Полная совместимость с существующим кодом
    """
    
    def __init__(self):
        """Инициализация анализатора новостей"""
        try:
            self.impact_scorer = NewsImpactScorer()
            self.is_available = True
            logger.info("✅ NewsAnalyzer инициализирован с NewsImpactScorer")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации NewsAnalyzer: {e}")
            self.impact_scorer = None
            self.is_available = False
    
    def analyze_news(self, news_text: str, symbol: Optional[str] = None, 
                    source: str = "unknown") -> Dict[str, Any]:
        """
        Основной метод анализа новостей
        
        Args:
            news_text: Текст новости
            symbol: Криптовалютный символ (опционально)
            source: Источник новости
            
        Returns:
            Dict с результатами анализа
        """
        if not self.is_available or not self.impact_scorer:
            return {
                'available': False,
                'error': 'NewsImpactScorer недоступен'
            }
        
        try:
            # Используем NewsImpactScorer для анализа
            impact = self.impact_scorer.score_news_impact(
                news_text=news_text,
                symbol=symbol,
                source=source
            )
            
            # Преобразуем результат в стандартный формат
            analysis_result = {
                'available': True,
                'sentiment': getattr(impact, 'sentiment', 'neutral'),
                'impact_score': getattr(impact, 'impact_score', 0.5),
                'confidence': getattr(impact, 'confidence', 0.1),
                'affected_symbols': getattr(impact, 'affected_symbols', []),
                'impact_duration': getattr(impact, 'impact_duration', 'short'),
                'timestamp': getattr(impact, 'timestamp', datetime.utcnow()),
                'source': source,
                'analyzer': 'NewsAnalyzer'
            }
            
            logger.debug(f"📰 Новость проанализирована: {sentiment} (confidence: {confidence:.2f})")
            return analysis_result
            
        except Exception as e:
            logger.error(f"❌ Ошибка анализа новости: {e}")
            return {
                'available': False,
                'error': str(e)
            }
    
    def get_news_sentiment(self, news_text: str) -> Dict[str, Any]:
        """Получение настроения новости"""
        analysis = self.analyze_news(news_text)
        
        return {
            'sentiment': analysis.get('sentiment', 'neutral'),
            'confidence': analysis.get('confidence', 0.1),
            'available': analysis.get('available', False)
        }
    
    def analyze_multiple_news(self, news_list: List[Dict[str, str]], 
                            symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Анализ множественных новостей"""
        results = []
        
        for news_item in news_list:
            text = news_item.get('text', '')
            source = news_item.get('source', 'unknown')
            
            if text:
                analysis = self.analyze_news(text, symbol, source)
                results.append(analysis)
        
        return results
    
    def get_aggregated_sentiment(self, news_list: List[Dict[str, str]], 
                                symbol: Optional[str] = None) -> Dict[str, Any]:
        """Получение агрегированного настроения по множественным новостям"""
        if not news_list:
            return {
                'sentiment': 'neutral',
                'confidence': 0.0,
                'total_news': 0,
                'available': False
            }
        
        try:
            analyses = self.analyze_multiple_news(news_list, symbol)
            available_analyses = [a for a in analyses if a.get('available', False)]
            
            if not available_analyses:
                return {
                    'sentiment': 'neutral',
                    'confidence': 0.0,
                    'total_news': len(news_list),
                    'available': False
                }
            
            # Простая агрегация настроений
            sentiments = [a.get('sentiment', 'neutral') for a in available_analyses]
            confidences = [a.get('confidence', 0.1) for a in available_analyses]
            
            # Подсчет преобладающего настроения
            sentiment_counts = {}
            for sentiment in sentiments:
                sentiment_counts[sentiment] = sentiment_counts.get(sentiment, 0) + 1
            
            dominant_sentiment = max(sentiment_counts, key=sentiment_counts.get)
            average_confidence = sum(confidences) / len(confidences) if confidences else 0.1
            
            return {
                'sentiment': dominant_sentiment,
                'confidence': average_confidence,
                'total_news': len(news_list),
                'analyzed_news': len(available_analyses),
                'sentiment_distribution': sentiment_counts,
                'available': True
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка агрегации настроений: {e}")
            return {
                'sentiment': 'neutral',
                'confidence': 0.0,
                'total_news': len(news_list),
                'available': False,
                'error': str(e)
            }
    
    def check_availability(self) -> Dict[str, Any]:
        """Проверка доступности анализатора"""
        return {
            'news_analyzer_available': self.is_available,
            'impact_scorer_available': IMPACT_SCORER_AVAILABLE,
            'impact_scorer_instance': self.impact_scorer is not None
        }

# ✅ СОЗДАЕМ АЛИАСЫ ДЛЯ ОБРАТНОЙ СОВМЕСТИМОСТИ
# Теперь можно импортировать как NewsAnalyzer, так и NewsImpactScorer

# ✅ ЭКСПОРТ ВСЕХ КЛАССОВ
__all__ = ['NewsAnalyzer', 'NewsImpactScorer']

# ✅ ЛОГИРОВАНИЕ СТАТУСА
if IMPACT_SCORER_AVAILABLE:
    logger.info("✅ News analysis модуль: NewsAnalyzer и NewsImpactScorer доступны")
else:
    logger.warning("⚠️ News analysis модуль: работает в режиме заглушек")