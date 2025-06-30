"""
Мониторинг Reddit для криптовалютных сигналов
Файл: src/analysis/social/reddit_monitor.py
"""
import os
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Set
import re
from collections import defaultdict, deque
import praw
import prawcore
import numpy as np

from ...core.database import SessionLocal
from ...logging.smart_logger import SmartLogger
from ..news.nlp_analyzer import nlp_analyzer


class RedditMonitor:
    """
    Мониторит Reddit для поиска криптовалютных сигналов и настроений
    
    ✅ ИСПРАВЛЕНО: Singleton паттерн для предотвращения дублирования логов
    """
    
    # ✅ ДОБАВЛЕНО: Singleton атрибуты
    _instance = None
    _initialized = False
    
    # Ключевые сабреддиты для мониторинга
    KEY_SUBREDDITS = {
        # Основные крипто сабреддиты
        'cryptocurrency': {'weight': 1.0, 'category': 'general'},
        'bitcoin': {'weight': 0.9, 'category': 'bitcoin'},
        'ethereum': {'weight': 0.9, 'category': 'ethereum'},
        'altcoin': {'weight': 0.8, 'category': 'altcoins'},
        'cryptomarkets': {'weight': 0.9, 'category': 'trading'},
        'cryptocurrencytrading': {'weight': 0.8, 'category': 'trading'},
        
        # Специализированные
        'cryptomoonshots': {'weight': 0.5, 'category': 'speculation'},
        'satoshistreetbets': {'weight': 0.6, 'category': 'speculation'},
        'wallstreetbetscrypto': {'weight': 0.6, 'category': 'speculation'},
        
        # Технический анализ
        'cryptotechnicalanalysis': {'weight': 0.8, 'category': 'technical'},
        'bitcoinmarkets': {'weight': 0.8, 'category': 'technical'},
        
        # DeFi и специфичные
        'defi': {'weight': 0.7, 'category': 'defi'},
        'nft': {'weight': 0.6, 'category': 'nft'},
        
        # Проекты
        'cardano': {'weight': 0.7, 'category': 'project'},
        'solana': {'weight': 0.7, 'category': 'project'},
        'binance': {'weight': 0.7, 'category': 'project'},
        'dogecoin': {'weight': 0.6, 'category': 'project'},
    }
    
    # Флейры, указывающие на важность
    IMPORTANT_FLAIRS = {
        'news': 1.2,
        'discussion': 1.0,
        'technical analysis': 1.3,
        'analysis': 1.2,
        'warning': 1.5,
        'scam alert': 1.5,
        'due diligence': 1.3,
        'dd': 1.3
    }
    
    # Паттерны для pump & dump
    PUMP_DUMP_PATTERNS = [
        r'to the moon',
        r'moon\s*(?:ing|shot|bound)',
        r'(?:100|1000)x',
        r'get in (?:now|early|before)',
        r'don\'t miss (?:out|this)',
        r'next (?:bitcoin|ethereum|100x)',
        r'guaranteed (?:profit|gains|return)',
        r'(?:buy|get) now or regret',
        r'pumping (?:hard|now)',
        r'easy (?:money|profit)',
        r'insider (?:info|tip)',
    ]
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RedditMonitor, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        # ✅ ИСПРАВЛЕННАЯ ПРОВЕРКА SINGLETON
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self._initialized = True
        RedditMonitor._initialized = True

        
        # Инициализируем logger
        self.logger = SmartLogger("RedditMonitor")
        
        # API credentials из переменных окружения
        self.client_id = os.getenv('REDDIT_CLIENT_ID')
        self.client_secret = os.getenv('REDDIT_CLIENT_SECRET')
        self.user_agent = os.getenv('REDDIT_USER_AGENT', 'CryptoBot/1.0')
        
        # Reddit клиент
        self.reddit = None
        
        # Кэш для избежания дубликатов
        self.processed_posts: Set[str] = set()
        self.processed_comments: Set[str] = set()
        self.post_cache = deque(maxlen=1000)
        
        # Статистика
        self.stats = defaultdict(int)
        
        # Инициализация (только один раз!)
        self._init_client()
    
    def _init_client(self):
        """Инициализация Reddit клиента"""
        if not self.client_id or not self.client_secret:
            self.logger.warning(
                "Reddit credentials не найдены. Установите REDDIT_CLIENT_ID и REDDIT_CLIENT_SECRET",
                category='social'
            )
            return
        
        try:
            # Клиент Reddit
            self.reddit = praw.Reddit(
                client_id=self.client_id,
                client_secret=self.client_secret,
                user_agent=self.user_agent,
                timeout=30
            )
            
            # Проверяем подключение
            self.reddit.user.me()
            
            # ✅ ЛОГИРУЕМ ТОЛЬКО ОДИН РАЗ
            self.logger.info(
                "Reddit клиент инициализирован",
                category='social'
            )
            
        except prawcore.exceptions.ResponseException:
            # Reddit работает в read-only режиме без аутентификации
            self.logger.info(
                "Reddit клиент инициализирован в read-only режиме",
                category='social'
            )
            
        except Exception as e:
            self.logger.error(
                f"Ошибка инициализации Reddit: {e}",
                category='social'
            )
    
    def get_instance_info(self):
        """
        ✅ ДОБАВЛЕНО: Метод для отладки Singleton
        """
        return {
            'instance_id': id(self),
            'initialized': RedditMonitor._initialized,
            'has_client': self.reddit is not None,
            'stats': dict(self.stats)
        }
    
    def _init_reddit(self):
        """Инициализация Reddit клиента"""
        if not self.client_id or not self.client_secret:
            self.logger.warning(
                "Reddit credentials не найдены. Установите REDDIT_CLIENT_ID и REDDIT_CLIENT_SECRET",
                category='social'
            )
            return
        
        try:
            self.reddit = praw.Reddit(
                client_id=self.client_id,
                client_secret=self.client_secret,
                user_agent=self.user_agent
            )
            
            # Проверка подключения
            self.reddit.user.me()
            
            self.logger.info(
                "Reddit клиент инициализирован",
                category='social'
            )
            
        except prawcore.exceptions.ResponseException:
            # Режим read-only (без аутентификации пользователя)
            self.reddit = praw.Reddit(
                client_id=self.client_id,
                client_secret=self.client_secret,
                user_agent=self.user_agent
            )
            self.logger.info(
                "Reddit клиент инициализирован в режиме read-only",
                category='social'
            )
            
        except Exception as e:
            self.logger.error(
                f"Ошибка инициализации Reddit: {e}",
                category='social'
            )
    
    def extract_tickers(self, text: str) -> List[str]:
        """Извлекает тикеры криптовалют из текста"""
        tickers = []
        
        # Паттерны для тикеров
        patterns = [
            r'\$([A-Z]{2,10})\b',  # $BTC
            r'\b([A-Z]{2,10})\b(?:\s*(?:coin|token|crypto))',  # BTC coin
            r'(?:buy|sell|long|short)\s+([A-Z]{2,10})\b',  # buy BTC
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if 2 <= len(match) <= 5 and match not in tickers:
                    # Фильтруем общие слова
                    if match not in ['THE', 'AND', 'FOR', 'NOT', 'BUT', 'CAN', 'WILL']:
                        tickers.append(match)
        
        # Проверяем известные криптовалюты
        known_cryptos = {
            'bitcoin': 'BTC', 'ethereum': 'ETH', 'binance': 'BNB',
            'cardano': 'ADA', 'solana': 'SOL', 'polygon': 'MATIC',
            'dogecoin': 'DOGE', 'shiba': 'SHIB', 'ripple': 'XRP'
        }
        
        text_lower = text.lower()
        for name, ticker in known_cryptos.items():
            if name in text_lower and ticker not in tickers:
                tickers.append(ticker)
        
        return tickers
    
    def detect_pump_dump(self, text: str) -> float:
        """
        Определяет вероятность pump & dump схемы
        
        Returns:
            Вероятность от 0 до 1
        """
        text_lower = text.lower()
        score = 0.0
        
        # Проверка паттернов
        for pattern in self.PUMP_DUMP_PATTERNS:
            if re.search(pattern, text_lower):
                score += 0.15
        
        # Дополнительные признаки
        if text.count('!') > 3:
            score += 0.1
        if text.count('🚀') > 2:
            score += 0.1
        if 'not financial advice' in text_lower:
            score += 0.05
        
        # Проверка на множественные эмодзи
        emoji_pattern = r'[🚀🌙💎🙌💰💸📈📊🔥🎯💯]'
        emoji_count = len(re.findall(emoji_pattern, text))
        if emoji_count > 5:
            score += 0.1
        
        return min(score, 1.0)
    
    def calculate_post_quality(self, post_data: Dict[str, Any]) -> float:
        """
        Оценивает качество поста
        
        Returns:
            Оценка качества от 0 до 10
        """
        score = 5.0  # Базовая оценка
        
        # Факторы качества
        text_length = len(post_data.get('text', ''))
        upvote_ratio = post_data.get('upvote_ratio', 0.5)
        score_value = post_data.get('score', 0)
        num_comments = post_data.get('num_comments', 0)
        
        # Длина текста
        if text_length > 500:
            score += 1.0
        elif text_length < 100:
            score -= 1.0
        
        # Соотношение upvotes
        if upvote_ratio > 0.9:
            score += 2.0
        elif upvote_ratio > 0.8:
            score += 1.0
        elif upvote_ratio < 0.5:
            score -= 2.0
        
        # Абсолютное количество upvotes
        if score_value > 1000:
            score += 2.0
        elif score_value > 100:
            score += 1.0
        elif score_value < 0:
            score -= 2.0
        
        # Вовлеченность (комментарии)
        if num_comments > 100:
            score += 1.0
        elif num_comments > 20:
            score += 0.5
        
        # Проверка на pump & dump
        pump_dump_prob = self.detect_pump_dump(post_data.get('text', ''))
        if pump_dump_prob > 0.5:
            score -= 3.0
        
        # Учет флейра
        flair = post_data.get('flair', '').lower()
        for important_flair, multiplier in self.IMPORTANT_FLAIRS.items():
            if important_flair in flair:
                score *= multiplier
                break
        
        return max(0.0, min(score, 10.0))
    
    async def analyze_post(self, post) -> Optional[Dict[str, Any]]:
        """
        Анализирует Reddit пост
        
        Args:
            post: PRAW post объект
            
        Returns:
            Результат анализа
        """
        try:
            # Проверяем, не обработан ли уже
            if post.id in self.processed_posts:
                return None
            
            self.processed_posts.add(post.id)
            
            # Извлекаем текст
            text = f"{post.title}\n{post.selftext}" if post.selftext else post.title
            
            # NLP анализ
            nlp_result = await nlp_analyzer.analyze_text(text)
            
            # Извлекаем тикеры
            tickers = self.extract_tickers(text)
            
            # Данные поста
            post_data = {
                'id': post.id,
                'title': post.title,
                'text': text,
                'author': str(post.author) if post.author else '[deleted]',
                'subreddit': str(post.subreddit),
                'score': post.score,
                'upvote_ratio': post.upvote_ratio,
                'num_comments': post.num_comments,
                'flair': post.link_flair_text or '',
                'created_utc': datetime.fromtimestamp(post.created_utc),
                'url': f"https://reddit.com{post.permalink}"
            }
            
            # Оценка качества
            quality_score = self.calculate_post_quality(post_data)
            
            # Обнаружение pump & dump
            pump_dump_score = self.detect_pump_dump(text)
            
            # Вес сабреддита
            subreddit_weight = self.KEY_SUBREDDITS.get(
                post.subreddit.display_name.lower(), 
                {'weight': 0.5}
            )['weight']
            
            # Финальная оценка влияния
            influence_score = quality_score * subreddit_weight
            
            result = {
                'post_id': post.id,
                'type': 'post',
                'subreddit': post.subreddit.display_name,
                'author': post_data['author'],
                'title': post.title,
                'text': text[:1000],  # Ограничиваем длину
                'url': post_data['url'],
                'sentiment': nlp_result['sentiment'],
                'keywords': nlp_result['keywords'],
                'mentioned_cryptos': tickers,
                'quality_score': round(quality_score, 2),
                'influence_score': round(influence_score, 2),
                'pump_dump_probability': round(pump_dump_score, 2),
                'metrics': {
                    'score': post.score,
                    'upvote_ratio': post.upvote_ratio,
                    'comments': post.num_comments
                },
                'created_at': post_data['created_utc'],
                'analyzed_at': datetime.utcnow()
            }
            
            # Определяем сигнал
            result['signal_type'] = self._determine_signal(result)
            
            # Обновляем статистику
            self.stats['posts_analyzed'] += 1
            self.stats[f'signal_{result["signal_type"]}'] += 1
            
            # Кэшируем
            self.post_cache.append(result)
            
            # Логируем важные посты
            if influence_score > 7:
                self.logger.info(
                    f"Важный пост в r/{post.subreddit}: {post.title[:50]}...",
                    category='social',
                    influence=influence_score,
                    cryptos=tickers
                )
            
            return result
            
        except Exception as e:
            self.logger.error(
                f"Ошибка анализа поста: {e}",
                category='social'
            )
            return None
    
    async def analyze_comment(self, comment) -> Optional[Dict[str, Any]]:
        """Анализирует комментарий Reddit"""
        try:
            # Проверяем, не обработан ли уже
            if comment.id in self.processed_comments:
                return None
            
            self.processed_comments.add(comment.id)
            
            # Пропускаем короткие комментарии
            if len(comment.body) < 20:
                return None
            
            # NLP анализ
            nlp_result = await nlp_analyzer.analyze_text(comment.body)
            
            # Извлекаем тикеры
            tickers = self.extract_tickers(comment.body)
            
            # Если нет упоминаний крипты, пропускаем
            if not tickers and not nlp_result.get('detected_cryptos'):
                return None
            
            result = {
                'comment_id': comment.id,
                'type': 'comment',
                'subreddit': str(comment.subreddit),
                'author': str(comment.author) if comment.author else '[deleted]',
                'text': comment.body[:500],
                'sentiment': nlp_result['sentiment'],
                'mentioned_cryptos': tickers,
                'score': comment.score,
                'created_at': datetime.fromtimestamp(comment.created_utc),
                'analyzed_at': datetime.utcnow()
            }
            
            return result
            
        except Exception as e:
            self.logger.debug(f"Ошибка анализа комментария: {e}", category='social')
            return None
    
    def _determine_signal(self, analysis: Dict[str, Any]) -> str:
        """Определяет тип торгового сигнала"""
        sentiment = analysis['sentiment']
        pump_dump = analysis['pump_dump_probability']
        quality = analysis['quality_score']
        
        # Фильтруем pump & dump
        if pump_dump > 0.6:
            return 'pump_dump_warning'
        
        # Низкое качество = игнорируем
        if quality < 3:
            return 'low_quality'
        
        # На основе sentiment и качества
        sentiment_score = sentiment.get('compound', 0)
        
        if sentiment_score > 0.5 and quality > 6:
            return 'buy'
        elif sentiment_score < -0.5 and quality > 6:
            return 'sell'
        elif quality > 7:
            return 'high_quality_neutral'
        
        return 'neutral'
    
    async def monitor_subreddit(self, 
                              subreddit_name: str,
                              sort_by: str = 'hot',
                              limit: int = 25) -> List[Dict[str, Any]]:
        """
        Мониторит конкретный сабреддит
        
        Args:
            subreddit_name: Название сабреддита
            sort_by: Сортировка (hot, new, top, rising)
            limit: Количество постов
            
        Returns:
            Список проанализированных постов
        """
        if not self.reddit:
            self.logger.error("Reddit клиент не инициализирован", category='social')
            return []
        
        try:
            subreddit = self.reddit.subreddit(subreddit_name)
            
            # Получаем посты
            if sort_by == 'hot':
                posts = subreddit.hot(limit=limit)
            elif sort_by == 'new':
                posts = subreddit.new(limit=limit)
            elif sort_by == 'top':
                posts = subreddit.top(limit=limit, time_filter='day')
            elif sort_by == 'rising':
                posts = subreddit.rising(limit=limit)
            else:
                posts = subreddit.hot(limit=limit)
            
            # Анализируем посты
            results = []
            for post in posts:
                analysis = await self.analyze_post(post)
                if analysis:
                    results.append(analysis)
                
                # Анализируем топ комментарии для важных постов
                if post.score > 100 and post.num_comments > 20:
                    post.comments.replace_more(limit=0)
                    for comment in post.comments[:10]:
                        comment_analysis = await self.analyze_comment(comment)
                        if comment_analysis:
                            results.append(comment_analysis)
            
            self.logger.info(
                f"Проанализировано {len(results)} элементов из r/{subreddit_name}",
                category='social'
            )
            
            return results
            
        except Exception as e:
            self.logger.error(
                f"Ошибка мониторинга r/{subreddit_name}: {e}",
                category='social'
            )
            return []
    
    async def monitor_all_subreddits(self) -> List[Dict[str, Any]]:
        """Мониторит все ключевые сабреддиты"""
        all_results = []
        
        for subreddit_name in self.KEY_SUBREDDITS:
            try:
                # Для спекулятивных сабреддитов смотрим new
                if self.KEY_SUBREDDITS[subreddit_name]['category'] == 'speculation':
                    results = await self.monitor_subreddit(subreddit_name, 'new', 15)
                else:
                    results = await self.monitor_subreddit(subreddit_name, 'hot', 20)
                
                all_results.extend(results)
                
                # Задержка между запросами
                await asyncio.sleep(2)
                
            except Exception as e:
                self.logger.error(
                    f"Ошибка мониторинга r/{subreddit_name}: {e}",
                    category='social'
                )
        
        return all_results
    
    async def search_posts(self, 
                         query: str,
                         subreddit: str = 'all',
                         time_filter: str = 'day',
                         limit: int = 100) -> List[Dict[str, Any]]:
        """
        Поиск постов по запросу
        
        Args:
            query: Поисковый запрос
            subreddit: Сабреддит или 'all'
            time_filter: Временной фильтр (hour, day, week, month, year, all)
            limit: Максимум результатов
            
        Returns:
            Список проанализированных постов
        """
        if not self.reddit:
            return []
        
        try:
            if subreddit == 'all':
                search_sub = self.reddit.subreddit('all')
            else:
                search_sub = self.reddit.subreddit(subreddit)
            
            # Поиск
            posts = search_sub.search(query, time_filter=time_filter, limit=limit)
            
            # Анализ
            results = []
            for post in posts:
                analysis = await self.analyze_post(post)
                if analysis:
                    results.append(analysis)
            
            return results
            
        except Exception as e:
            self.logger.error(
                f"Ошибка поиска: {e}",
                category='social'
            )
            return []
    
    async def get_trending_cryptos(self) -> Dict[str, Any]:
        """Определяет трендовые криптовалюты на Reddit"""
        # Мониторим горячие посты
        results = await self.monitor_all_subreddits()
        
        # Подсчитываем упоминания
        crypto_mentions = defaultdict(int)
        crypto_sentiment = defaultdict(list)
        
        for result in results:
            cryptos = result.get('mentioned_cryptos', [])
            sentiment_score = result['sentiment']['compound']
            influence = result.get('influence_score', 1)
            
            for crypto in cryptos:
                crypto_mentions[crypto] += influence
                crypto_sentiment[crypto].append(sentiment_score)
        
        # Сортируем по популярности
        trending = []
        for crypto, mentions in crypto_mentions.items():
            if mentions > 1:  # Минимум 2 упоминания
                sentiments = crypto_sentiment[crypto]
                avg_sentiment = np.mean(sentiments) if sentiments else 0
                
                trending.append({
                    'symbol': crypto,
                    'mentions_score': round(mentions, 2),
                    'avg_sentiment': round(avg_sentiment, 3),
                    'posts_count': len([r for r in results if crypto in r.get('mentioned_cryptos', [])])
                })
        
        # Сортируем по score
        trending.sort(key=lambda x: x['mentions_score'], reverse=True)
        
        return {
            'trending_cryptos': trending[:10],
            'total_posts_analyzed': len(results),
            'timestamp': datetime.utcnow()
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Получает статистику работы монитора"""
        return {
            'posts_analyzed': self.stats['posts_analyzed'],
            'signals': {
                'buy': self.stats.get('signal_buy', 0),
                'sell': self.stats.get('signal_sell', 0),
                'neutral': self.stats.get('signal_neutral', 0),
                'pump_dump_warning': self.stats.get('signal_pump_dump_warning', 0),
                'low_quality': self.stats.get('signal_low_quality', 0)
            },
            'cache_size': len(self.post_cache),
            'processed_posts': len(self.processed_posts),
            'processed_comments': len(self.processed_comments)
        }


# Создаем глобальный экземпляр
reddit_monitor = RedditMonitor()