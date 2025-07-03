"""
Извлечение торговых сигналов из социальных сетей
"""
import re
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import numpy as np
from collections import defaultdict

from ...logging.smart_logger import SmartLogger
from ...core.database import SessionLocal

from .twitter_monitor import twitter_monitor  # ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР
from .reddit_monitor import reddit_monitor    # ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР

logger = SmartLogger(__name__)


class SocialSignalExtractor:
    """Извлекает и анализирует торговые сигналы из соцсетей"""
    
    # Паттерны для поиска сигналов
    SIGNAL_PATTERNS = {
        'buy': [
            r'(?i)\b(buy|long|купить|лонг)\s+(\w+)',
            r'(?i)(\w+)\s+(to the moon|🚀|📈)',
            r'(?i)(\w+)\s+(bullish|бычий)',
            r'(?i)(accumulate|накапливать)\s+(\w+)'
        ],
        'sell': [
            r'(?i)\b(sell|short|продать|шорт)\s+(\w+)',
            r'(?i)(\w+)\s+(crash|dump|📉)',
            r'(?i)(\w+)\s+(bearish|медвежий)',
            r'(?i)(exit|выход)\s+(\w+)'
        ],
        'price_target': [
            r'(?i)(\w+)\s+(?:target|цель)\s*[:=]?\s*\$?(\d+\.?\d*)',
            r'(?i)(\w+)\s+to\s+\$?(\d+\.?\d*)'
        ]
    }
    
    # Криптовалюты для отслеживания
    CRYPTO_SYMBOLS = {
        'BTC': ['bitcoin', 'btc', 'биткоин'],
        'ETH': ['ethereum', 'eth', 'эфир', 'эфириум'],
        'BNB': ['binance', 'bnb', 'бинанс'],
        'SOL': ['solana', 'sol', 'солана'],
        'XRP': ['ripple', 'xrp', 'рипл'],
        # Добавьте больше по необходимости
    }
    
    def __init__(self):
        self.twitter_monitor = twitter_monitor    # НЕ СОЗДАЕМ НОВЫЙ!
        self.reddit_monitor = reddit_monitor      # НЕ СОЗДАЕМ НОВЫЙ!
        self.signal_cache = defaultdict(list)
        self.influencer_scores = {}
        
    async def get_sentiment(self, symbol: str) -> float:
        """Получает общий sentiment для символа"""
        # Получаем последние посты
        twitter_posts = await self.twitter_monitor.get_recent_posts(symbol, hours=4)
        reddit_posts = await self.reddit_monitor.get_recent_posts(symbol, hours=4)
        
        all_posts = twitter_posts + reddit_posts
        
        if not all_posts:
            return 0.0
        
        # Взвешенный sentiment
        total_sentiment = 0
        total_weight = 0
        
        for post in all_posts:
            weight = self._calculate_post_weight(post)
            sentiment = post.get('sentiment', 0)
            
            total_sentiment += sentiment * weight
            total_weight += weight
        
        if total_weight == 0:
            return 0.0
        
        return total_sentiment / total_weight
    
    async def extract_signals(self, timeframe_hours: int = 1) -> List[Dict]:
        """Извлекает торговые сигналы за период"""
        signals = []
        
        # Получаем посты
        twitter_posts = await self.twitter_monitor.get_recent_posts(hours=timeframe_hours)
        reddit_posts = await self.reddit_monitor.get_recent_posts(hours=timeframe_hours)
        
        # Извлекаем сигналы из каждого поста
        for post in twitter_posts + reddit_posts:
            extracted = self._extract_signals_from_post(post)
            signals.extend(extracted)
        
        # Агрегируем и фильтруем
        aggregated_signals = self._aggregate_signals(signals)
        
        # Оцениваем качество
        quality_signals = []
        for signal in aggregated_signals:
            quality = self._evaluate_signal_quality(signal)
            if quality > 0.6:
                signal['quality_score'] = quality
                quality_signals.append(signal)
        
        logger.info(
            f"Извлечено сигналов: {len(quality_signals)} из {len(signals)} сырых",
            category='social',
            quality_threshold=0.6
        )
        
        return quality_signals
    
    def _extract_signals_from_post(self, post: Dict) -> List[Dict]:
        """Извлекает сигналы из одного поста"""
        signals = []
        text = post.get('content', '')
        
        # Ищем паттерны покупки
        for pattern in self.SIGNAL_PATTERNS['buy']:
            matches = re.findall(pattern, text)
            for match in matches:
                symbol = self._normalize_symbol(match[-1] if isinstance(match, tuple) else match)
                if symbol:
                    signals.append({
                        'type': 'buy',
                        'symbol': symbol,
                        'source': post['platform'],
                        'author': post['author'],
                        'timestamp': post['created_at'],
                        'text': text[:200],
                        'engagement': post.get('engagement_score', 0),
                        'author_followers': post.get('author_followers', 0)
                    })
        
        # Ищем паттерны продажи
        for pattern in self.SIGNAL_PATTERNS['sell']:
            matches = re.findall(pattern, text)
            for match in matches:
                symbol = self._normalize_symbol(match[-1] if isinstance(match, tuple) else match)
                if symbol:
                    signals.append({
                        'type': 'sell',
                        'symbol': symbol,
                        'source': post['platform'],
                        'author': post['author'],
                        'timestamp': post['created_at'],
                        'text': text[:200],
                        'engagement': post.get('engagement_score', 0),
                        'author_followers': post.get('author_followers', 0)
                    })
        
        # Ищем ценовые цели
        for pattern in self.SIGNAL_PATTERNS['price_target']:
            matches = re.findall(pattern, text)
            for match in matches:
                symbol = self._normalize_symbol(match[0])
                if symbol:
                    try:
                        target_price = float(match[1])
                        signals.append({
                            'type': 'price_target',
                            'symbol': symbol,
                            'target': target_price,
                            'source': post['platform'],
                            'author': post['author'],
                            'timestamp': post['created_at'],
                            'text': text[:200]
                        })
                    except ValueError:
                        pass
        
        return signals
    
    def _normalize_symbol(self, text: str) -> Optional[str]:
        """Нормализует символ криптовалюты"""
        text = text.upper().strip()
        
        # Прямое совпадение
        if text in self.CRYPTO_SYMBOLS:
            return text
        
        # Поиск по алиасам
        for symbol, aliases in self.CRYPTO_SYMBOLS.items():
            if text.lower() in aliases:
                return symbol
        
        # Проверка на валидный тикер (3-5 букв)
        if re.match(r'^[A-Z]{3,5}$', text):
            return text
        
        return None
    
    def _aggregate_signals(self, signals: List[Dict]) -> List[Dict]:
        """Агрегирует похожие сигналы"""
        aggregated = defaultdict(lambda: {
            'count': 0,
            'buy_count': 0,
            'sell_count': 0,
            'authors': set(),
            'sources': defaultdict(int),
            'total_engagement': 0,
            'total_followers': 0,
            'timestamps': []
        })
        
        for signal in signals:
            symbol = signal['symbol']
            agg = aggregated[symbol]
            
            agg['count'] += 1
            if signal['type'] == 'buy':
                agg['buy_count'] += 1
            elif signal['type'] == 'sell':
                agg['sell_count'] += 1
            
            agg['authors'].add(signal['author'])
            agg['sources'][signal['source']] += 1
            agg['total_engagement'] += signal.get('engagement', 0)
            agg['total_followers'] += signal.get('author_followers', 0)
            agg['timestamps'].append(signal['timestamp'])
        
        # Преобразуем в список сигналов
        result = []
        for symbol, data in aggregated.items():
            # Определяем направление
            if data['buy_count'] > data['sell_count'] * 1.5:
                direction = 'buy'
                confidence = data['buy_count'] / data['count']
            elif data['sell_count'] > data['buy_count'] * 1.5:
                direction = 'sell'
                confidence = data['sell_count'] / data['count']
            else:
                continue  # Неопределенный сигнал
            
            result.append({
                'symbol': symbol,
                'direction': direction,
                'confidence': confidence,
                'mentions': data['count'],
                'unique_authors': len(data['authors']),
                'sources': dict(data['sources']),
                'avg_engagement': data['total_engagement'] / data['count'],
                'avg_followers': data['total_followers'] / data['count'],
                'first_mention': min(data['timestamps']),
                'last_mention': max(data['timestamps'])
            })
        
        return result
    
    def _evaluate_signal_quality(self, signal: Dict) -> float:
        """Оценивает качество сигнала"""
        score = 0.5  # Базовый счет
        
        # Факторы повышения качества
        if signal['mentions'] > 10:
            score += 0.1
        if signal['unique_authors'] > 5:
            score += 0.1
        if signal['avg_followers'] > 10000:
            score += 0.15
        if signal['avg_engagement'] > 100:
            score += 0.1
        
        # Проверка на pump & dump признаки
        time_span = (signal['last_mention'] - signal['first_mention']).total_seconds() / 3600
        mention_rate = signal['mentions'] / max(time_span, 0.1)
        
        if mention_rate > 50:  # Слишком много упоминаний за короткое время
            score -= 0.3
        
        # Диверсификация источников
        source_diversity = len(signal['sources']) / signal['mentions']
        score += source_diversity * 0.1
        
        # Учет истории автора (если есть)
        # TODO: добавить трекинг успешности предыдущих сигналов
        
        return min(max(score, 0), 1)
    
    def _calculate_post_weight(self, post: Dict) -> float:
        """Рассчитывает вес поста для sentiment анализа"""
        weight = 1.0
        
        # Вес на основе подписчиков
        followers = post.get('author_followers', 0)
        if followers > 100000:
            weight *= 2.0
        elif followers > 10000:
            weight *= 1.5
        elif followers < 1000:
            weight *= 0.5
        
        # Вес на основе вовлеченности
        engagement = post.get('engagement_score', 0)
        if engagement > 1000:
            weight *= 1.5
        elif engagement > 100:
            weight *= 1.2
        
        # Вес на основе платформы
        if post['platform'] == 'twitter' and post.get('is_verified'):
            weight *= 1.3
        
        # Свежесть
        age_hours = (datetime.utcnow() - post['created_at']).total_seconds() / 3600
        freshness_factor = max(0.5, 1 - age_hours / 24)
        weight *= freshness_factor
        
        return weight
    
    async def detect_pump_dump(self, symbol: str) -> Dict[str, Any]:
        """Обнаруживает признаки pump & dump"""
        # Получаем историю упоминаний
        history = await self._get_mention_history(symbol, hours=24)
        
        if len(history) < 10:
            return {'risk': 'low', 'confidence': 0.3}
        
        # Анализируем паттерн упоминаний
        timestamps = [h['timestamp'] for h in history]
        mention_counts = [h['count'] for h in history]
        
        # Вычисляем скорость роста упоминаний
        recent_rate = np.mean(mention_counts[-3:])
        historical_rate = np.mean(mention_counts[:-3])
        
        if historical_rate == 0:
            growth_rate = float('inf')
        else:
            growth_rate = recent_rate / historical_rate
        
        # Признаки pump & dump
        indicators = {
            'sudden_spike': growth_rate > 5,
            'concentrated_source': self._check_source_concentration(history),
            'new_accounts': self._check_new_accounts(history),
            'repetitive_content': self._check_content_similarity(history)
        }
        
        # Оценка риска
        risk_score = sum(1 for ind in indicators.values() if ind) / len(indicators)
        
        if risk_score > 0.7:
            risk_level = 'high'
        elif risk_score > 0.4:
            risk_level = 'medium'
        else:
            risk_level = 'low'
        
        return {
            'risk': risk_level,
            'confidence': min(len(history) / 100, 1),
            'growth_rate': growth_rate,
            'indicators': indicators
        }
    
    async def _get_mention_history(self, symbol: str, hours: int) -> List[Dict]:
        """Получает историю упоминаний символа"""
        # Здесь должен быть запрос к БД с агрегацией по часам
        # Временная заглушка
        return []
    
    def _check_source_concentration(self, history: List[Dict]) -> bool:
        """Проверяет концентрацию источников"""
        all_authors = []
        for h in history:
            all_authors.extend(h.get('authors', []))
        
        if not all_authors:
            return False
        
        # Если > 50% от одного автора - подозрительно
        author_counts = defaultdict(int)
        for author in all_authors:
            author_counts[author] += 1
        
        max_count = max(author_counts.values())
        return max_count / len(all_authors) > 0.5
    
    def _check_new_accounts(self, history: List[Dict]) -> bool:
        """Проверяет долю новых аккаунтов"""
        # Здесь должна быть проверка возраста аккаунтов
        # Временно возвращаем False
        return False
    
    def _check_content_similarity(self, history: List[Dict]) -> bool:
        """Проверяет похожесть контента"""
        # Здесь должен быть анализ схожести текстов
        # Временно возвращаем False
        return False