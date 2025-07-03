# ЗАМЕНИТЬ ВЕСЬ ФАЙЛ НА ЭТОТ КОД:
#!/usr/bin/env python3
"""
Конфигурация Bybit API v5 - ИСПРАВЛЕННАЯ ВЕРСИЯ
"""

import logging
import os
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class BybitAPIConfig:
    """Конфигурация для Bybit API v5 с полной интеграцией"""
    
    # Эндпоинты API
    ENDPOINTS = {
        'mainnet': {
            'base': 'https://api.bybit.com',
            'websocket_public': 'wss://stream.bybit.com/v5/public',
            'websocket_private': 'wss://stream.bybit.com/v5/private'
        },
        'testnet': {
            'base': 'https://api-testnet.bybit.com',
            'websocket_public': 'wss://stream-testnet.bybit.com/v5/public',
            'websocket_private': 'wss://stream-testnet.bybit.com/v5/private'
        }
    }
    
    @classmethod
    def get_ccxt_config(cls, api_key: str, secret: str, testnet: bool = True, 
                       market_type: str = 'spot') -> Dict[str, Any]:
        """Создание конфигурации для CCXT"""
        
        # Выбор эндпоинтов
        endpoints = cls.ENDPOINTS['testnet'] if testnet else cls.ENDPOINTS['mainnet']
        
        config = {
            'apiKey': api_key,
            'secret': secret,
            'enableRateLimit': True,
            'rateLimit': 2000,  # Увеличен интервал
            'timeout': 30000,
            'options': {
                'defaultType': market_type,
                'adjustForTimeDifference': True,
                'recvWindow': 5000,
                'fetchCurrencies': False,  # Отключаем проблемную функцию
                'fetchFundingHistory': False,
                'fetchTickers': True,
                'fetchOHLCV': 'emulated'
            },
            'headers': {
                'User-Agent': 'TradingBot-V5/1.0',
                'Accept': 'application/json'
            }
        }
        
        # Настройка для testnet
        if testnet:
            config['sandbox'] = True
            config['urls'] = {
                'api': {
                    'public': endpoints['base'],
                    'private': endpoints['base'],
                },
                'test': {
                    'public': endpoints['base'],
                    'private': endpoints['base'],
                }
            }
        
        return config
    
    @classmethod
    def integrate_with_unified_config(cls, unified_config) -> Dict[str, Any]:
        """Интеграция с существующим unified_config"""
        try:
            # Получаем API ключи из unified_config
            api_key = getattr(unified_config, 'BYBIT_API_KEY', '')
            
            # Проверяем разные варианты имени secret
            secret = (getattr(unified_config, 'BYBIT_API_SECRET', '') or 
                     getattr(unified_config, 'BYBIT_SECRET_KEY', '') or
                     getattr(unified_config, 'BYBIT_SECRET', ''))
            
            testnet = getattr(unified_config, 'BYBIT_TESTNET', True)
            
            # Создаем конфигурацию
            config = cls.get_ccxt_config(api_key, secret, testnet, 'spot')
            
            # Добавляем дополнительные настройки
            if hasattr(unified_config, 'BYBIT_RECV_WINDOW'):
                config['options']['recvWindow'] = unified_config.BYBIT_RECV_WINDOW
            
            if hasattr(unified_config, 'CONNECTION_TIMEOUT'):
                config['timeout'] = unified_config.CONNECTION_TIMEOUT * 1000
                
            logger.info("✅ Интеграция с unified_config успешна")
            return config
            
        except Exception as e:
            logger.error(f"❌ Ошибка интеграции: {e}")
            return {}

# Создаем экземпляр
bybit_config = BybitAPIConfig()

__all__ = ['BybitAPIConfig', 'bybit_config']