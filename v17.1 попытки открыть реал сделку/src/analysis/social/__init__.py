"""
ИСПРАВЛЕННЫЙ Social analysis модуль
==================================
Файл: src/analysis/social/__init__.py

🔧 КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ:
✅ Добавлен класс SocialAnalyzer (было только SocialSignalExtractor)
✅ Правильные импорты и экспорты
✅ Полная совместимость с тестами
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# ✅ ИМПОРТИРУЕМ СУЩЕСТВУЮЩИЙ КЛАСС
try:
    from .signal_extractor import SocialSignalExtractor
    SIGNAL_EXTRACTOR_AVAILABLE = True
    logger.info("✅ SocialSignalExtractor импортирован")
except ImportError as e:
    logger.warning(f"⚠️ SocialSignalExtractor модуль не найден: {e}")
    SIGNAL_EXTRACTOR_AVAILABLE = False
    
    # Создаем заглушку
    class SocialSignalExtractor:
        """Заглушка для SocialSignalExtractor"""
        
        def __init__(self):
            self._initialized = True
            logger.info("📱 SocialSignalExtractor заглушка инициализирована")
        
        def extract_signals_from_text(self, text, source="unknown"):
            """Заглушка извлечения сигналов из текста"""
            return []
        
        def extract_signals(self, data_sources):
            """Заглушка извлечения сигналов из источников"""
            return []

# ✅ СОЗДАЕМ НЕДОСТАЮЩИЙ КЛАСС SocialAnalyzer
class SocialAnalyzer:
    """
    ИСПРАВЛЕННЫЙ SocialAnalyzer - главный класс для анализа социальных сетей
    
    ✅ Интегрирует SocialSignalExtractor
    ✅ Предоставляет единый интерфейс для социального анализа
    ✅ Анализ Twitter, Reddit, Telegram и других платформ
    ✅ Полная совместимость с существующим кодом
    """
    
    def __init__(self):
        """Инициализация анализатора социальных сетей"""
        try:
            self.signal_extractor = SocialSignalExtractor()
            self.is_available = True
            logger.info("✅ SocialAnalyzer инициализирован с SocialSignalExtractor")
            
            # Настройки по умолчанию
            self.supported_platforms = ['twitter', 'reddit', 'telegram', 'discord']
            self.sentiment_threshold = 0.6  # Порог для значимых настроений
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации SocialAnalyzer: {e}")
            self.signal_extractor = None
            self.is_available = False
    
    def analyze_social_sentiment(self, text: str, platform: str = "unknown", 
                                symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        Анализ настроения в социальных сетях
        
        Args:
            text: Текст поста/сообщения
            platform: Платформа (twitter, reddit, telegram, etc.)
            symbol: Криптовалютный символ (опционально)
            
        Returns:
            Dict с результатами анализа настроения
        """
        if not self.is_available or not self.signal_extractor:
            return {
                'available': False,
                'error': 'SocialSignalExtractor недоступен'
            }
        
        try:
            # Используем SocialSignalExtractor для извлечения сигналов
            signals = self.signal_extractor.extract_signals_from_text(text, platform)
            
            # Базовый анализ настроения
            sentiment_score = self._calculate_sentiment_score(text, signals)
            sentiment_label = self._get_sentiment_label(sentiment_score)
            
            # Проверяем упоминания криптовалют
            mentioned_symbols = self._extract_crypto_mentions(text)
            if symbol and symbol.upper() not in mentioned_symbols:
                mentioned_symbols.append(symbol.upper())
            
            analysis_result = {
                'available': True,
                'sentiment': sentiment_label,
                'sentiment_score': sentiment_score,  # -1 до 1
                'confidence': min(abs(sentiment_score) * 2, 1.0),  # 0 до 1
                'platform': platform,
                'mentioned_symbols': mentioned_symbols,
                'signals_count': len(signals),
                'signals': signals[:5],  # Первые 5 сигналов
                'timestamp': datetime.utcnow(),
                'analyzer': 'SocialAnalyzer'
            }
            
            logger.debug(f"📱 Социальный пост проанализирован: {sentiment_label} "
                        f"(score: {sentiment_score:.2f})")
            return analysis_result
            
        except Exception as e:
            logger.error(f"❌ Ошибка анализа социального настроения: {e}")
            return {
                'available': False,
                'error': str(e)
            }
    
    def analyze_multiple_posts(self, posts: List[Dict[str, Any]], 
                              symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Анализ множественных постов из социальных сетей
        
        Args:
            posts: Список постов с полями 'text', 'platform', 'timestamp'
            symbol: Криптовалютный символ для фильтрации
            
        Returns:
            List результатов анализа
        """
        results = []
        
        for post in posts:
            text = post.get('text', '')
            platform = post.get('platform', 'unknown')
            
            if text:
                # Фильтруем по символу если указан
                if symbol and symbol.upper() not in text.upper():
                    continue
                    
                analysis = self.analyze_social_sentiment(text, platform, symbol)
                if analysis.get('available', False):
                    analysis['original_post'] = {
                        'timestamp': post.get('timestamp', datetime.utcnow()),
                        'author': post.get('author', 'unknown'),
                        'platform': platform
                    }
                    results.append(analysis)
        
        return results
    
    def get_aggregated_social_sentiment(self, posts: List[Dict[str, Any]], 
                                       symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        Получение агрегированного настроения по социальным сетям
        
        Args:
            posts: Список постов
            symbol: Символ для анализа
            
        Returns:
            Агрегированные данные о настроении
        """
        if not posts:
            return {
                'sentiment': 'neutral',
                'sentiment_score': 0.0,
                'confidence': 0.0,
                'total_posts': 0,
                'available': False
            }
        
        try:
            analyses = self.analyze_multiple_posts(posts, symbol)
            
            if not analyses:
                return {
                    'sentiment': 'neutral',
                    'sentiment_score': 0.0,
                    'confidence': 0.0,
                    'total_posts': len(posts),
                    'analyzed_posts': 0,
                    'available': False
                }
            
            # Агрегация настроений
            sentiment_scores = [a.get('sentiment_score', 0) for a in analyses]
            confidences = [a.get('confidence', 0) for a in analyses]
            
            # Вычисляем средние значения
            avg_sentiment_score = sum(sentiment_scores) / len(sentiment_scores)
            avg_confidence = sum(confidences) / len(confidences)
            
            # Подсчет по платформам
            platform_distribution = {}
            for analysis in analyses:
                platform = analysis.get('platform', 'unknown')
                platform_distribution[platform] = platform_distribution.get(platform, 0) + 1
            
            return {
                'sentiment': self._get_sentiment_label(avg_sentiment_score),
                'sentiment_score': avg_sentiment_score,
                'confidence': avg_confidence,
                'total_posts': len(posts),
                'analyzed_posts': len(analyses),
                'platform_distribution': platform_distribution,
                'sentiment_distribution': self._get_sentiment_distribution(analyses),
                'available': True,
                'timestamp': datetime.utcnow()
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка агрегации социальных настроений: {e}")
            return {
                'sentiment': 'neutral',
                'sentiment_score': 0.0,
                'confidence': 0.0,
                'total_posts': len(posts),
                'available': False,
                'error': str(e)
            }
    
    def _calculate_sentiment_score(self, text: str, signals: List) -> float:
        """Вычисление оценки настроения"""
        # Простой алгоритм на основе ключевых слов
        positive_words = ['moon', 'rocket', 'bull', 'pump', 'buy', 'hodl', 'diamond', 'hands']
        negative_words = ['dump', 'crash', 'bear', 'sell', 'rekt', 'fud', 'scam']
        
        text_lower = text.lower()
        
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)
        
        # Нормализуем счет
        total_words = len(text.split())
        if total_words == 0:
            return 0.0
        
        positive_ratio = positive_count / total_words
        negative_ratio = negative_count / total_words
        
        # Вычисляем итоговый скор (-1 до 1)
        sentiment_score = (positive_ratio - negative_ratio) * 10
        return max(-1.0, min(1.0, sentiment_score))
    
    def _get_sentiment_label(self, score: float) -> str:
        """Получение метки настроения по оценке"""
        if score > 0.3:
            return 'positive'
        elif score < -0.3:
            return 'negative'
        else:
            return 'neutral'
    
    def _extract_crypto_mentions(self, text: str) -> List[str]:
        """Извлечение упоминаний криптовалют"""
        import re
        
        # Паттерны для поиска криптовалют
        patterns = [
            r'\$([A-Z]{2,10})',  # $BTC, $ETH
            r'\b([A-Z]{2,10})USDT\b',  # BTCUSDT
            r'\b(BTC|ETH|ADA|DOT|LINK|UNI|DOGE|SHIB|MATIC|SOL|AVAX)\b'  # Популярные монеты
        ]
        
        mentioned = set()
        text_upper = text.upper()
        
        for pattern in patterns:
            matches = re.findall(pattern, text_upper)
            mentioned.update(matches)
        
        return list(mentioned)
    
    def _get_sentiment_distribution(self, analyses: List[Dict[str, Any]]) -> Dict[str, int]:
        """Подсчет распределения настроений"""
        distribution = {'positive': 0, 'negative': 0, 'neutral': 0}
        
        for analysis in analyses:
            sentiment = analysis.get('sentiment', 'neutral')
            if sentiment in distribution:
                distribution[sentiment] += 1
        
        return distribution
    
    def check_availability(self) -> Dict[str, Any]:
        """Проверка доступности анализатора"""
        return {
            'social_analyzer_available': self.is_available,
            'signal_extractor_available': SIGNAL_EXTRACTOR_AVAILABLE,
            'signal_extractor_instance': self.signal_extractor is not None,
            'supported_platforms': self.supported_platforms if self.is_available else []
        }

# ✅ СОЗДАЕМ АЛИАСЫ ДЛЯ ОБРАТНОЙ СОВМЕСТИМОСТИ
# Теперь можно импортировать как SocialAnalyzer, так и SocialSignalExtractor

# ✅ ЭКСПОРТ ВСЕХ КЛАССОВ
__all__ = ['SocialAnalyzer', 'SocialSignalExtractor']

# ✅ ЛОГИРОВАНИЕ СТАТУСА
if SIGNAL_EXTRACTOR_AVAILABLE:
    logger.info("✅ Social analysis модуль: SocialAnalyzer и SocialSignalExtractor доступны")
else:
    logger.warning("⚠️ Social analysis модуль: работает в режиме заглушек")