/**
 * TradingController - Оптимизированный класс для управления торговым ботом
 * Версия 2.0 - Исправлены основные проблемы и улучшена структура
 * 
 * ИСПРАВЛЕНИЯ:
 * ✅ Унифицированы ID элементов
 * ✅ Исправлен конфликт WebSocket/Socket.IO  
 * ✅ Убрано дублирование кода
 * ✅ Улучшена обработка ошибок
 * ✅ Добавлена совместимость с jQuery
 */

class TradingController {
    constructor() {
        // Состояние контроллера
        this.isInitialized = false;
        this.botStatus = 'stopped';
        this.authToken = this.getAuthToken();
        this.updateInterval = null;
        this.socket = null; // Изменено с webSocket на socket для Socket.IO
        
        // Настройки обновления
        this.updateIntervals = {
            status: 5000,    // 5 секунд
            balance: 10000,  // 10 секунд
            trades: 15000,   // 15 секунд
            stats: 30000     // 30 секунд
        };
        
        // Кэш данных
        this.cache = {
            balance: null,
            trades: [],
            stats: null,
            positions: []
        };

        // Таймеры для интервалов
        this.intervals = {};
        
        this.init();
    }
    
    /**
     * Инициализация контроллера
     */
    async init() {
        console.log('🚀 Инициализация TradingController v2.0...');
        
        try {
            // Ждем полной загрузки DOM если еще не загружен
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', () => this.continueInit());
            } else {
                this.continueInit();
            }
            
        } catch (error) {
            console.error('❌ Ошибка инициализации TradingController:', error);
            this.showNotification('❌ Ошибка инициализации системы', 'error');
        }
    }

    async continueInit() {
        try {
            // Настройка обработчиков событий
            this.setupEventListeners();
            
            // Инициализация Socket.IO (если доступен)
            this.initSocketIO();
            
            // Первоначальная загрузка данных
            await this.loadInitialData();
            
            // Запуск периодических обновлений
            this.startUpdateCycles();
            
            this.isInitialized = true;
            console.log('✅ TradingController v2.0 инициализирован');
            
            this.showNotification('🔄 Система готова к работе', 'success');
            
        } catch (error) {
            console.error('❌ Ошибка продолжения инициализации:', error);
            this.showNotification('❌ Ошибка инициализации системы', 'error');
        }
    }
    
    /**
     * Настройка обработчиков событий - исправлены ID элементов
     */
    setupEventListeners() {
        // Исправленные ID кнопок (совпадают с HTML шаблоном)
        const startBtn = document.getElementById('btn-start');
        const stopBtn = document.getElementById('btn-stop');
        const emergencyBtn = document.getElementById('emergency-stop');
        
        if (startBtn) {
            startBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.startBot();
            });
        }
        
        if (stopBtn) {
            stopBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.stopBot();
            });
        }
        
        if (emergencyBtn) {
            emergencyBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.emergencyStop();
            });
        }
        
        // Обработчики для других элементов интерфейса
        this.setupFormHandlers();
        this.setupKeyboardShortcuts();
    }
    
    /**
     * Настройка обработчиков форм
     */
    setupFormHandlers() {
        // Форма настроек торговых пар
        const pairsForm = document.getElementById('trading-pairs-form');
        if (pairsForm) {
            pairsForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.updateTradingPairs();
            });
        }
        
        // Форма настроек стратегий
        const strategyForm = document.getElementById('strategy-settings-form');
        if (strategyForm) {
            strategyForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.updateStrategySettings();
            });
        }
    }
    
    /**
     * Настройка горячих клавиш
     */
    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Ctrl+S - Запуск/остановка бота
            if (e.ctrlKey && e.key === 's') {
                e.preventDefault();
                if (this.botStatus === 'running') {
                    this.stopBot();
                } else {
                    this.startBot();
                }
            }
            
            // Ctrl+E - Экстренная остановка
            if (e.ctrlKey && e.key === 'e') {
                e.preventDefault();
                this.emergencyStop();
            }
            
            // F5 - Обновление данных
            if (e.key === 'F5') {
                e.preventDefault();
                this.refreshAllData();
            }
        });
    }
    
    /**
     * Инициализация Socket.IO (вместо нативного WebSocket)
     */
    initSocketIO() {
        try {
            // Проверяем доступность Socket.IO
            if (typeof io !== 'undefined') {
                this.socket = io();
                
                this.socket.on('connect', () => {
                    console.log('✅ Socket.IO соединение установлено');
                    this.showNotification('🌐 Real-time подключение активно', 'info');
                });
                
                this.socket.on('disconnect', () => {
                    console.log('🔌 Socket.IO соединение закрыто');
                    this.showNotification('🔌 Соединение потеряно', 'warning');
                });
                
                this.socket.on('bot_status', (data) => {
                    this.handleSocketMessage('bot_status', data);
                });
                
                this.socket.on('new_trade', (data) => {
                    this.handleSocketMessage('new_trade', data);
                });
                
                this.socket.on('balance_update', (data) => {
                    this.handleSocketMessage('balance_update', data);
                });
                
                this.socket.on('error', (error) => {
                    console.error('❌ Socket.IO ошибка:', error);
                });
                
            } else {
                console.warn('⚠️ Socket.IO не доступен');
            }
            
        } catch (error) {
            console.error('❌ Ошибка инициализации Socket.IO:', error);
        }
    }
    
    /**
     * Обработка Socket.IO сообщений (заменяет handleWebSocketMessage)
     */
    handleSocketMessage(type, data) {
        try {
            switch (type) {
                case 'bot_status':
                    this.updateBotStatus(data.status === 'running');
                    break;
                    
                case 'balance_update':
                    this.updateBalance(data);
                    break;
                    
                case 'new_trade':
                    this.handleNewTrade(data);
                    break;
                    
                case 'new_signal':
                    this.handleNewSignal(data);
                    break;
                    
                default:
                    console.log('Неизвестное Socket сообщение:', type, data);
            }
            
        } catch (error) {
            console.error('Ошибка обработки Socket сообщения:', error);
        }
    }
    
    /**
     * Загрузка начальных данных
     */
    async loadInitialData() {
        console.log('📊 Загрузка начальных данных...');
        
        try {
            // Загружаем данные параллельно
            const promises = [
                this.loadBotStatus(),
                this.loadBalance(),
                this.loadStats(),
                this.loadRecentTrades()
            ];
            
            await Promise.allSettled(promises);
            console.log('✅ Начальные данные загружены');
            
        } catch (error) {
            console.error('❌ Ошибка загрузки данных:', error);
            this.showNotification('⚠️ Ошибка загрузки данных', 'warning');
        }
    }
    
    /**
     * Запуск бота - улучшенная версия
     */
    async startBot() {
        const startBtn = document.getElementById('btn-start');
        
        if (this.botStatus === 'running') {
            this.showNotification('⚠️ Бот уже запущен', 'warning');
            return;
        }
        
        if (startBtn) {
            startBtn.disabled = true;
            // Совместимость с jQuery
            if (typeof $ !== 'undefined') {
                $(startBtn).prop('disabled', true);
            }
        }
        
        try {
            console.log('🚀 Запуск торгового бота...');
            this.showNotification('🚀 Запуск бота...', 'info');
            
            const response = await this.apiRequest('/api/bot/start', {
                method: 'POST',
                body: JSON.stringify({
                    auto_strategy: true
                })
            });
            
            if (response.success) {
                this.botStatus = 'running';
                this.updateBotStatus(true);
                this.showNotification('✅ Бот запущен успешно!', 'success');
                
            } else {
                throw new Error(response.message || 'Неизвестная ошибка');
            }
            
        } catch (error) {
            console.error('❌ Ошибка запуска бота:', error);
            this.showNotification(`❌ Ошибка запуска: ${error.message}`, 'error');
            
            // Возвращаем кнопку в исходное состояние
            if (startBtn) {
                startBtn.disabled = false;
                if (typeof $ !== 'undefined') {
                    $(startBtn).prop('disabled', false);
                }
            }
        }
    }
    
    /**
     * Остановка бота - улучшенная версия
     */
    async stopBot() {
        const stopBtn = document.getElementById('btn-stop');
        
        if (this.botStatus === 'stopped') {
            this.showNotification('⚠️ Бот уже остановлен', 'warning');
            return;
        }
        
        if (stopBtn) {
            stopBtn.disabled = true;
            if (typeof $ !== 'undefined') {
                $(stopBtn).prop('disabled', true);
            }
        }
        
        try {
            console.log('🛑 Остановка торгового бота...');
            this.showNotification('🛑 Остановка бота...', 'info');
            
            const response = await this.apiRequest('/api/bot/stop', {
                method: 'POST'
            });
            
            if (response.success) {
                this.botStatus = 'stopped';
                this.updateBotStatus(false);
                this.showNotification('✅ Бот остановлен', 'success');
                
            } else {
                throw new Error(response.message || 'Неизвестная ошибка');
            }
            
        } catch (error) {
            console.error('❌ Ошибка остановки бота:', error);
            this.showNotification(`❌ Ошибка остановки: ${error.message}`, 'error');
            
            if (stopBtn) {
                stopBtn.disabled = false;
                if (typeof $ !== 'undefined') {
                    $(stopBtn).prop('disabled', false);
                }
            }
        }
    }
    
    /**
     * Экстренная остановка
     */
    async emergencyStop() {
        const confirmed = confirm(
            '⚠️ ЭКСТРЕННАЯ ОСТАНОВКА!\n\n' +
            'Это действие немедленно остановит все торговые операции.\n\n' +
            'Продолжить?'
        );
        
        if (!confirmed) return;
        
        try {
            console.log('🚨 ЭКСТРЕННАЯ ОСТАНОВКА!');
            this.showNotification('🚨 ЭКСТРЕННАЯ ОСТАНОВКА!', 'error');
            
            const response = await this.apiRequest('/api/bot/emergency-stop', {
                method: 'POST'
            });
            
            if (response.success) {
                this.botStatus = 'emergency_stop';
                this.updateBotStatus(false);
                this.showNotification('🚨 Экстренная остановка выполнена', 'error');
                
            } else {
                throw new Error(response.message || 'Неизвестная ошибка');
            }
            
        } catch (error) {
            console.error('❌ Ошибка экстренной остановки:', error);
            this.showNotification(`❌ Ошибка: ${error.message}`, 'error');
        }
    }
    
    /**
     * Загрузка статуса бота
     */
    async loadBotStatus() {
        try {
            const response = await this.apiRequest('/api/bot/status');
            
            if (response.success) {
                const isRunning = response.status === 'running';
                this.botStatus = response.status;
                this.updateBotStatus(isRunning);
            }
            
        } catch (error) {
            console.error('❌ Ошибка загрузки статуса бота:', error);
        }
    }
    
    /**
     * Загрузка баланса - совместимость с существующим кодом
     */
    async loadBalance() {
        try {
            const response = await this.apiRequest('/api/balance');
            
            if (response.success || !response.error) {
                this.cache.balance = response;
                this.updateBalance(response);
                
                // Обновляем график если есть функция (совместимость)
                if (typeof window.balanceChart !== 'undefined' && window.balanceChart) {
                    this.updateBalanceChart(response);
                }
            }
            
        } catch (error) {
            console.error('❌ Ошибка загрузки баланса:', error);
            this.updateBalanceDisplay('Ошибка');
        }
    }
    
    /**
     * Загрузка статистики
     */
    async loadStats() {
        try {
            const response = await this.apiRequest('/api/stats');
            
            if (response.success) {
                this.cache.stats = response;
                this.updateStatsDisplay(response);
            }
            
        } catch (error) {
            console.error('❌ Ошибка загрузки статистики:', error);
        }
    }
    
    /**
     * Загрузка последних сделок
     */
    async loadRecentTrades() {
        try {
            const response = await this.apiRequest('/api/trades?limit=10');
            
            if (response.success && response.trades) {
                this.cache.trades = response.trades;
                this.updateTradesTable(response.trades);
            }
            
        } catch (error) {
            console.error('❌ Ошибка загрузки сделок:', error);
        }
    }
    
    /**
     * Обновление статуса бота - исправленные ID
     */
    updateBotStatus(isRunning) {
        // Обновляем состояние
        this.botStatus = isRunning ? 'running' : 'stopped';
        
        // Обновляем UI элементы
        const statusCard = document.getElementById('bot-status-card');
        const statusIndicator = document.getElementById('bot-status-indicator');
        const statusText = document.getElementById('bot-status-text');
        const startBtn = document.getElementById('btn-start');
        const stopBtn = document.getElementById('btn-stop');
        
        if (statusCard) {
            statusCard.innerHTML = isRunning ? 
                '<i class="fas fa-check-circle"></i> Работает' : 
                '<i class="fas fa-times-circle"></i> Остановлен';
        }
        
        if (statusIndicator) {
            const icon = statusIndicator.querySelector('i');
            if (icon) {
                icon.className = isRunning ? 
                    'fas fa-circle fa-3x text-success' : 
                    'fas fa-circle fa-3x text-danger';
            }
        }
        
        if (statusText) {
            statusText.textContent = isRunning ? 'Бот активен' : 'Бот остановлен';
        }
        
        if (startBtn) {
            startBtn.disabled = isRunning;
            if (typeof $ !== 'undefined') {
                $(startBtn).prop('disabled', isRunning);
            }
        }
        
        if (stopBtn) {
            stopBtn.disabled = !isRunning;
            if (typeof $ !== 'undefined') {
                $(stopBtn).prop('disabled', !isRunning);
            }
        }
    }
    
    /**
     * Обновление баланса - совместимость с jQuery
     */
    updateBalance(data) {
        const balanceDisplay = document.getElementById('balance-display');
        
        if (balanceDisplay && data) {
            const total = data.total_usdt || 0;
            balanceDisplay.textContent = `$${total.toFixed(2)}`;
            
            // jQuery совместимость
            if (typeof $ !== 'undefined') {
                $('#balance-display').text(`$${total.toFixed(2)}`);
            }
        }
    }
    
    /**
     * Обновление графика баланса (совместимость)
     */
    updateBalanceChart(data) {
        if (typeof window.balanceChart !== 'undefined' && window.balanceChart && data.total_usdt) {
            const now = new Date().toLocaleTimeString();
            window.balanceChart.data.labels.push(now);
            window.balanceChart.data.datasets[0].data.push(data.total_usdt);
            
            // Ограничиваем количество точек
            if (window.balanceChart.data.labels.length > 20) {
                window.balanceChart.data.labels.shift();
                window.balanceChart.data.datasets[0].data.shift();
            }
            
            window.balanceChart.update();
        }
    }
    
    /**
     * Обновление таблицы сделок
     */
    updateTradesTable(trades) {
        const tbody = document.getElementById('trades-table');
        if (!tbody || !trades) return;
        
        // Очищаем таблицу
        tbody.innerHTML = '';
        
        trades.forEach(trade => {
            const row = this.createTradeRow(trade);
            tbody.appendChild(row);
        });
    }
    
    /**
     * Создание строки таблицы сделок
     */
    createTradeRow(trade) {
        const row = document.createElement('tr');
        
        const profitClass = (trade.profit >= 0) ? 'text-success' : 'text-danger';
        const sideClass = (trade.side === 'BUY') ? 'success' : 'danger';
        const statusClass = trade.status === 'CLOSED' ? 'success' : 'primary';
        
        const createdAt = trade.created_at ? 
            new Date(trade.created_at).toLocaleString('ru-RU') : 'N/A';
        
        row.innerHTML = `
            <td>${trade.id || 'N/A'}</td>
            <td>${createdAt}</td>
            <td>${trade.symbol || 'N/A'}</td>
            <td><span class="badge bg-${sideClass}">${trade.side || 'N/A'}</span></td>
            <td>$${(trade.price || 0).toFixed(2)}</td>
            <td>${(trade.quantity || 0).toFixed(4)}</td>
            <td><span class="badge bg-${statusClass}">${trade.status || 'N/A'}</span></td>
            <td class="${profitClass}">$${(trade.profit || 0).toFixed(2)}</td>
        `;
        
        return row;
    }
    
    /**
     * Обновление отображения баланса
     */
    updateBalanceDisplay(value) {
        const balanceElement = document.getElementById('balance-display');
        if (balanceElement) {
            balanceElement.textContent = typeof value === 'string' ? value : `$${value.toFixed(2)}`;
        }
    }
    
    /**
     * Получение токена авторизации
     */
    getAuthToken() {
        return localStorage.getItem('auth_token') || 
               sessionStorage.getItem('auth_token') || 
               '';
    }
    
    /**
     * API запрос с улучшенной обработкой ошибок
     */
    async apiRequest(url, options = {}) {
        const defaultOptions = {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json'
            }
        };
        
        // Добавляем токен авторизации если есть
        if (this.authToken) {
            defaultOptions.headers['Authorization'] = `Bearer ${this.authToken}`;
        }
        
        const finalOptions = { ...defaultOptions, ...options };
        
        try {
            const response = await fetch(url, finalOptions);
            
            if (!response.ok) {
                if (response.status === 401) {
                    this.handleAuthError();
                }
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            return await response.json();
            
        } catch (error) {
            console.error(`API запрос к ${url} не удался:`, error);
            throw error;
        }
    }
    
    /**
     * Обработка ошибок авторизации
     */
    handleAuthError() {
        console.log('🔐 Ошибка авторизации');
        this.showNotification('🔐 Сессия истекла. Необходимо войти заново.', 'warning');
        
        setTimeout(() => {
            window.location.href = '/login';
        }, 2000);
    }
    
    /**
     * Показ уведомлений - совместимость с jQuery
     */
    showNotification(message, type = 'info') {
        // Если доступен jQuery и контейнер уведомлений
        if (typeof $ !== 'undefined' && $('#notifications-container').length) {
            const alertClass = {
                'success': 'alert-success',
                'error': 'alert-danger', 
                'warning': 'alert-warning',
                'info': 'alert-info'
            }[type] || 'alert-info';

            const notification = $(`
                <div class="alert ${alertClass} alert-dismissible fade show" role="alert">
                    ${message}
                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                </div>
            `);

            $('#notifications-container').append(notification);
            
            setTimeout(() => {
                notification.alert('close');
            }, 5000);
            
        } else {
            // Fallback на нативные уведомления
            this.showNativeNotification(message, type);
        }
    }
    
    /**
     * Нативные уведомления
     */
    showNativeNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `alert alert-${type} notification`;
        notification.textContent = message;
        
        Object.assign(notification.style, {
            position: 'fixed',
            top: '20px',
            right: '20px',
            zIndex: '9999',
            padding: '15px 20px',
            borderRadius: '5px',
            boxShadow: '0 4px 6px rgba(0,0,0,0.1)',
            transform: 'translateX(400px)',
            transition: 'transform 0.3s ease-in-out'
        });
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.style.transform = 'translateX(0)';
        }, 100);
        
        setTimeout(() => {
            notification.style.transform = 'translateX(400px)';
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 300);
        }, 3000);
    }
    
    /**
     * Запуск циклов обновления
     */
    startUpdateCycles() {
        console.log('🔄 Запуск циклов обновления данных...');
        
        // Очищаем существующие интервалы
        this.stopUpdateCycles();
        
        // Обновление статуса бота
        this.intervals.status = setInterval(() => {
            if (this.isInitialized) {
                this.loadBotStatus();
            }
        }, this.updateIntervals.status);
        
        // Обновление баланса
        this.intervals.balance = setInterval(() => {
            if (this.isInitialized) {
                this.loadBalance();
            }
        }, this.updateIntervals.balance);
        
        // Обновление статистики
        this.intervals.stats = setInterval(() => {
            if (this.isInitialized) {
                this.loadStats();
            }
        }, this.updateIntervals.stats);
        
        // Обновление сделок
        this.intervals.trades = setInterval(() => {
            if (this.isInitialized && this.botStatus === 'running') {
                this.loadRecentTrades();
            }
        }, this.updateIntervals.trades);
    }
    
    /**
     * Остановка циклов обновления
     */
    stopUpdateCycles() {
        Object.values(this.intervals).forEach(interval => {
            if (interval) clearInterval(interval);
        });
        this.intervals = {};
    }
    
    /**
     * Обновление всех данных
     */
    async refreshAllData() {
        console.log('🔄 Принудительное обновление всех данных...');
        this.showNotification('🔄 Обновление данных...', 'info');
        
        await this.loadInitialData();
        this.showNotification('✅ Данные обновлены', 'success');
    }
    
    /**
     * Обработка новой сделки
     */
    handleNewTrade(trade) {
        console.log('💰 Новая сделка:', trade);
        
        // Добавляем в кэш
        this.cache.trades.unshift(trade);
        if (this.cache.trades.length > 50) {
            this.cache.trades.pop();
        }
        
        // Обновляем таблицу
        this.updateTradesTable(this.cache.trades);
        
        // Показываем уведомление
        const profit = trade.profit >= 0 ? '+' : '';
        this.showNotification(
            `💰 ${trade.symbol}: ${profit}$${trade.profit.toFixed(2)}`, 
            trade.profit >= 0 ? 'success' : 'warning'
        );
    }
    
    /**
     * Обработка нового сигнала
     */
    handleNewSignal(signal) {
        console.log('📡 Новый сигнал:', signal);
        this.showNotification(`📡 Сигнал: ${signal.type} ${signal.symbol}`, 'info');
    }
    
    /**
     * Деструктор - очистка ресурсов
     */
    destroy() {
        console.log('🗑️ Очистка TradingController...');
        
        if (this.socket && this.socket.disconnect) {
            this.socket.disconnect();
        }
        
        this.stopUpdateCycles();
        this.isInitialized = false;
    }
}

// Глобальная переменная для контроллера
window.tradingController = null;

// Функция инициализации (может быть вызвана из HTML)
function initTradingController() {
    if (!window.tradingController) {
        console.log('🚀 Инициализация TradingController из функции...');
        window.tradingController = new TradingController();
    }
    return window.tradingController;
}

// Автоматическая инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 DOM загружен, инициализируем TradingController...');
    initTradingController();
});

// Очистка при выгрузке страницы
window.addEventListener('beforeunload', function() {
    if (window.tradingController) {
        window.tradingController.destroy();
    }
});

// Экспорт для совместимости
if (typeof module !== 'undefined' && module.exports) {
    module.exports = TradingController;
}