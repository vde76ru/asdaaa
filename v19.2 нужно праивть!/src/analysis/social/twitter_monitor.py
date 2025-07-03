"""
Мониторинг Twitter для криптовалютных сигналов
Файл: src/analysis/social/twitter_monitor.py
"""
import os
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Set
import re
from collections import defaultdict, deque  # ← ДОБАВИТЬ deque ЗДЕСЬ!
import json

import tweepy
from tweepy import StreamingClient, StreamRule
import numpy as np

from ...core.database import SessionLocal
from ...logging.smart_logger import SmartLogger
from ..news.nlp_analyzer import nlp_analyzer


class TwitterMonitor:
    # ✅ ДОБАВИТЬ SINGLETON
    _instance = None
    _initialized = False
    
    
    
    
    
    # Ключевые аккаунты для мониторинга
    KEY_ACCOUNTS = {
        # Влиятельные персоны
        'elonmusk': {'influence': 10, 'category': 'influencer'},
        'michael_saylor': {'influence': 9, 'category': 'bitcoin_bull'},
        'APompliano': {'influence': 8, 'category': 'crypto_influencer'},
        'CathieDWood': {'influence': 8, 'category': 'investor'},
        'novogratz': {'influence': 7, 'category': 'investor'},
        'cameron': {'influence': 7, 'category': 'bitcoin_bull'},
        'tyler': {'influence': 7, 'category': 'bitcoin_bull'},
        
        # Аналитики и трейдеры
        'CryptoCred': {'influence': 8, 'category': 'trader'},
        'CryptoKaleo': {'influence': 7, 'category': 'trader'},
        'AltcoinPsycho': {'influence': 7, 'category': 'trader'},
        'CryptoGainz1': {'influence': 6, 'category': 'trader'},
        'TheCryptoLark': {'influence': 6, 'category': 'analyst'},
        
        # Новостные аккаунты
        'CoinDesk': {'influence': 8, 'category': 'news'},
        'Cointelegraph': {'influence': 7, 'category': 'news'},
        'TheBlock__': {'influence': 7, 'category': 'news'},
        'Decrypt': {'influence': 6, 'category': 'news'},
        
        # Проекты и биржи
        'binance': {'influence': 9, 'category': 'exchange'},
        'coinbase': {'influence': 8, 'category': 'exchange'},
        'krakenfx': {'influence': 7, 'category': 'exchange'},
        'ethereum': {'influence': 8, 'category': 'project'},
        'solana': {'influence': 7, 'category': 'project'},
    }
    
    # Ключевые слова для отслеживания
    TRACK_KEYWORDS = [
        # Общие крипто термины
        'bitcoin', 'btc', 'ethereum', 'eth', 'crypto',
        
        # Торговые сигналы
        'bullish', 'bearish', 'buy signal', 'sell signal',
        'long', 'short', 'pump', 'dump', 'moon',
        
        # Важные события
        'breaking', 'announcement', 'partnership', 'listing',
        'hack', 'exploit', 'regulation', 'sec',
        
        # Технический анализ
        'support', 'resistance', 'breakout', 'breakdown',
        'golden cross', 'death cross', 'rsi', 'macd'
    ]
    
    # Паттерны для извлечения цен
    PRICE_PATTERNS = [
        r'\$(\d+(?:,\d+)*(?:\.\d+)?)',  # $1,234.56
        r'(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:usd|USD|dollars?)',  # 1234.56 USD
        r'price:?\s*(\d+(?:,\d+)*(?:\.\d+)?)',  # price: 1234.56
    ]
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TwitterMonitor, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        # ✅ ИСПРАВЛЕННАЯ ПРОВЕРКА SINGLETON
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self._initialized = True
        TwitterMonitor._initialized = True

        
        # Инициализируем logger
        self.logger = SmartLogger("TwitterMonitor")
        
        # API credentials из переменных окружения
        self.api_key = os.getenv('TWITTER_API_KEY')
        self.api_secret = os.getenv('TWITTER_API_SECRET')
        self.bearer_token = os.getenv('TWITTER_BEARER_TOKEN')
        self.access_token = os.getenv('TWITTER_ACCESS_TOKEN')
        self.access_token_secret = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')
        
        # Клиент Twitter
        self.client = None
        self.stream = None
        
        # Кэш для избежания дубликатов
        self.processed_tweets: Set[str] = set()
        self.tweet_cache = deque(maxlen=1000)
        
        # Статистика
        self.stats = defaultdict(int)
        
        # Инициализация (только один раз!)
        self._init_client()
    
    def _init_client(self):
        """Инициализация Twitter клиента"""
        if not self.bearer_token:
            self.logger.warning(
                "Twitter Bearer Token не найден. Установите TWITTER_BEARER_TOKEN",
                category='social'
            )
            return
        
        try:
            # Клиент для API v2
            self.client = tweepy.Client(
                bearer_token=self.bearer_token,
                consumer_key=self.api_key,
                consumer_secret=self.api_secret,
                access_token=self.access_token,
                access_token_secret=self.access_token_secret,
                wait_on_rate_limit=True
            )
            
            # ✅ ЛОГИРУЕМ ТОЛЬКО ОДИН РАЗ
            self.logger.info(
                "Twitter клиент инициализирован",
                category='social'
            )
            
        except Exception as e:
            self.logger.error(
                f"Ошибка инициализации Twitter: {e}",
                category='social'
            )
    
    def get_instance_info(self):
        """
        ✅ ДОБАВЛЕНО: Метод для отладки Singleton
        """
        return {
            'instance_id': id(self),
            'initialized': TwitterMonitor._initialized,
            'has_client': self.client is not None,
            'stats': dict(self.stats)
        }
    
    def extract_crypto_mentions(self, text: str) -> List[str]:
        """Извлекает упоминания криптовалют из текста"""
        mentions = []
        text_lower = text.lower()
        
        # Проверяем известные криптовалюты
        crypto_patterns = {
            'BTC': [r'\bbtc\b', r'\bbitcoin\b', r'\$btc\b'],
            'ETH': [r'\beth\b', r'\bethereum\b', r'\$eth\b'],
            'BNB': [r'\bbnb\b', r'\bbinance coin\b', r'\$bnb\b'],
            'SOL': [r'\bsol\b', r'\bsolana\b', r'\$sol\b'],
            'XRP': [r'\bxrp\b', r'\bripple\b', r'\$xrp\b'],
            'ADA': [r'\bada\b', r'\bcardano\b', r'\$ada\b'],
            'DOGE': [r'\bdoge\b', r'\bdogecoin\b', r'\$doge\b'],
            'AVAX': [r'\bavax\b', r'\bavalanche\b', r'\$avax\b'],
            'DOT': [r'\bdot\b', r'\bpolkadot\b', r'\$dot\b'],
            'MATIC': [r'\bmatic\b', r'\bpolygon\b', r'\$matic\b'],
        }
        
        for symbol, patterns in crypto_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    if symbol not in mentions:
                        mentions.append(symbol)
                    break
        
        # Также ищем тикеры с $
        ticker_pattern = r'\$([A-Z]{2,10})\b'
        tickers = re.findall(ticker_pattern, text.upper())
        for ticker in tickers:
            if ticker not in mentions and len(ticker) <= 5:
                mentions.append(ticker)
        
        return mentions
    
    def extract_price_targets(self, text: str) -> List[float]:
        """Извлекает ценовые цели из текста"""
        prices = []
        
        for pattern in self.PRICE_PATTERNS:
            matches = re.findall(pattern, text)
            for match in matches:
                try:
                    # Убираем запятые и конвертируем в float
                    price = float(match.replace(',', ''))
                    if 0.00001 <= price <= 1000000:  # Разумные границы
                        prices.append(price)
                except:
                    pass
        
        return prices
    
    def calculate_influence_score(self, 
                                user_data: Dict[str, Any],
                                engagement: Dict[str, int]) -> float:
        """
        Рассчитывает оценку влияния твита
        
        Args:
            user_data: Данные пользователя
            engagement: Метрики вовлеченности (likes, retweets)
            
        Returns:
            Оценка влияния от 0 до 10
        """
        score = 0.0
        
        # Базовая оценка от известных аккаунтов
        username = user_data.get('username', '').lower()
        if username in self.KEY_ACCOUNTS:
            score = self.KEY_ACCOUNTS[username]['influence']
        else:
            # Оценка на основе подписчиков
            followers = user_data.get('followers_count', 0)
            if followers > 1000000:
                score = 7.0
            elif followers > 100000:
                score = 5.0
            elif followers > 10000:
                score = 3.0
            elif followers > 1000:
                score = 1.0
        
        # Модификаторы на основе вовлеченности
        likes = engagement.get('like_count', 0)
        retweets = engagement.get('retweet_count', 0)
        
        # Коэффициент вовлеченности
        if user_data.get('followers_count', 0) > 0:
            engagement_rate = (likes + retweets * 2) / user_data['followers_count']
            if engagement_rate > 0.1:  # Очень высокая вовлеченность
                score *= 1.5
            elif engagement_rate > 0.05:
                score *= 1.2
        
        # Проверка верификации
        if user_data.get('verified', False):
            score *= 1.2
        
        return min(score, 10.0)
    
    async def analyze_tweet(self, tweet_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Анализирует твит на наличие торговых сигналов
        
        Args:
            tweet_data: Данные твита от Twitter API
            
        Returns:
            Результат анализа
        """
        try:
            tweet_id = tweet_data.get('id')
            
            # Проверяем, не обработан ли уже
            if tweet_id in self.processed_tweets:
                return None
            
            self.processed_tweets.add(tweet_id)
            
            # Извлекаем данные
            text = tweet_data.get('text', '')
            author = tweet_data.get('author_id_obj', {})
            metrics = tweet_data.get('public_metrics', {})
            created_at = datetime.strptime(
                tweet_data.get('created_at', ''),
                '%Y-%m-%dT%H:%M:%S.%fZ'
            )
            
            # Анализ текста
            nlp_result = await nlp_analyzer.analyze_text(text)
            
            # Извлекаем криптовалюты и цены
            cryptos = self.extract_crypto_mentions(text)
            prices = self.extract_price_targets(text)
            
            # Рассчитываем влияние
            influence_score = self.calculate_influence_score(author, metrics)
            
            # Определяем тип сигнала
            signal_type = self._determine_signal_type(text, nlp_result['sentiment'])
            
            result = {
                'tweet_id': tweet_id,
                'author': author.get('username', 'unknown'),
                'author_followers': author.get('followers_count', 0),
                'text': text,
                'url': f"https://twitter.com/{author.get('username')}/status/{tweet_id}",
                'sentiment': nlp_result['sentiment'],
                'keywords': nlp_result['keywords'],
                'mentioned_cryptos': cryptos,
                'price_targets': prices,
                'influence_score': influence_score,
                'engagement': {
                    'likes': metrics.get('like_count', 0),
                    'retweets': metrics.get('retweet_count', 0),
                    'replies': metrics.get('reply_count', 0)
                },
                'signal_type': signal_type,
                'created_at': created_at,
                'analyzed_at': datetime.utcnow()
            }
            
            # Обновляем статистику
            self.stats['tweets_analyzed'] += 1
            self.stats[f'signal_{signal_type}'] += 1
            
            # Кэшируем
            self.tweet_cache.append(result)
            
            # Логируем важные сигналы
            if influence_score > 5 and signal_type in ['buy', 'sell']:
                self.logger.info(
                    f"Важный сигнал от @{author.get('username')}: {signal_type}",
                    category='social',
                    signal_type=signal_type,
                    cryptos=cryptos,
                    influence=influence_score
                )
            
            return result
            
        except Exception as e:
            self.logger.error(
                f"Ошибка анализа твита: {e}",
                category='social'
            )
            return None
    
    def _determine_signal_type(self, text: str, sentiment: Dict[str, Any]) -> str:
        """
        Определяет тип торгового сигнала
        
        Args:
            text: Текст твита
            sentiment: Результат sentiment анализа
            
        Returns:
            Тип сигнала: buy/sell/neutral/news
        """
        text_lower = text.lower()
        
        # Явные торговые сигналы
        buy_signals = [
            'buy', 'long', 'bullish', 'accumulate', 'moon',
            'breakout', 'pump', 'rocket', '🚀', '📈'
        ]
        
        sell_signals = [
            'sell', 'short', 'bearish', 'dump', 'crash',
            'breakdown', 'exit', '📉', '🔻'
        ]
        
        # Подсчет сигналов
        buy_count = sum(1 for signal in buy_signals if signal in text_lower)
        sell_count = sum(1 for signal in sell_signals if signal in text_lower)
        
        # Учитываем sentiment
        sentiment_label = sentiment.get('label', 'neutral')
        sentiment_score = sentiment.get('compound', 0)
        
        if buy_count > sell_count:
            if sentiment_label == 'positive' or sentiment_score > 0.3:
                return 'buy'
            return 'neutral'
        elif sell_count > buy_count:
            if sentiment_label == 'negative' or sentiment_score < -0.3:
                return 'sell'
            return 'neutral'
        else:
            # Проверяем, новость ли это
            news_keywords = ['breaking', 'news', 'announced', 'report', 'update']
            if any(keyword in text_lower for keyword in news_keywords):
                return 'news'
            
            # По умолчанию на основе sentiment
            if sentiment_score > 0.5:
                return 'buy'
            elif sentiment_score < -0.5:
                return 'sell'
            
            return 'neutral'
    
    async def search_tweets(self, 
                          query: str,
                          max_results: int = 100,
                          hours_back: int = 24) -> List[Dict[str, Any]]:
        """
        Поиск твитов по запросу
        
        Args:
            query: Поисковый запрос
            max_results: Максимум результатов
            hours_back: Сколько часов назад искать
            
        Returns:
            Список проанализированных твитов
        """
        if not self.client:
            self.logger.error("Twitter клиент не инициализирован", category='social')
            return []
        
        try:
            # Время начала поиска
            start_time = datetime.utcnow() - timedelta(hours=hours_back)
            
            # Поиск твитов
            tweets = self.client.search_recent_tweets(
                query=query,
                start_time=start_time.isoformat() + 'Z',
                max_results=min(max_results, 100),
                tweet_fields=['created_at', 'public_metrics', 'author_id'],
                user_fields=['username', 'verified', 'public_metrics'],
                expansions=['author_id']
            )
            
            if not tweets.data:
                return []
            
            # Создаем маппинг пользователей
            users_map = {}
            if tweets.includes and 'users' in tweets.includes:
                for user in tweets.includes['users']:
                    users_map[user.id] = user.data
            
            # Анализируем твиты
            results = []
            for tweet in tweets.data:
                tweet_dict = tweet.data
                
                # Добавляем данные автора
                if tweet.author_id in users_map:
                    tweet_dict['author_id_obj'] = users_map[tweet.author_id]
                
                # Анализируем
                analysis = await self.analyze_tweet(tweet_dict)
                if analysis:
                    results.append(analysis)
            
            self.logger.info(
                f"Найдено и проанализировано {len(results)} твитов",
                category='social',
                query=query
            )
            
            return results
            
        except Exception as e:
            self.logger.error(
                f"Ошибка поиска твитов: {e}",
                category='social'
            )
            return []
    
    async def monitor_key_accounts(self) -> List[Dict[str, Any]]:
        """Мониторит твиты ключевых аккаунтов"""
        all_results = []
        
        for account, info in self.KEY_ACCOUNTS.items():
            try:
                # Поиск твитов от аккаунта
                query = f"from:{account} (crypto OR bitcoin OR ethereum)"
                results = await self.search_tweets(query, max_results=10, hours_back=6)
                all_results.extend(results)
                
                # Небольшая задержка для избежания rate limit
                await asyncio.sleep(1)
                
            except Exception as e:
                self.logger.error(
                    f"Ошибка мониторинга @{account}: {e}",
                    category='social'
                )
        
        return all_results
    
    async def get_market_sentiment(self, symbol: str) -> Dict[str, Any]:
        """
        Получает общее настроение рынка для символа
        
        Args:
            symbol: Торговый символ (BTC, ETH, etc)
            
        Returns:
            Анализ настроений
        """
        # Поиск твитов о символе
        query = f"({symbol} OR #{symbol}) (crypto OR cryptocurrency) -is:retweet"
        tweets = await self.search_tweets(query, max_results=100, hours_back=12)
        
        if not tweets:
            return {
                'symbol': symbol,
                'sentiment': 'neutral',
                'score': 0.0,
                'tweets_analyzed': 0
            }
        
        # Агрегируем sentiment
        sentiments = []
        influences = []
        
        for tweet in tweets:
            sentiment_score = tweet['sentiment']['compound']
            influence = tweet['influence_score']
            
            # Взвешенный sentiment
            sentiments.append(sentiment_score * influence)
            influences.append(influence)
        
        # Средневзвешенный sentiment
        if sum(influences) > 0:
            avg_sentiment = sum(sentiments) / sum(influences)
        else:
            avg_sentiment = np.mean([t['sentiment']['compound'] for t in tweets])
        
        # Определяем общее настроение
        if avg_sentiment > 0.1:
            overall_sentiment = 'bullish'
        elif avg_sentiment < -0.1:
            overall_sentiment = 'bearish'
        else:
            overall_sentiment = 'neutral'
        
        # Считаем сигналы
        signal_counts = defaultdict(int)
        for tweet in tweets:
            signal_counts[tweet['signal_type']] += 1
        
        return {
            'symbol': symbol,
            'sentiment': overall_sentiment,
            'score': round(avg_sentiment, 3),
            'tweets_analyzed': len(tweets),
            'signal_distribution': dict(signal_counts),
            'top_influencers': self._get_top_influencers(tweets),
            'timestamp': datetime.utcnow()
        }
    
    def _get_top_influencers(self, tweets: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
        """Получает топ влиятельных аккаунтов из твитов"""
        # Группируем по авторам
        author_tweets = defaultdict(list)
        
        for tweet in tweets:
            author = tweet['author']
            author_tweets[author].append(tweet)
        
        # Считаем влияние
        author_influence = []
        
        for author, tweets in author_tweets.items():
            max_influence = max(t['influence_score'] for t in tweets)
            avg_sentiment = np.mean([t['sentiment']['compound'] for t in tweets])
            
            author_influence.append({
                'author': author,
                'influence': max_influence,
                'tweets_count': len(tweets),
                'avg_sentiment': round(avg_sentiment, 3),
                'followers': tweets[0]['author_followers']
            })
        
        # Сортируем по влиянию
        author_influence.sort(key=lambda x: x['influence'], reverse=True)
        
        return author_influence[:limit]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Получает статистику работы монитора"""
        return {
            'tweets_analyzed': self.stats['tweets_analyzed'],
            'signals': {
                'buy': self.stats.get('signal_buy', 0),
                'sell': self.stats.get('signal_sell', 0),
                'neutral': self.stats.get('signal_neutral', 0),
                'news': self.stats.get('signal_news', 0)
            },
            'cache_size': len(self.tweet_cache),
            'processed_tweets': len(self.processed_tweets)
        }


# Создаем глобальный экземпляр
twitter_monitor = TwitterMonitor()