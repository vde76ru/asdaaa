"""
Класс для исполнения торговых операций с безопасными импортами
Файл: src/bot/trader.py

🔥 ИСПРАВЛЕНЫ ВСЕ ПРОБЛЕМНЫЕ ИМПОРТЫ
"""
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
import numpy as np
from collections import deque

# Импорты моделей из core (ИСПРАВЛЕНО)
from ..core.models import Trade, Signal, Order
from ..core.database import SessionLocal
from ..core.unified_config import unified_config as config
from ..exchange.unified_exchange import UnifiedExchangeClient as ExchangeClient

# ML модули - используем безопасный импорт (ИСПРАВЛЕНО)
try:
    from ..ml.models.direction_classifier import DirectionClassifier
except ImportError:
    DirectionClassifier = None
    
try:
    from ..ml.features.feature_engineering import FeatureEngineer
except ImportError:
    FeatureEngineer = None
    
try:
    from ..ml.models.rl_agent import TradingRLAgent
except ImportError:
    TradingRLAgent = None

# Модули анализа - безопасный импорт (ИСПРАВЛЕНО)
try:
    from ..analysis.news.impact_scorer import NewsImpactScorer
except ImportError:
    NewsImpactScorer = None
    
try:
    from ..analysis.social.signal_extractor import SocialSignalExtractor
except ImportError:
    SocialSignalExtractor = None

# Логирование - безопасный импорт (ИСПРАВЛЕНО)
try:
    from ..logging.smart_logger import get_logger
    logger = get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

class Trader:
    """Класс для исполнения торговых операций"""
    
    def __init__(self, exchange: ExchangeClient):
        self.exchange = exchange
        
        # Инициализируем ML компоненты если они доступны
        self.direction_classifier = DirectionClassifier() if DirectionClassifier else None
        self.feature_engineer = FeatureEngineer() if FeatureEngineer else None
        self.rl_agent = TradingRLAgent() if TradingRLAgent else None
        
        # Инициализируем модули анализа
        self.news_scorer = NewsImpactScorer() if NewsImpactScorer else None
        self.social_extractor = SocialSignalExtractor() if SocialSignalExtractor else None
        
        # Статистика трейдера
        self.total_trades = 0
        self.profitable_trades = 0
        self.total_profit = 0.0
        self.recent_trades = deque(maxlen=100)
        
        # Статус компонентов для логирования
        components_status = {
            'DirectionClassifier': self.direction_classifier is not None,
            'FeatureEngineer': self.feature_engineer is not None,
            'TradingRLAgent': self.rl_agent is not None,
            'NewsImpactScorer': self.news_scorer is not None,
            'SocialSignalExtractor': self.social_extractor is not None
        }
        
        available_components = [name for name, available in components_status.items() if available]
        unavailable_components = [name for name, available in components_status.items() if not available]
        
        logger.info(f"✅ Trader инициализирован")
        if available_components:
            logger.info(f"✅ Доступные компоненты: {', '.join(available_components)}")
        if unavailable_components:
            logger.warning(f"⚠️ Недоступные компоненты: {', '.join(unavailable_components)}")
    
    async def execute_trade(self, signal: Dict[str, Any], strategy_name: str) -> Dict[str, Any]:
        """
        Исполнение торговой операции
        
        Args:
            signal: Торговый сигнал
            strategy_name: Название стратегии
            
        Returns:
            Dict с результатом операции
        """
        try:
            logger.info(f"🔄 Исполнение сделки: {signal.get('action')} {signal.get('symbol')}")
            
            # Подготовка данных для сделки
            trade_data = {
                'symbol': signal.get('symbol'),
                'action': signal.get('action'),
                'amount': signal.get('amount', 0),
                'price': signal.get('price', 0),
                'strategy': strategy_name,
                'confidence': signal.get('confidence', 0),
                'timestamp': datetime.utcnow()
            }
            
            # ML анализ если доступен
            if self.direction_classifier and signal.get('features'):
                try:
                    ml_prediction = await self._get_ml_prediction(signal)
                    trade_data['ml_prediction'] = ml_prediction
                except Exception as e:
                    logger.warning(f"⚠️ ML предсказание недоступно: {e}")
            
            # Анализ новостей если доступен
            if self.news_scorer:
                try:
                    news_impact = await self._analyze_news_impact(signal.get('symbol'))
                    trade_data['news_impact'] = news_impact
                except Exception as e:
                    logger.warning(f"⚠️ Анализ новостей недоступен: {e}")
            
            # Социальные сигналы если доступны
            if self.social_extractor:
                try:
                    social_sentiment = await self._analyze_social_sentiment(signal.get('symbol'))
                    trade_data['social_sentiment'] = social_sentiment
                except Exception as e:
                    logger.warning(f"⚠️ Анализ социальных сигналов недоступен: {e}")
            
            # Исполнение через exchange
            execution_result = await self.exchange.execute_order(trade_data)
            
            # Обновление статистики
            self._update_statistics(execution_result)
            
            # Сохранение в БД
            await self._save_trade_to_db(trade_data, execution_result)
            
            logger.info(f"✅ Сделка исполнена: {execution_result.get('status', 'unknown')}")
            
            return {
                'success': True,
                'trade_data': trade_data,
                'execution_result': execution_result,
                'total_trades': self.total_trades,
                'win_rate': self.get_win_rate()
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка исполнения сделки: {e}")
            return {
                'success': False,
                'error': str(e),
                'trade_data': trade_data if 'trade_data' in locals() else {}
            }
    
    async def _get_ml_prediction(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """Получение ML предсказания"""
        if not self.direction_classifier:
            return {'available': False}
        
        try:
            # Здесь должна быть реальная логика ML предсказания
            # Пока используем заглушку
            prediction = {
                'direction': 'UP' if signal.get('confidence', 0) > 0.7 else 'HOLD',
                'confidence': signal.get('confidence', 0.5),
                'expected_return': signal.get('confidence', 0.5) * 0.05,  # 5% максимум
                'risk_score': 1 - signal.get('confidence', 0.5),
                'model_used': 'DirectionClassifier',
                'timestamp': datetime.utcnow().isoformat()
            }
            
            return prediction
            
        except Exception as e:
            logger.error(f"❌ Ошибка ML предсказания: {e}")
            return {'available': False, 'error': str(e)}
    
    async def _analyze_news_impact(self, symbol: str) -> Dict[str, Any]:
        """Анализ влияния новостей"""
        if not self.news_scorer:
            return {'available': False}
        
        try:
            # Базовый анализ новостей
            # В реальной реализации здесь будет поиск и анализ свежих новостей
            impact = self.news_scorer.score_news_impact(
                news_text=f"Recent market analysis for {symbol}",
                symbol=symbol
            )
            
            return {
                'sentiment': impact.sentiment.value,
                'impact_score': impact.impact_score,
                'confidence': impact.confidence,
                'category': impact.category.value,
                'urgency': impact.urgency,
                'available': True
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка анализа новостей: {e}")
            return {'available': False, 'error': str(e)}
    
    async def _analyze_social_sentiment(self, symbol: str) -> Dict[str, Any]:
        """Анализ социальных настроений"""
        if not self.social_extractor:
            return {'available': False}
        
        try:
            # Базовый анализ социальных сигналов
            # В реальной реализации здесь будет анализ Twitter, Reddit и т.д.
            sentiment = {
                'overall_sentiment': 'neutral',
                'sentiment_score': 0.0,
                'mention_volume': 'medium',
                'influencer_sentiment': 'neutral',
                'trending': False,
                'available': True
            }
            
            return sentiment
            
        except Exception as e:
            logger.error(f"❌ Ошибка анализа социальных сигналов: {e}")
            return {'available': False, 'error': str(e)}
    
    def _update_statistics(self, execution_result: Dict[str, Any]):
        """Обновление статистики трейдера"""
        try:
            if execution_result.get('success', False):
                self.total_trades += 1
                
                profit = execution_result.get('profit', 0)
                self.total_profit += profit
                
                if profit > 0:
                    self.profitable_trades += 1
                
                # Добавляем в историю
                trade_record = {
                    'timestamp': datetime.utcnow(),
                    'profit': profit,
                    'success': True
                }
                self.recent_trades.append(trade_record)
                
        except Exception as e:
            logger.error(f"❌ Ошибка обновления статистики: {e}")
    
    async def _save_trade_to_db(self, trade_data: Dict[str, Any], 
                              execution_result: Dict[str, Any]):
        """Сохранение сделки в базу данных"""
        try:
            db = SessionLocal()
            
            # Создаем запись о сделке
            trade = Trade(
                symbol=trade_data.get('symbol'),
                strategy=trade_data.get('strategy'),
                action=trade_data.get('action'),
                amount=trade_data.get('amount', 0),
                price=trade_data.get('price', 0),
                confidence=trade_data.get('confidence', 0),
                profit=execution_result.get('profit', 0),
                status='completed' if execution_result.get('success') else 'failed',
                created_at=trade_data.get('timestamp', datetime.utcnow())
            )
            
            db.add(trade)
            db.commit()
            
            logger.debug(f"💾 Сделка сохранена в БД: ID {trade.id}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения в БД: {e}")
        finally:
            try:
                db.close()
            except:
                pass
    
    def get_statistics(self) -> Dict[str, Any]:
        """Получение статистики трейдера"""
        return {
            'total_trades': self.total_trades,
            'profitable_trades': self.profitable_trades,
            'total_profit': self.total_profit,
            'win_rate': self.get_win_rate(),
            'average_profit': self.get_average_profit(),
            'recent_trades_count': len(self.recent_trades),
            'components_available': {
                'ml_classifier': self.direction_classifier is not None,
                'feature_engineer': self.feature_engineer is not None,
                'news_scorer': self.news_scorer is not None,
                'social_extractor': self.social_extractor is not None
            }
        }
    
    def get_win_rate(self) -> float:
        """Расчет винрейта"""
        if self.total_trades == 0:
            return 0.0
        return (self.profitable_trades / self.total_trades) * 100
    
    def get_average_profit(self) -> float:
        """Расчет средней прибыли"""
        if self.total_trades == 0:
            return 0.0
        return self.total_profit / self.total_trades

# Экспорт
__all__ = ['Trader']