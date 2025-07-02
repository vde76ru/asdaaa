"""
Сборщик новостей из различных источников
Файл: src/analysis/news/news_collector.py
"""
import asyncio
import aiohttp
import feedparser
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
import json
import re
from bs4 import BeautifulSoup
from urllib.parse import urlparse

from sqlalchemy.orm import Session
from ...core.database import SessionLocal
from ...core.models import NewsAnalysis
from ...logging.smart_logger import SmartLogger

logger = SmartLogger(__name__)


class NewsSource:
    """Базовый класс для источников новостей"""
    
    def __init__(self, name: str, url: str, category: str = 'general'):
        self.name = name
        self.url = url
        self.category = category
        self.last_fetch = None
        self.fetch_interval = 300  # 5 минут
    
    async def fetch(self) -> List[Dict[str, Any]]:
        """Получает новости из источника"""
        raise NotImplementedError


class RSSNewsSource(NewsSource):
    """Источник новостей через RSS"""
    
    async def fetch(self) -> List[Dict[str, Any]]:
        """Получает новости из RSS фида"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.url, timeout=30) as response:
                    content = await response.text()
            
            feed = feedparser.parse(content)
            news_items = []
            
            for entry in feed.entries[:20]:  # Берем последние 20 новостей
                try:
                    # Парсим дату
                    published = None
                    if hasattr(entry, 'published_parsed'):
                        published = datetime.fromtimestamp(
                            entry.published_parsed.timestamp(),
                            tz=timezone.utc
                        )
                    elif hasattr(entry, 'updated_parsed'):
                        published = datetime.fromtimestamp(
                            entry.updated_parsed.timestamp(),
                            tz=timezone.utc
                        )
                    
                    # Извлекаем контент
                    content = ''
                    if hasattr(entry, 'summary'):
                        content = entry.summary
                    elif hasattr(entry, 'description'):
                        content = entry.description
                    
                    # Чистим HTML
                    content = BeautifulSoup(content, 'html.parser').get_text()
                    content = re.sub(r'\s+', ' ', content).strip()
                    
                    news_item = {
                        'source': self.name,
                        'url': entry.get('link', ''),
                        'title': entry.get('title', ''),
                        'content': content[:1000],  # Ограничиваем длину
                        'published_at': published,
                        'category': self.category,
                        'tags': [tag.term for tag in entry.get('tags', [])]
                    }
                    
                    news_items.append(news_item)
                    
                except Exception as e:
                    logger.error(
                        f"Ошибка парсинга новости из {self.name}",
                        category='news',
                        error=str(e)
                    )
            
            logger.info(
                f"Получено {len(news_items)} новостей из {self.name}",
                category='news',
                source=self.name
            )
            
            return news_items
            
        except Exception as e:
            logger.error(
                f"Ошибка получения новостей из {self.name}",
                category='news',
                source=self.name,
                error=str(e)
            )
            return []


class APINewsSource(NewsSource):
    """Источник новостей через API"""
    
    def __init__(self, name: str, base_url: str, api_key: str, category: str = 'general'):
        super().__init__(name, base_url, category)
        self.api_key = api_key
        self.headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
    
    async def fetch(self) -> List[Dict[str, Any]]:
        """Получает новости через API"""
        try:
            params = {
                'category': 'cryptocurrency',
                'language': 'en',
                'sortBy': 'publishedAt',
                'pageSize': 20
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.url,
                    headers=self.headers,
                    params=params,
                    timeout=30
                ) as response:
                    data = await response.json()
            
            news_items = []
            articles = data.get('articles', [])
            
            for article in articles:
                news_item = {
                    'source': self.name,
                    'url': article.get('url', ''),
                    'title': article.get('title', ''),
                    'content': article.get('description', ''),
                    'published_at': datetime.fromisoformat(
                        article.get('publishedAt', '').replace('Z', '+00:00')
                    ),
                    'category': self.category,
                    'author': article.get('author', ''),
                    'image_url': article.get('urlToImage', '')
                }
                
                news_items.append(news_item)
            
            return news_items
            
        except Exception as e:
            logger.error(
                f"Ошибка API запроса к {self.name}",
                category='news',
                source=self.name,
                error=str(e)
            )
            return []


class NewsCollector:
    """Основной сборщик новостей"""
    
    def __init__(self):
        self.sources = self._initialize_sources()
        self.running = False
        self.collection_task = None
        self.cache = {}
        self.cache_ttl = 300  # 5 минут
    
    def _initialize_sources(self) -> List[NewsSource]:
        """Инициализирует источники новостей"""
        sources = [
            # RSS источники
            RSSNewsSource(
                'CoinDesk',
                'https://www.coindesk.com/arc/outboundfeeds/rss/',
                'market'
            ),
            RSSNewsSource(
                'CryptoNews',
                'https://cryptonews.com/news/feed/',
                'general'
            ),
            RSSNewsSource(
                'Bitcoin.com',
                'https://news.bitcoin.com/feed/',
                'bitcoin'
            ),
            RSSNewsSource(
                'Cointelegraph',
                'https://cointelegraph.com/rss',
                'market'
            ),
            RSSNewsSource(
                'TheBlock',
                'https://www.theblockcrypto.com/rss.xml',
                'analysis'
            ),
            RSSNewsSource(
                'Decrypt',
                'https://decrypt.co/feed',
                'general'
            ),
            RSSNewsSource(
                'CryptoSlate',
                'https://cryptoslate.com/feed/',
                'market'
            ),
            # Можно добавить API источники если есть ключи
        ]
        
        return sources
    
    async def start(self):
        """Запускает сборщик новостей"""
        self.running = True
        self.collection_task = asyncio.create_task(self._collection_loop())
        logger.info("Сборщик новостей запущен", category='news')
    
    async def stop(self):
        """Останавливает сборщик"""
        self.running = False
        if self.collection_task:
            self.collection_task.cancel()
            try:
                await self.collection_task
            except asyncio.CancelledError:
                pass
        logger.info("Сборщик новостей остановлен", category='news')
    
    async def _collection_loop(self):
        """Основной цикл сбора новостей"""
        while self.running:
            try:
                await self.collect_all_news()
                await asyncio.sleep(300)  # Каждые 5 минут
            except Exception as e:
                logger.error(
                    "Ошибка в цикле сбора новостей",
                    category='news',
                    error=str(e)
                )
                await asyncio.sleep(60)
    
    async def collect_all_news(self) -> List[Dict[str, Any]]:
        """Собирает новости из всех источников"""
        all_news = []
        tasks = []
        
        # Запускаем сбор параллельно
        for source in self.sources:
            if self._should_fetch(source):
                tasks.append(self._fetch_from_source(source))
        
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, list):
                    all_news.extend(result)
                elif isinstance(result, Exception):
                    logger.error(
                        "Ошибка сбора новостей",
                        category='news',
                        error=str(result)
                    )
        
        # Фильтруем дубликаты
        unique_news = self._filter_duplicates(all_news)
        
        # Сохраняем в БД
        if unique_news:
            await self._save_news(unique_news)
        
        logger.info(
            f"Собрано {len(unique_news)} уникальных новостей",
            category='news',
            total_collected=len(all_news),
            unique=len(unique_news)
        )
        
        return unique_news
    
    def _should_fetch(self, source: NewsSource) -> bool:
        """Проверяет, нужно ли обновить источник"""
        if not source.last_fetch:
            return True
        
        elapsed = (datetime.now() - source.last_fetch).total_seconds()
        return elapsed >= source.fetch_interval
    
    async def _fetch_from_source(self, source: NewsSource) -> List[Dict[str, Any]]:
        """Получает новости из источника с кешированием"""
        cache_key = f"{source.name}:{source.url}"
        
        # Проверяем кеш
        if cache_key in self.cache:
            cached_data, cached_time = self.cache[cache_key]
            if (datetime.now() - cached_time).total_seconds() < self.cache_ttl:
                return cached_data
        
        # Получаем новые данные
        news = await source.fetch()
        source.last_fetch = datetime.now()
        
        # Кешируем
        self.cache[cache_key] = (news, datetime.now())
        
        return news
    
    def _filter_duplicates(self, news_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Фильтрует дубликаты новостей"""
        seen_titles = set()
        seen_urls = set()
        unique_news = []
        
        for item in news_items:
            # Нормализуем заголовок
            title_normalized = re.sub(r'\s+', ' ', item['title'].lower().strip())
            
            # Проверяем дубликаты
            if title_normalized not in seen_titles and item['url'] not in seen_urls:
                seen_titles.add(title_normalized)
                seen_urls.add(item['url'])
                unique_news.append(item)
        
        return unique_news
    
    async def _save_news(self, news_items: List[Dict[str, Any]]):
        """Сохраняет новости в БД"""
        db = SessionLocal()
        try:
            for item in news_items:
                # Проверяем, нет ли уже такой новости
                existing = db.query(NewsAnalysis).filter(
                    NewsAnalysis.url == item['url']
                ).first()
                
                if not existing:
                    # Создаем запись
                    news_record = NewsAnalysis(
                        source=item['source'],
                        url=item['url'],
                        title=item['title'],
                        content=item.get('content', ''),
                        published_at=item.get('published_at'),
                        # Анализ будет добавлен позже NLPAnalyzer
                        sentiment_score=None,
                        impact_score=None,
                        affected_coins=None
                    )
                    
                    db.add(news_record)
            
            db.commit()
            
        except Exception as e:
            db.rollback()
            logger.error(
                "Ошибка сохранения новостей в БД",
                category='news',
                error=str(e)
            )
        finally:
            db.close()
    
    async def get_recent_news(self, 
                            hours: int = 24, 
                            category: Optional[str] = None,
                            analyzed_only: bool = False) -> List[NewsAnalysis]:
        """Получает последние новости"""
        db = SessionLocal()
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            
            query = db.query(NewsAnalysis).filter(
                NewsAnalysis.published_at >= cutoff_time
            )
            
            if category:
                query = query.filter(NewsAnalysis.source.like(f'%{category}%'))
            
            if analyzed_only:
                query = query.filter(NewsAnalysis.sentiment_score.isnot(None))
            
            news = query.order_by(NewsAnalysis.published_at.desc()).all()
            
            return news
            
        finally:
            db.close()
    
    async def get_news_by_symbol(self, symbol: str, hours: int = 24) -> List[NewsAnalysis]:
        """Получает новости по конкретной монете"""
        db = SessionLocal()
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            
            # Ищем упоминания символа в заголовке или контенте
            news = db.query(NewsAnalysis).filter(
                and_(
                    NewsAnalysis.published_at >= cutoff_time,
                    or_(
                        NewsAnalysis.title.like(f'%{symbol}%'),
                        NewsAnalysis.content.like(f'%{symbol}%'),
                        NewsAnalysis.affected_coins.like(f'%"{symbol}"%')
                    )
                )
            ).order_by(NewsAnalysis.published_at.desc()).all()
            
            return news
            
        finally:
            db.close()
    
    def extract_mentioned_coins(self, text: str) -> List[str]:
        """Извлекает упоминания криптовалют из текста"""
        # Список популярных криптовалют
        crypto_symbols = [
            'BTC', 'ETH', 'BNB', 'XRP', 'ADA', 'SOL', 'DOT', 'DOGE', 
            'AVAX', 'LUNA', 'SHIB', 'MATIC', 'UNI', 'LINK', 'ATOM',
            'LTC', 'NEAR', 'ALGO', 'BCH', 'TRX', 'XLM', 'MANA', 'AXS',
            'VET', 'FIL', 'SAND', 'THETA', 'FTM', 'HBAR', 'EGLD', 'XTZ'
        ]
        
        crypto_names = {
            'bitcoin': 'BTC', 'ethereum': 'ETH', 'binance': 'BNB',
            'ripple': 'XRP', 'cardano': 'ADA', 'solana': 'SOL',
            'polkadot': 'DOT', 'dogecoin': 'DOGE', 'avalanche': 'AVAX',
            'polygon': 'MATIC', 'chainlink': 'LINK', 'uniswap': 'UNI',
            'litecoin': 'LTC', 'cosmos': 'ATOM'
        }
        
        mentioned = set()
        text_lower = text.lower()
        
        # Ищем символы
        for symbol in crypto_symbols:
            # Ищем как отдельное слово
            if re.search(rf'\b{symbol}\b', text, re.IGNORECASE):
                mentioned.add(symbol)
        
        # Ищем названия
        for name, symbol in crypto_names.items():
            if name in text_lower:
                mentioned.add(symbol)
        
        return list(mentioned)


# Создаем глобальный экземпляр
news_collector = NewsCollector()