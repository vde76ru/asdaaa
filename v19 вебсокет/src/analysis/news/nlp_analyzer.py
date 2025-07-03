"""
NLP анализатор для обработки текста новостей
Файл: src/analysis/news/nlp_analyzer.py
"""
import re
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import numpy as np
from collections import Counter

# NLP библиотеки
import nltk
from textblob import TextBlob
from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification
import torch

# Загрузка необходимых ресурсов NLTK
try:
    nltk.download('punkt', quiet=True)
    nltk.download('stopwords', quiet=True)
    nltk.download('vader_lexicon', quiet=True)
    nltk.download('wordnet', quiet=True)
except:
    pass

from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize, sent_tokenize
from nltk.sentiment import SentimentIntensityAnalyzer

from ...core.database import SessionLocal
from ...logging.smart_logger import SmartLogger


class NLPAnalyzer:
    """
    Анализатор текста с использованием NLP для криптоновостей
    """
    
    # Ключевые слова для криптовалют
    CRYPTO_KEYWORDS = {
        'BTC': ['bitcoin', 'btc', 'satoshi'],
        'ETH': ['ethereum', 'eth', 'ether', 'vitalik'],
        'BNB': ['binance', 'bnb', 'cz'],
        'SOL': ['solana', 'sol'],
        'XRP': ['ripple', 'xrp'],
        'ADA': ['cardano', 'ada'],
        'DOGE': ['dogecoin', 'doge', 'shiba'],
        'AVAX': ['avalanche', 'avax'],
        'DOT': ['polkadot', 'dot'],
        'MATIC': ['polygon', 'matic'],
        'LINK': ['chainlink', 'link'],
        'UNI': ['uniswap', 'uni'],
        'ATOM': ['cosmos', 'atom'],
        'LTC': ['litecoin', 'ltc'],
        'FTT': ['ftx', 'ftt'],
        'XLM': ['stellar', 'xlm'],
        'NEAR': ['near', 'near protocol'],
        'ALGO': ['algorand', 'algo'],
        'CRO': ['crypto.com', 'cro', 'cronos'],
        'APE': ['apecoin', 'ape', 'bayc']
    }
    
    # Ключевые слова для определения типа новости
    BULLISH_KEYWORDS = [
        'surge', 'rally', 'bullish', 'pump', 'moon', 'breakout', 'gains',
        'profit', 'buy', 'accumulate', 'upgrade', 'partnership', 'adoption',
        'institutional', 'invest', 'positive', 'growth', 'recover', 'support',
        'resistance broken', 'all time high', 'ath', 'golden cross'
    ]
    
    BEARISH_KEYWORDS = [
        'crash', 'dump', 'bearish', 'sell', 'decline', 'plunge', 'fear',
        'panic', 'loss', 'negative', 'warning', 'scam', 'hack', 'exploit',
        'regulation', 'ban', 'lawsuit', 'investigation', 'fraud', 'fud',
        'death cross', 'resistance', 'rejected', 'breakdown'
    ]
    
    # Важные сущности
    IMPORTANT_ENTITIES = [
        'sec', 'cftc', 'fed', 'ecb', 'china', 'usa', 'europe', 'asia',
        'goldman sachs', 'jp morgan', 'blackrock', 'microstrategy',
        'tesla', 'paypal', 'square', 'grayscale', 'coinbase', 'binance',
        'kraken', 'ftx', 'celsius', 'blockfi', 'genesis'
    ]
    
    def __init__(self):
        self.logger = SmartLogger("NLPAnalyzer")
        
        # Инициализация анализаторов
        self.sia = SentimentIntensityAnalyzer()
        
        # Загрузка стоп-слов
        self.stop_words = set(stopwords.words('english'))
        
        # Инициализация трансформеров для продвинутого анализа
        self._init_transformers()
        
        # Кэш для моделей
        self._sentiment_cache = {}
        
    def _init_transformers(self):
        """Инициализация моделей трансформеров"""
        try:
            # Модель для анализа финансовых текстов
            self.finbert = pipeline(
                "sentiment-analysis",
                model="ProsusAI/finbert",
                device=0 if torch.cuda.is_available() else -1
            )
            
            # Модель для извлечения именованных сущностей
            self.ner = pipeline(
                "ner",
                model="dslim/bert-base-NER",
                device=0 if torch.cuda.is_available() else -1
            )
            
        except Exception as e:
            self.logger.warning(
                f"Не удалось загрузить трансформеры: {e}",
                category='nlp'
            )
            self.finbert = None
            self.ner = None
    
    def preprocess_text(self, text: str) -> str:
        """Предобработка текста"""
        # Нижний регистр
        text = text.lower()
        
        # Удаление URL
        text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
        
        # Удаление email
        text = re.sub(r'\S+@\S+', '', text)
        
        # Удаление специальных символов, но оставляем знаки препинания для sentiment
        text = re.sub(r'[^\w\s\.\,\!\?\-]', '', text)
        
        # Удаление лишних пробелов
        text = ' '.join(text.split())
        
        return text
    
    def extract_keywords(self, text: str, num_keywords: int = 10) -> List[str]:
        """Извлечение ключевых слов"""
        # Токенизация
        tokens = word_tokenize(text.lower())
        
        # Удаление стоп-слов и коротких слов
        filtered_tokens = [
            token for token in tokens 
            if token not in self.stop_words and len(token) > 2 and token.isalpha()
        ]
        
        # Подсчет частоты
        word_freq = Counter(filtered_tokens)
        
        # Возвращаем топ ключевых слов
        return [word for word, _ in word_freq.most_common(num_keywords)]
    
    def detect_cryptocurrencies(self, text: str) -> List[str]:
        """Определение упомянутых криптовалют"""
        text_lower = text.lower()
        detected_cryptos = []
        
        for symbol, keywords in self.CRYPTO_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    if symbol not in detected_cryptos:
                        detected_cryptos.append(symbol)
                    break
        
        return detected_cryptos
    
    def analyze_sentiment(self, text: str) -> Dict[str, float]:
        """
        Анализ тональности текста
        
        Returns:
            Dict с оценками sentiment
        """
        # Базовый анализ с VADER
        vader_scores = self.sia.polarity_scores(text)
        
        result = {
            'positive': vader_scores['pos'],
            'negative': vader_scores['neg'],
            'neutral': vader_scores['neu'],
            'compound': vader_scores['compound'],
            'label': 'neutral',
            'confidence': 0.0
        }
        
        # Определение основной метки
        if vader_scores['compound'] >= 0.05:
            result['label'] = 'positive'
        elif vader_scores['compound'] <= -0.05:
            result['label'] = 'negative'
        
        # Продвинутый анализ с FinBERT если доступен
        if self.finbert and len(text) > 20:
            try:
                # Ограничиваем длину текста для BERT
                truncated_text = text[:512]
                
                finbert_result = self.finbert(truncated_text)[0]
                
                # Преобразуем метки FinBERT
                label_map = {
                    'positive': 'positive',
                    'negative': 'negative',
                    'neutral': 'neutral'
                }
                
                finbert_label = label_map.get(finbert_result['label'].lower(), 'neutral')
                finbert_score = finbert_result['score']
                
                # Комбинируем результаты
                if finbert_score > 0.8:
                    result['label'] = finbert_label
                    result['confidence'] = finbert_score
                else:
                    # Взвешенное среднее
                    result['confidence'] = (abs(vader_scores['compound']) + finbert_score) / 2
                
                result['finbert_label'] = finbert_label
                result['finbert_score'] = finbert_score
                
            except Exception as e:
                self.logger.debug(f"Ошибка FinBERT: {e}", category='nlp')
        
        return result
    
    def calculate_market_impact(self, text: str, sentiment: Dict[str, float]) -> float:
        """
        Расчет потенциального влияния на рынок
        
        Returns:
            Оценка влияния от 0 до 10
        """
        impact_score = 0.0
        
        text_lower = text.lower()
        
        # Проверка наличия важных сущностей
        for entity in self.IMPORTANT_ENTITIES:
            if entity in text_lower:
                impact_score += 1.0
        
        # Проверка ключевых слов
        bullish_count = sum(1 for word in self.BULLISH_KEYWORDS if word in text_lower)
        bearish_count = sum(1 for word in self.BEARISH_KEYWORDS if word in text_lower)
        
        keyword_impact = (bullish_count + bearish_count) * 0.5
        impact_score += min(keyword_impact, 3.0)
        
        # Учет силы sentiment
        sentiment_strength = abs(sentiment['compound'])
        impact_score += sentiment_strength * 2.0
        
        # Проверка наличия чисел (возможно, цены или проценты)
        numbers = re.findall(r'\b\d+(?:\.\d+)?%?\b', text)
        if numbers:
            impact_score += min(len(numbers) * 0.3, 1.5)
        
        # Нормализация до 0-10
        impact_score = min(impact_score, 10.0)
        
        return round(impact_score, 2)
    
    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """Извлечение именованных сущностей"""
        entities = {
            'persons': [],
            'organizations': [],
            'locations': [],
            'misc': []
        }
        
        if self.ner and len(text) > 10:
            try:
                # NER анализ
                ner_results = self.ner(text[:512])  # Ограничение для BERT
                
                for entity in ner_results:
                    entity_type = entity['entity'].split('-')[-1]
                    entity_text = entity['word'].replace('##', '')
                    
                    if entity_type == 'PER' and entity_text not in entities['persons']:
                        entities['persons'].append(entity_text)
                    elif entity_type == 'ORG' and entity_text not in entities['organizations']:
                        entities['organizations'].append(entity_text)
                    elif entity_type == 'LOC' and entity_text not in entities['locations']:
                        entities['locations'].append(entity_text)
                    elif entity_type == 'MISC' and entity_text not in entities['misc']:
                        entities['misc'].append(entity_text)
                
            except Exception as e:
                self.logger.debug(f"Ошибка NER: {e}", category='nlp')
        
        # Дополнительное извлечение известных сущностей
        text_lower = text.lower()
        for entity in self.IMPORTANT_ENTITIES:
            if entity in text_lower and entity not in entities['organizations']:
                entities['organizations'].append(entity)
        
        return entities
    
    def analyze_news_relevance(self, text: str, target_symbols: List[str]) -> float:
        """
        Анализ релевантности новости для конкретных символов
        
        Args:
            text: Текст новости
            target_symbols: Список интересующих символов
            
        Returns:
            Оценка релевантности от 0 до 1
        """
        if not target_symbols:
            return 0.0
        
        detected_cryptos = self.detect_cryptocurrencies(text)
        
        if not detected_cryptos:
            return 0.0
        
        # Проверка совпадений
        matches = set(detected_cryptos) & set(target_symbols)
        
        if not matches:
            return 0.0
        
        # Базовая релевантность
        relevance = len(matches) / len(target_symbols)
        
        # Учитываем позицию упоминания (раньше = важнее)
        text_lower = text.lower()
        position_bonus = 0.0
        
        for symbol in matches:
            keywords = self.CRYPTO_KEYWORDS.get(symbol, [])
            for keyword in keywords:
                pos = text_lower.find(keyword)
                if pos != -1:
                    # Чем раньше упоминание, тем выше бонус
                    position_bonus += (1.0 - pos / len(text_lower)) * 0.2
                    break
        
        relevance += min(position_bonus, 0.3)
        
        return min(relevance, 1.0)
    
    async def analyze_text(self, text: str, 
                          title: str = None,
                          target_symbols: List[str] = None) -> Dict[str, Any]:
        """
        Полный анализ текста новости
        
        Args:
            text: Основной текст
            title: Заголовок (опционально)
            target_symbols: Целевые символы для анализа релевантности
            
        Returns:
            Словарь с результатами анализа
        """
        try:
            # Предобработка
            processed_text = self.preprocess_text(text)
            if title:
                processed_title = self.preprocess_text(title)
                # Заголовок важнее - анализируем отдельно
                full_text = f"{processed_title}. {processed_text}"
            else:
                full_text = processed_text
            
            # Основной анализ
            sentiment = self.analyze_sentiment(full_text)
            keywords = self.extract_keywords(full_text)
            cryptos = self.detect_cryptocurrencies(full_text)
            entities = self.extract_entities(text)  # Используем оригинальный текст для NER
            impact = self.calculate_market_impact(full_text, sentiment)
            
            # Релевантность
            relevance = 0.0
            if target_symbols:
                relevance = self.analyze_news_relevance(full_text, target_symbols)
            
            # Создание резюме
            sentences = sent_tokenize(text)
            summary = ' '.join(sentences[:2]) if len(sentences) > 2 else text
            
            result = {
                'sentiment': sentiment,
                'impact_score': impact,
                'relevance_score': relevance,
                'keywords': keywords,
                'detected_cryptos': cryptos,
                'entities': entities,
                'summary': summary[:500],  # Ограничиваем длину
                'analysis_timestamp': datetime.utcnow()
            }
            
            self.logger.debug(
                f"Анализ завершен: sentiment={sentiment['label']}, impact={impact}",
                category='nlp',
                cryptos=cryptos
            )
            
            return result
            
        except Exception as e:
            self.logger.error(
                f"Ошибка анализа текста: {e}",
                category='nlp'
            )
            
            # Возвращаем базовый результат
            return {
                'sentiment': {
                    'label': 'neutral',
                    'compound': 0.0,
                    'confidence': 0.0
                },
                'impact_score': 0.0,
                'relevance_score': 0.0,
                'keywords': [],
                'detected_cryptos': [],
                'entities': {},
                'summary': text[:500] if text else '',
                'analysis_timestamp': datetime.utcnow(),
                'error': str(e)
            }
    
    def batch_analyze(self, texts: List[Dict[str, str]], 
                     target_symbols: List[str] = None) -> List[Dict[str, Any]]:
        """
        Пакетный анализ текстов
        
        Args:
            texts: Список словарей с 'text' и опционально 'title'
            target_symbols: Целевые символы
            
        Returns:
            Список результатов анализа
        """
        results = []
        
        for item in texts:
            text = item.get('text', '')
            title = item.get('title', '')
            
            if text:
                result = asyncio.run(
                    self.analyze_text(text, title, target_symbols)
                )
                results.append(result)
        
        return results


# Создаем глобальный экземпляр
nlp_analyzer = NLPAnalyzer()