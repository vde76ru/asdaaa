"""
News Impact Scorer - Анализатор влияния новостей на рынок
Файл: src/analysis/news/impact_scorer.py

🎯 ФУНКЦИИ:
✅ Анализ настроений в новостях (sentiment analysis)
✅ Оценка влияния новостей на цену криптовалют
✅ Классификация важности новостных событий
✅ Интеграция с торговыми сигналами
"""

import re
import asyncio
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import logging

# Попытка импорта продвинутых библиотек
try:
    import nltk
    from textblob import TextBlob
    NLTK_AVAILABLE = True
except ImportError:
    NLTK_AVAILABLE = False
    logging.warning("⚠️ NLTK/TextBlob не установлены, используем базовый анализ")

try:
    from ...core.unified_config import unified_config as config
except ImportError:
    try:
        from ...core import unified_config as config
    except ImportError:
        # Заглушка если конфиг недоступен
        class MockConfig:
            def __getattr__(self, name):
                return None
        config = MockConfig()
from ...core.database import SessionLocal
from ...core.models import NewsAnalysis

logger = logging.getLogger(__name__)

class SentimentType(Enum):
    """Типы настроений"""
    VERY_NEGATIVE = "very_negative"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    POSITIVE = "positive"
    VERY_POSITIVE = "very_positive"

class NewsCategory(Enum):
    """Категории новостей"""
    REGULATORY = "regulatory"          # Регулирование
    TECHNICAL = "technical"            # Технические обновления
    ADOPTION = "adoption"              # Принятие/партнерства
    MARKET = "market"                  # Рыночные события
    SECURITY = "security"              # Безопасность/хакы
    MACROECONOMIC = "macroeconomic"    # Макроэкономика
    SOCIAL = "social"                  # Социальные события

@dataclass
class NewsImpact:
    """Результат анализа влияния новости"""
    sentiment: SentimentType
    sentiment_score: float       # -1 до 1
    impact_score: float         # 0 до 10
    category: NewsCategory
    confidence: float           # 0 до 1
    affected_symbols: List[str]
    key_phrases: List[str]
    urgency: str               # low/medium/high
    time_horizon: str          # short/medium/long

class NewsImpactScorer:
    """
    Анализатор влияния новостей на криптовалютные рынки
    
    🔥 ИНТЕЛЛЕКТУАЛЬНЫЙ АНАЛИЗ НОВОСТЕЙ:
    - Sentiment analysis с учетом контекста криптовалют
    - Классификация по типам событий и влиянию
    - Автоматическое извлечение упоминаемых криптовалют
    - Оценка временного горизонта влияния
    """
    
    def __init__(self):
        """Инициализация анализатора новостей"""
        
        # Ключевые слова для разных типов настроений
        self.positive_keywords = {
            'adoption': ['partnership', 'integration', 'mainstream', 'institutional', 
                        'партнерство', 'интеграция', 'принятие'],
            'technical': ['upgrade', 'improvement', 'scalability', 'efficiency',
                         'обновление', 'улучшение', 'масштабируемость'],
            'market': ['bullish', 'rally', 'surge', 'breakthrough', 'ATH',
                      'бычий', 'рост', 'прорыв', 'рекорд']
        }
        
        self.negative_keywords = {
            'regulatory': ['ban', 'restriction', 'regulation', 'crackdown',
                          'запрет', 'ограничение', 'регулирование'],
            'security': ['hack', 'exploit', 'vulnerability', 'breach',
                        'взлом', 'уязвимость', 'нарушение'],
            'market': ['crash', 'dump', 'bearish', 'decline', 'correction',
                      'падение', 'медвежий', 'коррекция']
        }
        
        # Символы криптовалют для поиска
        self.crypto_symbols = [
            'BTC', 'ETH', 'ADA', 'DOT', 'SOL', 'MATIC', 'AVAX', 'LINK', 
            'UNI', 'ATOM', 'NEAR', 'ALGO', 'XRP', 'LTC', 'BCH', 'EOS',
            'Bitcoin', 'Ethereum', 'Cardano', 'Polkadot', 'Solana'
        ]
        
        # Весовые коэффициенты для разных источников
        self.source_weights = {
            'reuters': 0.9,
            'bloomberg': 0.9,
            'coindesk': 0.8,
            'cointelegraph': 0.7,
            'decrypt': 0.7,
            'theblock': 0.8,
            'default': 0.5
        }
        
        logger.info("✅ NewsImpactScorer инициализирован")
    
    def score_news_impact(self, news_text: str, title: str = "", 
                         source: str = "unknown", symbol: str = None) -> NewsImpact:
        """
        Основной метод оценки влияния новости
        
        Args:
            news_text: Текст новости
            title: Заголовок новости
            source: Источник новости
            symbol: Конкретная криптовалюта (если известна)
            
        Returns:
            NewsImpact: Полный анализ влияния новости
        """
        try:
            # Объединяем заголовок и текст
            full_text = f"{title} {news_text}".strip()
            
            # Анализ настроений
            sentiment_result = self.analyze_sentiment(full_text)
            
            # Определение категории
            category = self._classify_news_category(full_text)
            
            # Поиск упоминаемых криптовалют
            affected_symbols = self._extract_crypto_symbols(full_text, symbol)
            
            # Ключевые фразы
            key_phrases = self._extract_key_phrases(full_text)
            
            # Расчет impact score
            impact_score = self._calculate_impact_score(
                sentiment_result, category, source, affected_symbols, key_phrases
            )
            
            # Определение срочности и временного горизонта
            urgency = self._determine_urgency(full_text, category)
            time_horizon = self._determine_time_horizon(category, sentiment_result['score'])
            
            # Уверенность в анализе
            confidence = self._calculate_confidence(
                sentiment_result, category, len(affected_symbols)
            )
            
            result = NewsImpact(
                sentiment=sentiment_result['sentiment'],
                sentiment_score=sentiment_result['score'],
                impact_score=impact_score,
                category=category,
                confidence=confidence,
                affected_symbols=affected_symbols,
                key_phrases=key_phrases,
                urgency=urgency,
                time_horizon=time_horizon
            )
            
            logger.debug(
                f"📰 Анализ новости: {sentiment_result['sentiment'].value}, "
                f"Impact: {impact_score:.1f}, Symbols: {affected_symbols}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Ошибка анализа новости: {e}")
            return self._get_default_impact(symbol)
    
    def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """Анализ настроений в тексте"""
        try:
            if NLTK_AVAILABLE:
                # Используем TextBlob для sentiment analysis
                blob = TextBlob(text)
                polarity = blob.sentiment.polarity
                
                # Корректируем с учетом криптовалютного контекста
                crypto_adjustment = self._crypto_context_adjustment(text)
                adjusted_polarity = polarity + crypto_adjustment
                adjusted_polarity = max(-1, min(1, adjusted_polarity))
                
            else:
                # Простой анализ на основе ключевых слов
                adjusted_polarity = self._simple_sentiment_analysis(text)
            
            # Классификация настроения
            if adjusted_polarity > 0.5:
                sentiment = SentimentType.VERY_POSITIVE
            elif adjusted_polarity > 0.1:
                sentiment = SentimentType.POSITIVE
            elif adjusted_polarity < -0.5:
                sentiment = SentimentType.VERY_NEGATIVE
            elif adjusted_polarity < -0.1:
                sentiment = SentimentType.NEGATIVE
            else:
                sentiment = SentimentType.NEUTRAL
            
            return {
                'sentiment': sentiment,
                'score': adjusted_polarity,
                'confidence': abs(adjusted_polarity) if abs(adjusted_polarity) > 0.1 else 0.3
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка анализа настроений: {e}")
            return {
                'sentiment': SentimentType.NEUTRAL,
                'score': 0.0,
                'confidence': 0.3
            }
    
    def _simple_sentiment_analysis(self, text: str) -> float:
        """Простой анализ настроений на основе ключевых слов"""
        text_lower = text.lower()
        positive_score = 0
        negative_score = 0
        
        # Подсчет позитивных ключевых слов
        for category, keywords in self.positive_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    positive_score += 1
        
        # Подсчет негативных ключевых слов
        for category, keywords in self.negative_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    negative_score += 1
        
        # Нормализация
        total_words = len(text.split())
        if total_words > 0:
            positive_ratio = positive_score / total_words * 10
            negative_ratio = negative_score / total_words * 10
            
            return max(-1, min(1, positive_ratio - negative_ratio))
        
        return 0.0
    
    def _crypto_context_adjustment(self, text: str) -> float:
        """Корректировка sentiment с учетом криптовалютного контекста"""
        text_lower = text.lower()
        adjustment = 0.0
        
        # Специальные паттерны для криптовалют
        crypto_positive = [
            'moon', 'hodl', 'diamond hands', 'to the moon', 'bullish',
            'adoption', 'mainstream', 'institutional'
        ]
        
        crypto_negative = [
            'dump', 'rug pull', 'bear market', 'crash', 'scam',
            'regulation', 'ban', 'crackdown'
        ]
        
        for phrase in crypto_positive:
            if phrase in text_lower:
                adjustment += 0.2
        
        for phrase in crypto_negative:
            if phrase in text_lower:
                adjustment -= 0.2
        
        return max(-0.5, min(0.5, adjustment))
    
    def _classify_news_category(self, text: str) -> NewsCategory:
        """Классификация категории новости"""
        text_lower = text.lower()
        
        # Паттерны для каждой категории
        category_patterns = {
            NewsCategory.REGULATORY: ['regulation', 'sec', 'government', 'legal', 'ban', 'law'],
            NewsCategory.TECHNICAL: ['upgrade', 'protocol', 'blockchain', 'update', 'fork'],
            NewsCategory.ADOPTION: ['partnership', 'integration', 'mainstream', 'institutional'],
            NewsCategory.SECURITY: ['hack', 'exploit', 'security', 'vulnerability', 'breach'],
            NewsCategory.MARKET: ['price', 'trading', 'volume', 'exchange', 'market'],
            NewsCategory.MACROECONOMIC: ['inflation', 'fed', 'economy', 'gdp', 'interest']
        }
        
        # Подсчет совпадений для каждой категории
        category_scores = {}
        for category, patterns in category_patterns.items():
            score = sum(1 for pattern in patterns if pattern in text_lower)
            category_scores[category] = score
        
        # Возвращаем категорию с максимальным счетом
        if category_scores:
            best_category = max(category_scores, key=category_scores.get)
            if category_scores[best_category] > 0:
                return best_category
        
        return NewsCategory.SOCIAL  # По умолчанию
    
    def _extract_crypto_symbols(self, text: str, hint_symbol: str = None) -> List[str]:
        """Извлечение упоминаемых криптовалют из текста"""
        found_symbols = set()
        text_upper = text.upper()
        
        # Если есть подсказка, добавляем её
        if hint_symbol:
            found_symbols.add(hint_symbol.upper())
        
        # Ищем известные символы
        for symbol in self.crypto_symbols:
            if symbol.upper() in text_upper:
                found_symbols.add(symbol.upper())
        
        # Поиск паттернов $SYMBOL
        dollar_pattern = r'\$([A-Z]{2,10})'
        dollar_matches = re.findall(dollar_pattern, text_upper)
        for match in dollar_matches:
            if len(match) >= 2:  # Минимум 2 символа
                found_symbols.add(match)
        
        return list(found_symbols)
    
    def _extract_key_phrases(self, text: str) -> List[str]:
        """Извлечение ключевых фраз из новости"""
        key_phrases = []
        text_lower = text.lower()
        
        # Важные фразы для криптовалют
        important_phrases = [
            'all-time high', 'market cap', 'price target', 'technical analysis',
            'whale movement', 'institutional adoption', 'regulatory approval',
            'new partnership', 'major update', 'security breach'
        ]
        
        for phrase in important_phrases:
            if phrase in text_lower:
                key_phrases.append(phrase)
        
        return key_phrases[:5]  # Максимум 5 фраз
    
    def _calculate_impact_score(self, sentiment_result: Dict, category: NewsCategory,
                              source: str, symbols: List[str], key_phrases: List[str]) -> float:
        """Расчет общего скора влияния новости"""
        try:
            base_score = abs(sentiment_result['score']) * 5  # Базовый скор 0-5
            
            # Корректировка по категории
            category_multipliers = {
                NewsCategory.REGULATORY: 1.5,    # Регулирование очень важно
                NewsCategory.SECURITY: 1.4,      # Безопасность критична
                NewsCategory.ADOPTION: 1.3,      # Принятие важно
                NewsCategory.TECHNICAL: 1.1,     # Технические обновления
                NewsCategory.MARKET: 1.0,        # Рыночные новости базовые
                NewsCategory.MACROECONOMIC: 1.2, # Макроэкономика важна
                NewsCategory.SOCIAL: 0.8         # Социальные события менее важны
            }
            
            category_score = base_score * category_multipliers.get(category, 1.0)
            
            # Корректировка по источнику
            source_weight = self.source_weights.get(source.lower(), 
                                                   self.source_weights['default'])
            source_score = category_score * source_weight
            
            # Бонус за упоминание множественных криптовалют
            symbol_bonus = min(len(symbols) * 0.5, 2.0)
            
            # Бонус за ключевые фразы
            phrase_bonus = min(len(key_phrases) * 0.3, 1.5)
            
            # Итоговый скор
            final_score = source_score + symbol_bonus + phrase_bonus
            
            # Ограничиваем 0-10
            return max(0, min(10, final_score))
            
        except Exception as e:
            logger.error(f"❌ Ошибка расчета impact score: {e}")
            return 5.0
    
    def _determine_urgency(self, text: str, category: NewsCategory) -> str:
        """Определение срочности новости"""
        text_lower = text.lower()
        
        urgent_keywords = ['breaking', 'urgent', 'emergency', 'immediate', 'срочно']
        
        if any(keyword in text_lower for keyword in urgent_keywords):
            return 'high'
        elif category in [NewsCategory.REGULATORY, NewsCategory.SECURITY]:
            return 'medium'
        else:
            return 'low'
    
    def _determine_time_horizon(self, category: NewsCategory, sentiment_score: float) -> str:
        """Определение временного горизонта влияния"""
        # Регулирование и принятие имеют долгосрочное влияние
        if category in [NewsCategory.REGULATORY, NewsCategory.ADOPTION]:
            return 'long'
        # Технические обновления имеют среднесрочное влияние
        elif category == NewsCategory.TECHNICAL:
            return 'medium'
        # Рыночные события и безопасность - краткосрочные
        else:
            return 'short'
    
    def _calculate_confidence(self, sentiment_result: Dict, category: NewsCategory,
                            symbols_count: int) -> float:
        """Расчет уверенности в анализе"""
        base_confidence = sentiment_result.get('confidence', 0.5)
        
        # Бонус за количество найденных символов
        symbol_bonus = min(symbols_count * 0.1, 0.3)
        
        # Различные категории дают разную уверенность
        category_confidence = {
            NewsCategory.REGULATORY: 0.8,
            NewsCategory.SECURITY: 0.9,
            NewsCategory.ADOPTION: 0.7,
            NewsCategory.TECHNICAL: 0.6,
            NewsCategory.MARKET: 0.5,
            NewsCategory.SOCIAL: 0.4
        }
        
        category_factor = category_confidence.get(category, 0.5)
        
        final_confidence = (base_confidence + symbol_bonus) * category_factor
        return max(0.2, min(0.95, final_confidence))
    
    def _get_default_impact(self, symbol: str = None) -> NewsImpact:
        """Возвращает нейтральный impact при ошибках"""
        return NewsImpact(
            sentiment=SentimentType.NEUTRAL,
            sentiment_score=0.0,
            impact_score=5.0,
            category=NewsCategory.SOCIAL,
            confidence=0.3,
            affected_symbols=[symbol] if symbol else [],
            key_phrases=[],
            urgency='low',
            time_horizon='short'
        )
    
    async def analyze_news_batch(self, news_items: List[Dict]) -> List[NewsImpact]:
        """Анализ множественных новостей"""
        results = []
        
        for news in news_items:
            try:
                impact = self.score_news_impact(
                    news_text=news.get('content', ''),
                    title=news.get('title', ''),
                    source=news.get('source', 'unknown'),
                    symbol=news.get('symbol')
                )
                results.append(impact)
            except Exception as e:
                logger.error(f"❌ Ошибка анализа новости: {e}")
                results.append(self._get_default_impact())
        
        return results

# Экспорт
__all__ = [
    'NewsImpactScorer',
    'NewsImpact',
    'SentimentType',
    'NewsCategory'
]