"""
Улучшенный исполнитель сделок с интеграцией ML
"""
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
import numpy as np

from ..core.models import Trade, Signal, Order
from ..core.database import SessionLocal
from ..ml.strategy_selector import MLStrategySelector
from ..ml.models.regressor import PriceLevelRegressor
from ..ml.models.reinforcement import TradingRLAgent
from ..ml.feature_engineering import FeatureEngineering
from ..analysis.news.impact_scorer import NewsImpactScorer
from ..analysis.social.signal_extractor import SocialSignalExtractor
from ..logging.smart_logger import get_logger

logger = SmartLogger(__name__)


class EnhancedRiskManager:
    """Продвинутый риск-менеджер с ML"""
    
    def __init__(self, max_risk_per_trade: float = 0.02, max_daily_risk: float = 0.06):
        self.max_risk_per_trade = max_risk_per_trade
        self.max_daily_risk = max_daily_risk
        self.daily_losses = {}
        self.rl_agent = TradingRLAgent()
        
    async def calculate_position_size(self, signal: Dict, market_conditions: Dict, 
                                    ml_confidence: float, balance: float) -> float:
        """Динамический расчет размера позиции"""
        # Базовый размер на основе Kelly Criterion
        kelly_fraction = self._calculate_kelly_fraction(
            win_rate=market_conditions.get('historical_win_rate', 0.5),
            avg_win=market_conditions.get('avg_win', 1.5),
            avg_loss=market_conditions.get('avg_loss', 1.0)
        )
        
        # Корректировка на основе ML уверенности
        ml_adjustment = ml_confidence * 1.5 if ml_confidence > 0.7 else ml_confidence * 0.8
        
        # Корректировка на основе рыночных условий
        volatility_adjustment = 1.0 / (1.0 + market_conditions.get('volatility', 0.02))
        
        # Корректировка на основе новостей
        news_impact = market_conditions.get('news_impact', 0)
        news_adjustment = 1.2 if news_impact > 0 else 0.8 if news_impact < 0 else 1.0
        
        # Финальный размер позиции
        position_fraction = kelly_fraction * ml_adjustment * volatility_adjustment * news_adjustment
        position_fraction = min(position_fraction, self.max_risk_per_trade)
        
        # Проверка дневного лимита
        today = datetime.utcnow().date()
        daily_loss = self.daily_losses.get(today, 0)
        remaining_risk = self.max_daily_risk - abs(daily_loss)
        
        if remaining_risk <= 0:
            logger.warning(
                "Достигнут дневной лимит риска",
                category='risk',
                daily_loss=daily_loss,
                limit=self.max_daily_risk
            )
            return 0
        
        position_fraction = min(position_fraction, remaining_risk)
        position_size = balance * position_fraction
        
        logger.info(
            f"Рассчитан размер позиции: ${position_size:.2f} ({position_fraction:.2%} от баланса)",
            category='risk',
            kelly_fraction=kelly_fraction,
            ml_confidence=ml_confidence,
            adjustments={
                'ml': ml_adjustment,
                'volatility': volatility_adjustment,
                'news': news_adjustment
            }
        )
        
        return position_size
    
    def _calculate_kelly_fraction(self, win_rate: float, avg_win: float, avg_loss: float) -> float:
        """Расчет оптимальной доли капитала по формуле Келли"""
        if avg_loss == 0:
            return 0
        
        # f = (p * b - q) / b
        # где p - вероятность выигрыша, q - вероятность проигрыша, b - отношение выигрыша к проигрышу
        b = avg_win / avg_loss
        f = (win_rate * b - (1 - win_rate)) / b
        
        # Используем долю Келли (обычно 25% для безопасности)
        return max(0, min(f * 0.25, 0.1))
    
    def update_daily_loss(self, loss: float):
        """Обновляет дневные потери"""
        today = datetime.utcnow().date()
        self.daily_losses[today] = self.daily_losses.get(today, 0) + loss


class DynamicLevelCalculator:
    """Динамический расчет уровней TP/SL с ML"""
    
    def __init__(self):
        self.regressor = PriceLevelRegressor()
        self.feature_eng = FeatureEngineering()
        
    async def calculate_levels(self, signal: Dict, market_data: Dict, 
                             ml_predictions: Dict) -> Tuple[float, float]:
        """Рассчитывает адаптивные уровни TP и SL"""
        # Получаем предсказания регрессора
        features = self.feature_eng.create_features(market_data)
        tp_distance, sl_distance = self.regressor.predict_levels(features)
        
        # Корректировка на основе волатильности
        atr = market_data.get('atr', 0)
        volatility_factor = 1 + (atr / market_data['price']) * 2
        
        # Корректировка на основе силы тренда
        trend_strength = ml_predictions.get('trend_strength', 0.5)
        trend_factor = 1.5 if trend_strength > 0.7 else 0.8 if trend_strength < 0.3 else 1.0
        
        # Корректировка на основе поддержки/сопротивления
        support_resistance = self._find_support_resistance_levels(market_data)
        
        current_price = market_data['price']
        
        if signal['side'] == 'BUY':
            # Take Profit
            tp_base = current_price * (1 + tp_distance)
            tp = self._adjust_to_resistance(tp_base, support_resistance['resistance'])
            tp *= trend_factor * volatility_factor
            
            # Stop Loss
            sl_base = current_price * (1 - sl_distance)
            sl = self._adjust_to_support(sl_base, support_resistance['support'])
            
        else:  # SELL
            # Take Profit
            tp_base = current_price * (1 - tp_distance)
            tp = self._adjust_to_support(tp_base, support_resistance['support'])
            tp *= trend_factor * volatility_factor
            
            # Stop Loss
            sl_base = current_price * (1 + sl_distance)
            sl = self._adjust_to_resistance(sl_base, support_resistance['resistance'])
        
        # Минимальное соотношение риск/прибыль 1:1.5
        risk = abs(current_price - sl)
        reward = abs(tp - current_price)
        
        if reward / risk < 1.5:
            if signal['side'] == 'BUY':
                tp = current_price + risk * 1.5
            else:
                tp = current_price - risk * 1.5
        
        logger.info(
            f"Рассчитаны уровни TP: {tp:.8f}, SL: {sl:.8f}",
            category='trade',
            symbol=market_data['symbol'],
            risk_reward_ratio=reward/risk,
            adjustments={
                'volatility_factor': volatility_factor,
                'trend_factor': trend_factor
            }
        )
        
        return tp, sl
    
    def _find_support_resistance_levels(self, market_data: Dict) -> Dict[str, List[float]]:
        """Находит уровни поддержки и сопротивления"""
        candles = market_data.get('candles', [])
        if not candles:
            return {'support': [], 'resistance': []}
        
        # Простой алгоритм поиска локальных экстремумов
        highs = [c['high'] for c in candles[-100:]]
        lows = [c['low'] for c in candles[-100:]]
        
        resistance_levels = []
        support_levels = []
        
        # Поиск локальных максимумов и минимумов
        for i in range(2, len(highs) - 2):
            # Сопротивление
            if highs[i] > highs[i-1] and highs[i] > highs[i-2] and \
               highs[i] > highs[i+1] and highs[i] > highs[i+2]:
                resistance_levels.append(highs[i])
            
            # Поддержка
            if lows[i] < lows[i-1] and lows[i] < lows[i-2] and \
               lows[i] < lows[i+1] and lows[i] < lows[i+2]:
                support_levels.append(lows[i])
        
        return {
            'resistance': sorted(resistance_levels, reverse=True)[:3],
            'support': sorted(support_levels)[:3]
        }
    
    def _adjust_to_resistance(self, price: float, resistance_levels: List[float]) -> float:
        """Корректирует цену к ближайшему уровню сопротивления"""
        for level in resistance_levels:
            if level > price:
                # Ставим TP чуть ниже сопротивления
                return level * 0.998
        return price
    
    def _adjust_to_support(self, price: float, support_levels: List[float]) -> float:
        """Корректирует цену к ближайшему уровню поддержки"""
        for level in reversed(support_levels):
            if level < price:
                # Ставим TP чуть выше поддержки
                return level * 1.002
        return price


class SmartTradeExecutor:
    """Интеллектуальный исполнитель сделок с полной ML интеграцией"""
    
    def __init__(self, exchange_client, balance_manager):
        self.exchange = exchange_client
        self.balance_manager = balance_manager
        self.ml_selector = MLStrategySelector()
        self.risk_manager = EnhancedRiskManager()
        self.level_calculator = DynamicLevelCalculator()
        self.news_scorer = NewsImpactScorer()
        self.social_extractor = SocialSignalExtractor()
        self.rl_agent = TradingRLAgent()
        self.feature_eng = FeatureEngineering()
        
    async def execute_signal(self, signal: Signal) -> Optional[Trade]:
        """Исполняет торговый сигнал с ML валидацией"""
        try:
            # 1. Получаем рыночные данные
            market_data = await self._get_market_data(signal.symbol)
            
            # 2. ML валидация сигнала
            ml_validation = await self._validate_with_ml(signal, market_data)
            
            if not ml_validation['should_trade']:
                logger.info(
                    f"Сигнал отклонен ML валидацией",
                    category='signal',
                    symbol=signal.symbol,
                    reason=ml_validation['reason'],
                    confidence=ml_validation['confidence']
                )
                return None
            
            # 3. Анализ рыночных условий
            market_conditions = await self._analyze_market_conditions(signal.symbol)
            
            # 4. Проверка новостей и социальных сигналов
            external_signals = await self._check_external_signals(signal.symbol)
            
            if external_signals['risk_level'] == 'high':
                logger.warning(
                    f"Высокий риск из-за внешних факторов",
                    category='risk',
                    symbol=signal.symbol,
                    news_impact=external_signals['news_impact'],
                    social_sentiment=external_signals['social_sentiment']
                )
                return None
            
            # 5. Расчет размера позиции
            balance = await self.balance_manager.get_available_balance()
            position_size = await self.risk_manager.calculate_position_size(
                signal.to_dict(),
                market_conditions,
                ml_validation['confidence'],
                balance
            )
            
            if position_size <= 0:
                logger.warning(
                    "Нулевой размер позиции, пропускаем сигнал",
                    category='risk',
                    symbol=signal.symbol
                )
                return None
            
            # 6. Расчет уровней TP/SL
            tp, sl = await self.level_calculator.calculate_levels(
                signal.to_dict(),
                market_data,
                ml_validation['predictions']
            )
            
            # 7. Исполнение ордера
            order = await self._execute_order(
                symbol=signal.symbol,
                side=signal.action,
                quantity=position_size / market_data['price'],
                tp=tp,
                sl=sl
            )
            
            if not order:
                return None
            
            # 8. Создание записи о сделке
            trade = await self._create_trade_record(
                signal=signal,
                order=order,
                ml_data={
                    'confidence': ml_validation['confidence'],
                    'strategy': ml_validation['selected_strategy'],
                    'predictions': ml_validation['predictions'],
                    'market_conditions': market_conditions,
                    'external_signals': external_signals
                }
            )
            
            # 9. Обновление RL агента
            await self.rl_agent.record_action(
                state=market_data,
                action=signal.action,
                trade_id=trade.id
            )
            
            logger.trade_opened(
                symbol=trade.symbol,
                side=trade.side,
                quantity=trade.quantity,
                price=trade.entry_price,
                strategy=signal.strategy,
                trade_id=trade.id,
                ml_confidence=ml_validation['confidence']
            )
            
            return trade
            
        except Exception as e:
            logger.error(
                f"Ошибка исполнения сигнала: {str(e)}",
                category='trade',
                symbol=signal.symbol,
                error=str(e)
            )
            return None
    
    async def _validate_with_ml(self, signal: Signal, market_data: Dict) -> Dict:
        """ML валидация сигнала"""
        # Создаем признаки
        features = self.feature_eng.create_features(market_data)
        
        # Выбираем лучшую стратегию
        strategy_recommendation = await self.ml_selector.select_best_strategy(
            signal.symbol,
            market_data
        )
        
        # Проверяем соответствие
        if strategy_recommendation['best_strategy'] != signal.strategy:
            confidence_penalty = 0.3
        else:
            confidence_penalty = 0
        
        # Получаем предсказания
        predictions = await self.ml_selector.get_ml_predictions(features)
        
        # Финальная уверенность
        final_confidence = strategy_recommendation['confidence'] - confidence_penalty
        
        should_trade = (
            final_confidence > 0.6 and
            predictions['direction_confidence'] > 0.65 and
            strategy_recommendation['expected_return'] > 0.002  # 0.2%
        )
        
        return {
            'should_trade': should_trade,
            'confidence': final_confidence,
            'selected_strategy': strategy_recommendation['best_strategy'],
            'predictions': predictions,
            'reason': strategy_recommendation.get('reason', ''),
            'expected_return': strategy_recommendation['expected_return']
        }
    
    async def _analyze_market_conditions(self, symbol: str) -> Dict:
        """Анализирует текущие рыночные условия"""
        # Получаем исторические данные
        candles = await self.exchange.get_candles(symbol, '1h', limit=100)
        
        # Рассчитываем метрики
        closes = [c['close'] for c in candles]
        returns = np.diff(closes) / closes[:-1]
        
        volatility = np.std(returns) * np.sqrt(24)  # Дневная волатильность
        trend = (closes[-1] - closes[-20]) / closes[-20]  # 20-часовой тренд
        
        # Определяем состояние рынка
        if abs(trend) < 0.01:
            market_state = 'sideways'
        elif trend > 0.03:
            market_state = 'strong_uptrend'
        elif trend > 0:
            market_state = 'uptrend'
        elif trend < -0.03:
            market_state = 'strong_downtrend'
        else:
            market_state = 'downtrend'
        
        # Получаем историческую производительность
        db = SessionLocal()
        try:
            # Здесь бы запрос к strategy_performance таблице
            historical_stats = {
                'win_rate': 0.55,  # Заглушка - нужно из БД
                'avg_win': 0.015,
                'avg_loss': 0.01
            }
        finally:
            db.close()
        
        return {
            'volatility': volatility,
            'trend': trend,
            'market_state': market_state,
            'volume_24h': sum(c['volume'] for c in candles[-24:]),
            'atr': self._calculate_atr(candles),
            'historical_win_rate': historical_stats['win_rate'],
            'avg_win': historical_stats['avg_win'],
            'avg_loss': historical_stats['avg_loss']
        }
    
    async def _check_external_signals(self, symbol: str) -> Dict:
        """Проверяет новости и социальные сигналы"""
        # Анализ новостей
        news_impact = await self.news_scorer.get_current_impact(symbol)
        
        # Анализ социальных сетей
        social_sentiment = await self.social_extractor.get_sentiment(symbol)
        
        # Определяем уровень риска
        if news_impact < -0.5 or social_sentiment < -0.5:
            risk_level = 'high'
        elif news_impact < -0.2 or social_sentiment < -0.2:
            risk_level = 'medium'
        else:
            risk_level = 'low'
        
        return {
            'news_impact': news_impact,
            'social_sentiment': social_sentiment,
            'risk_level': risk_level,
            'combined_score': (news_impact + social_sentiment) / 2
        }
    
    async def _get_market_data(self, symbol: str) -> Dict:
        """Получает текущие рыночные данные"""
        ticker = await self.exchange.get_ticker(symbol)
        orderbook = await self.exchange.get_orderbook(symbol)
        candles = await self.exchange.get_candles(symbol, '1m', limit=100)
        
        return {
            'symbol': symbol,
            'price': ticker['last'],
            'bid': ticker['bid'],
            'ask': ticker['ask'],
            'volume_24h': ticker['volume'],
            'orderbook': orderbook,
            'candles': candles,
            'spread': (ticker['ask'] - ticker['bid']) / ticker['bid'],
            'atr': self._calculate_atr(candles)
        }
    
    def _calculate_atr(self, candles: List[Dict], period: int = 14) -> float:
        """Рассчитывает Average True Range"""
        if len(candles) < period:
            return 0
        
        true_ranges = []
        for i in range(1, len(candles)):
            high = candles[i]['high']
            low = candles[i]['low']
            prev_close = candles[i-1]['close']
            
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            true_ranges.append(tr)
        
        return np.mean(true_ranges[-period:])
    
    async def _execute_order(self, symbol: str, side: str, quantity: float, 
                           tp: float, sl: float) -> Optional[Order]:
        """Исполняет ордер на бирже"""
        try:
            # Основной ордер
            order = await self.exchange.create_order(
                symbol=symbol,
                type='market',
                side=side,
                amount=quantity
            )
            
            # OCO ордера для TP/SL
            if side == 'buy':
                await self.exchange.create_oco_order(
                    symbol=symbol,
                    side='sell',
                    amount=quantity,
                    price=tp,
                    stop_price=sl,
                    limit_price=sl * 0.995  # Проскальзывание
                )
            else:
                await self.exchange.create_oco_order(
                    symbol=symbol,
                    side='buy',
                    amount=quantity,
                    price=tp,
                    stop_price=sl,
                    limit_price=sl * 1.005
                )
            
            return order
            
        except Exception as e:
            logger.error(
                f"Ошибка исполнения ордера: {str(e)}",
                category='trade',
                symbol=symbol,
                side=side,
                quantity=quantity
            )
            return None
    
    async def _create_trade_record(self, signal: Signal, order: Order, 
                                 ml_data: Dict) -> Trade:
        """Создает запись о сделке в БД"""
        db = SessionLocal()
        try:
            trade = Trade(
                symbol=signal.symbol,
                side=signal.action,
                quantity=order['amount'],
                entry_price=order['price'],
                strategy=signal.strategy,
                signal_id=signal.id,
                status='open',
                ml_confidence=ml_data['confidence'],
                ml_predictions=ml_data['predictions'],
                market_conditions=ml_data['market_conditions'],
                created_at=datetime.utcnow()
            )
            
            db.add(trade)
            db.commit()
            db.refresh(trade)
            
            return trade
            
        finally:
            db.close()