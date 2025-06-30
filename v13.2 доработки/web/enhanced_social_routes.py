"""
Улучшенные роуты для социальных сигналов
Файл: src/web/enhanced_social_routes.py
"""
from flask import jsonify, request
from typing import Optional
import logging

from ..analysis.social.enhanced_signals import enhanced_social_manager

logger = logging.getLogger(__name__)

def register_enhanced_social_routes(app):
    """Регистрация улучшенных роутов для социальных сигналов"""
    
    @app.route('/api/social/signals/enhanced', methods=['GET'])
    def get_enhanced_social_signals():
        """Получение улучшенных социальных сигналов"""
        try:
            symbol = request.args.get('symbol', '').upper()
            limit = min(request.args.get('limit', 20, type=int), 100)
            
            logger.info(f"📊 Запрос улучшенных социальных сигналов: symbol={symbol}, limit={limit}")
            
            # Получаем сигналы
            import asyncio
            signals = asyncio.run(enhanced_social_manager.get_signals_for_symbol(symbol, limit))
            
            # Форматируем ответ
            formatted_signals = []
            for signal in signals:
                formatted_signals.append({
                    'source': signal.source,
                    'symbol': signal.symbol,
                    'sentiment': signal.sentiment,
                    'confidence': signal.confidence,
                    'content': signal.content,
                    'author': signal.author,
                    'timestamp': signal.timestamp.isoformat(),
                    'engagement': signal.engagement,
                    'influence_score': signal.influence_score
                })
            
            return jsonify({
                'success': True,
                'signals': formatted_signals,
                'count': len(formatted_signals),
                'symbol': symbol,
                'timestamp': datetime.utcnow().isoformat()
            })
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения улучшенных сигналов: {e}")
            return jsonify({
                'success': False,
                'error': str(e),
                'signals': [],
                'count': 0
            }), 500
    
    logger.info("✅ Улучшенные роуты для социальных сигналов зарегистрированы")