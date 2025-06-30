"""
Новый файл: src/strategies/mean_reversion.py
===========================================
Стратегия возврата к средней (Mean Reversion Strategy)
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
import logging

try:
    from ta.momentum import RSIIndicator
    from ta.trend import EMAIndicator
    from ta.volatility import BollingerBands, AverageTrueRange
    TA_AVAILABLE = True
except ImportError:
    TA_AVAILABLE = False
    logging.warning("⚠️ TA-Lib не установлен, используем базовые вычисления")

from .base import BaseStrategy, TradingSignal

logger = logging.getLogger(__name__)

class MeanReversionStrategy(BaseStrategy):
    """
    Стратегия возврата к средней
    
    Логика:
    - Ищет отклонения цены от средних значений
    - Торгует против тренда в расчете на возврат к средней
    - Использует Bollinger Bands, RSI и отклонения от EMA
    - Лучше работает в боковых рынках
    """
    
    # Константы стратегии
    RSI_OVERSOLD = 25      # Более строгие уровни чем обычно
    RSI_OVERBOUGHT = 75
    BB_LOWER_THRESHOLD = 0.1   # Сильное отклонение к нижней полосе
    BB_UPPER_THRESHOLD = 0.9   # Сильное отклонение к верхней полосе
    PRICE_DEVIATION_THRESHOLD = 0.03  # 3% отклонение от EMA
    
    # Метаинформация
    STRATEGY_TYPE = 'mean_reversion'
    RISK_LEVEL = 'medium'
    TIMEFRAMES = ['1h', '4h', '1d']
    
    def __init__(self, strategy_name: str = "mean_reversion", config: Optional[Dict] = None):
        """Инициализация стратегии возврата к средней"""
        super().__init__(strategy_name, config)
        
        # Параметры из конфигурации
        self.bb_period = self.config.get('bb_period', 20)
        self.bb_std = self.config.get('bb_std', 2.0)
        self.rsi_period = self.config.get('rsi_period', 14)
        self.ema_period = self.config.get('ema_period', 50)
        self.min_confidence = self.config.get('min_confidence', 0.7)
        
        logger.info(f"✅ MeanReversionStrategy инициализирована: {self.name}")
        
    async def analyze(self, df: pd.DataFrame, symbol: str) -> TradingSignal:
        """Анализ для стратегии возврата к средней"""
        if not self.validate_dataframe(df):
            return TradingSignal('WAIT', 0, 0, reason='Недостаточно данных')
            
        try:
            # Рассчитываем индикаторы
            indicators = self._calculate_indicators(df)
            if not indicators:
                return TradingSignal('WAIT', 0, 0, reason='Ошибка расчета индикаторов')
                
            # Проверяем рыночные условия (боковой рынок лучше для mean reversion)
            market_condition = self._assess_market_condition(indicators, df)
            
            # Анализируем сигналы отклонения
            deviation_signals = self._analyze_deviations(indicators)
            
            # Принимаем решение
            return self._make_decision(deviation_signals, indicators, market_condition, df)
            
        except Exception as e:
            logger.error(f"Ошибка анализа mean reversion для {symbol}: {e}")
            return TradingSignal('WAIT', 0, 0, reason=f'Ошибка анализа: {e}')
    
    def _calculate_indicators(self, df: pd.DataFrame) -> Dict:
        """Расчет индикаторов для mean reversion"""
        try:
            indicators = {}
            current_price = float(df['close'].iloc[-1])
            indicators['current_price'] = current_price
            
            if TA_AVAILABLE:
                # RSI
                rsi = RSIIndicator(df['close'], window=self.rsi_period)
                indicators['rsi'] = float(rsi.rsi().iloc[-1])
                
                # Bollinger Bands
                bb = BollingerBands(df['close'], window=self.bb_period, window_dev=self.bb_std)
                indicators['bb_upper'] = float(bb.bollinger_hband().iloc[-1])
                indicators['bb_lower'] = float(bb.bollinger_lband().iloc[-1])
                indicators['bb_middle'] = float(bb.bollinger_mavg().iloc[-1])
                indicators['bb_percent'] = float(bb.bollinger_pband().iloc[-1])
                indicators['bb_width'] = float(bb.bollinger_wband().iloc[-1])
                
                # EMA
                ema = EMAIndicator(df['close'], window=self.ema_period)
                indicators['ema'] = float(ema.ema_indicator().iloc[-1])
                
                # ATR
                atr = AverageTrueRange(df['high'], df['low'], df['close'])
                indicators['atr'] = float(atr.average_true_range().iloc[-1])
                
            else:
                # Базовые вычисления без TA-Lib
                indicators['rsi'] = self._calculate_rsi(df['close'])
                bb_upper, bb_middle, bb_lower = self._calculate_bollinger_bands(df['close'])
                indicators['bb_upper'] = bb_upper
                indicators['bb_lower'] = bb_lower
                indicators['bb_middle'] = bb_middle
                
                # Bollinger percent
                bb_range = bb_upper - bb_lower
                if bb_range > 0:
                    indicators['bb_percent'] = (current_price - bb_lower) / bb_range
                else:
                    indicators['bb_percent'] = 0.5
                    
                indicators['bb_width'] = bb_range / bb_middle if bb_middle > 0 else 0
                indicators['ema'] = df['close'].ewm(span=self.ema_period).mean().iloc[-1]
                indicators['atr'] = self._calculate_atr(df)
            
            # Дополнительные вычисления
            # Отклонение от EMA в процентах
            indicators['ema_deviation'] = (current_price - indicators['ema']) / indicators['ema']
            
            # Позиция внутри Bollinger Bands
            indicators['bb_position'] = indicators['bb_percent']
            
            # Недавняя волатильность
            indicators['volatility'] = df['close'].pct_change().std() * np.sqrt(24)  # Дневная волатильность
            
            return indicators
            
        except Exception as e:
            logger.error(f"Ошибка расчета индикаторов mean reversion: {e}")
            return {}
    
    def _assess_market_condition(self, indicators: Dict, df: pd.DataFrame) -> str:
        """Оценка рыночных условий"""
        try:
            # Определяем силу тренда по Bollinger Band width
            bb_width = indicators.get('bb_width', 0)
            volatility = indicators.get('volatility', 0)
            
            # Mean reversion лучше работает в боковых рынках с низкой волатильностью
            if bb_width < 0.05 and volatility < 0.02:
                return 'SIDEWAYS_LOW_VOL'  # Идеальные условия
            elif bb_width < 0.08:
                return 'SIDEWAYS'  # Хорошие условия
            elif bb_width > 0.15:
                return 'TRENDING_HIGH_VOL'  # Плохие условия
            else:
                return 'NEUTRAL'
                
        except Exception as e:
            logger.error(f"Ошибка оценки рынка: {e}")
            return 'UNKNOWN'
    
    def _analyze_deviations(self, indicators: Dict) -> Dict:
        """Анализ отклонений от средних значений"""
        signals = {'buy_signals': [], 'sell_signals': []}
        
        try:
            current_price = indicators['current_price']
            rsi = indicators['rsi']
            bb_percent = indicators['bb_percent']
            ema_deviation = indicators['ema_deviation']
            
            # RSI экстремумы (более строгие уровни)
            if rsi < self.RSI_OVERSOLD:
                confidence = min((self.RSI_OVERSOLD - rsi) / 10, 1.0)  # Чем ниже RSI, тем выше уверенность
                signals['buy_signals'].append(('RSI_Extreme', f'RSI={rsi:.1f} - экстремальная перепроданность', confidence))
                
            elif rsi > self.RSI_OVERBOUGHT:
                confidence = min((rsi - self.RSI_OVERBOUGHT) / 10, 1.0)
                signals['sell_signals'].append(('RSI_Extreme', f'RSI={rsi:.1f} - экстремальная перекупленность', confidence))
            
            # Bollinger Bands экстремумы
            if bb_percent < self.BB_LOWER_THRESHOLD:
                confidence = min((self.BB_LOWER_THRESHOLD - bb_percent) / 0.1, 1.0)
                signals['buy_signals'].append(('BB_Extreme', f'BB%={bb_percent:.2f} - касание нижней полосы', confidence))
                
            elif bb_percent > self.BB_UPPER_THRESHOLD:
                confidence = min((bb_percent - self.BB_UPPER_THRESHOLD) / 0.1, 1.0)
                signals['sell_signals'].append(('BB_Extreme', f'BB%={bb_percent:.2f} - касание верхней полосы', confidence))
            
            # Сильное отклонение от EMA
            if ema_deviation < -self.PRICE_DEVIATION_THRESHOLD:
                confidence = min(abs(ema_deviation) / 0.05, 1.0)
                signals['buy_signals'].append(('EMA_Deviation', f'Отклонение от EMA: {ema_deviation:.2%}', confidence))
                
            elif ema_deviation > self.PRICE_DEVIATION_THRESHOLD:
                confidence = min(ema_deviation / 0.05, 1.0)
                signals['sell_signals'].append(('EMA_Deviation', f'Отклонение от EMA: {ema_deviation:.2%}', confidence))
            
            return signals
            
        except Exception as e:
            logger.error(f"Ошибка анализа отклонений: {e}")
            return signals
    
    def _make_decision(self, signals: Dict, indicators: Dict, market_condition: str, df: pd.DataFrame) -> TradingSignal:
        """Принятие решения для mean reversion"""
        try:
            buy_signals = signals['buy_signals']
            sell_signals = signals['sell_signals']
            
            current_price = indicators['current_price']
            atr = indicators['atr']
            
            # Корректировка уверенности в зависимости от рыночных условий
            market_multiplier = {
                'SIDEWAYS_LOW_VOL': 1.3,    # Лучшие условия
                'SIDEWAYS': 1.1,            # Хорошие условия
                'NEUTRAL': 1.0,             # Нормальные условия
                'TRENDING_HIGH_VOL': 0.7,   # Плохие условия
                'UNKNOWN': 0.8
            }.get(market_condition, 1.0)
            
            # BUY сигнал
            if buy_signals:
                total_confidence = sum(signal[2] for signal in buy_signals) * market_multiplier
                total_confidence = min(total_confidence, 1.0)
                
                if total_confidence >= self.min_confidence:
                    # Расчет уровней
                    stop_loss = self.calculate_stop_loss(current_price, 'BUY', atr)
                    take_profit = self.calculate_take_profit(current_price, 'BUY', atr)
                    
                    reasons = [f"{signal[0]}: {signal[1]}" for signal in buy_signals]
                    reason = f"MEAN_REVERSION_BUY ({market_condition}): " + "; ".join(reasons)
                    
                    return TradingSignal(
                        action='BUY',
                        confidence=total_confidence,
                        price=current_price,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        reason=reason,
                        risk_reward_ratio=(take_profit - current_price) / (current_price - stop_loss),
                        indicators=indicators
                    )
            
            # SELL сигнал
            if sell_signals:
                total_confidence = sum(signal[2] for signal in sell_signals) * market_multiplier
                total_confidence = min(total_confidence, 1.0)
                
                if total_confidence >= self.min_confidence:
                    stop_loss = self.calculate_stop_loss(current_price, 'SELL', atr)
                    take_profit = self.calculate_take_profit(current_price, 'SELL', atr)
                    
                    reasons = [f"{signal[0]}: {signal[1]}" for signal in sell_signals]
                    reason = f"MEAN_REVERSION_SELL ({market_condition}): " + "; ".join(reasons)
                    
                    return TradingSignal(
                        action='SELL',
                        confidence=total_confidence,
                        price=current_price,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        reason=reason,
                        risk_reward_ratio=(current_price - take_profit) / (stop_loss - current_price),
                        indicators=indicators
                    )
            
            # WAIT
            signal_count = len(buy_signals) + len(sell_signals)
            reason = f"WAIT ({market_condition}): сигналов={signal_count}, недостаточная уверенность"
            
            return TradingSignal(
                action='WAIT',
                confidence=0.0,
                price=current_price,
                reason=reason,
                indicators=indicators
            )
            
        except Exception as e:
            logger.error(f"Ошибка принятия решения mean reversion: {e}")
            return TradingSignal('WAIT', 0, 0, reason=f'Ошибка решения: {e}')
    
    # Вспомогательные методы для расчетов без TA-Lib
    def _calculate_rsi(self, prices, period=14):
        """RSI без TA-Lib"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return float(rsi.iloc[-1]) if not rsi.empty else 50.0
    
    def _calculate_bollinger_bands(self, prices, period=20, std_dev=2):
        """Bollinger Bands без TA-Lib"""
        sma = prices.rolling(window=period).mean()
        std = prices.rolling(window=period).std()
        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)
        return float(upper.iloc[-1]), float(sma.iloc[-1]), float(lower.iloc[-1])
    
    def _calculate_atr(self, df, period=14):
        """ATR без TA-Lib"""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        return float(atr.iloc[-1]) if not atr.empty else 0.01