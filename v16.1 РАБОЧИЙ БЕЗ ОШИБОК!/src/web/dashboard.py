"""
Полный дашборд для торгового бота с авторизацией
Файл: src/web/dashboard.py
"""

def get_dashboard_html() -> str:
    """Возвращает HTML код полного дашборда с авторизацией"""
    
    html = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🚀 Криптотрейдинг Бот - Панель Управления</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            color: #333;
        }
        
        /* Стили для формы авторизации */
        .login-container {
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            padding: 20px;
        }
        
        .login-form {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            padding: 40px;
            border-radius: 20px;
            box-shadow: 0 15px 35px rgba(0, 0, 0, 0.2);
            width: 100%;
            max-width: 400px;
        }
        
        .login-form h2 {
            text-align: center;
            color: #2c3e50;
            margin-bottom: 30px;
            font-size: 2em;
        }
        
        .login-input-group {
            margin-bottom: 20px;
        }
        
        .login-input-group label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: #2c3e50;
        }
        
        .login-input-group input {
            width: 100%;
            padding: 12px 15px;
            border: 2px solid #ecf0f1;
            border-radius: 10px;
            font-size: 1em;
            transition: border-color 0.3s ease;
        }
        
        .login-input-group input:focus {
            outline: none;
            border-color: #3498db;
            box-shadow: 0 0 0 3px rgba(52, 152, 219, 0.1);
        }
        
        .login-btn {
            width: 100%;
            background: linear-gradient(135deg, #3498db, #2980b9);
            color: white;
            border: none;
            padding: 14px;
            border-radius: 10px;
            font-size: 1.1em;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .login-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(52, 152, 219, 0.4);
        }
        
        .login-error {
            background: rgba(231, 76, 60, 0.1);
            color: #e74c3c;
            padding: 10px;
            border-radius: 10px;
            margin-bottom: 20px;
            text-align: center;
            display: none;
        }
        
        /* Основные стили дашборда */
        .main-container {
            display: none;
        }
        
        .header {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            padding: 20px;
            box-shadow: 0 2px 20px rgba(0, 0, 0, 0.1);
            position: sticky;
            top: 0;
            z-index: 100;
        }
        
        .header-content {
            max-width: 1400px;
            margin: 0 auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .header h1 {
            color: #2c3e50;
            font-size: 2.5em;
        }
        
        .user-info {
            display: flex;
            align-items: center;
            gap: 20px;
        }
        
        .user-badge {
            background: rgba(52, 152, 219, 0.1);
            padding: 8px 16px;
            border-radius: 20px;
            font-weight: 600;
            color: #2c3e50;
        }
        
        .logout-btn {
            background: linear-gradient(135deg, #e74c3c, #c0392b);
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 20px;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.3s ease;
        }
        
        .logout-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(231, 76, 60, 0.4);
        }
        
        .status-bar {
            display: flex;
            justify-content: center;
            gap: 30px;
            flex-wrap: wrap;
            margin-top: 20px;
        }
        
        .status-item {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 10px 20px;
            background: rgba(52, 152, 219, 0.1);
            border-radius: 25px;
            border: 2px solid transparent;
            transition: all 0.3s ease;
        }
        
        .status-item.active {
            background: rgba(46, 204, 113, 0.2);
            border-color: #2ecc71;
        }
        
        .status-item.error {
            background: rgba(231, 76, 60, 0.2);
            border-color: #e74c3c;
        }
        
        .status-dot {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: #95a5a6;
            animation: pulse 2s infinite;
        }
        
        .status-dot.active {
            background: #2ecc71;
        }
        
        .status-dot.error {
            background: #e74c3c;
        }
        
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 30px 20px;
        }
        
        .control-panel {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 25px;
            margin-bottom: 30px;
        }
        
        .card {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 25px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }
        
        .card:hover {
            transform: translateY(-5px);
            box-shadow: 0 15px 40px rgba(0, 0, 0, 0.15);
        }
        
        .card h3 {
            color: #2c3e50;
            margin-bottom: 20px;
            font-size: 1.4em;
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
        }
        
        .btn {
            background: linear-gradient(135deg, #3498db, #2980b9);
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 25px;
            cursor: pointer;
            font-size: 1em;
            font-weight: 600;
            transition: all 0.3s ease;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin: 5px;
            min-width: 120px;
        }
        
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(52, 152, 219, 0.4);
        }
        
        .btn.btn-success {
            background: linear-gradient(135deg, #2ecc71, #27ae60);
        }
        
        .btn.btn-success:hover {
            box-shadow: 0 5px 15px rgba(46, 204, 113, 0.4);
        }
        
        .btn.btn-danger {
            background: linear-gradient(135deg, #e74c3c, #c0392b);
        }
        
        .btn.btn-danger:hover {
            box-shadow: 0 5px 15px rgba(231, 76, 60, 0.4);
        }
        
        .btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }
        
        .input-group {
            margin-bottom: 20px;
        }
        
        .input-group label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: #2c3e50;
        }
        
        .input-group select,
        .input-group input {
            width: 100%;
            padding: 12px 15px;
            border: 2px solid #ecf0f1;
            border-radius: 10px;
            font-size: 1em;
            transition: border-color 0.3s ease;
            background: white;
        }
        
        .input-group select:focus,
        .input-group input:focus {
            outline: none;
            border-color: #3498db;
            box-shadow: 0 0 0 3px rgba(52, 152, 219, 0.1);
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .stat-card {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            padding: 20px;
            border-radius: 15px;
            text-align: center;
            box-shadow: 0 5px 20px rgba(0, 0, 0, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        
        .stat-number {
            font-size: 2.5em;
            font-weight: bold;
            color: #2c3e50;
            margin-bottom: 5px;
        }
        
        .stat-label {
            color: #7f8c8d;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .stat-card.positive .stat-number {
            color: #2ecc71;
        }
        
        .stat-card.negative .stat-number {
            color: #e74c3c;
        }
        
        .trades-table {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            overflow: hidden;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
        }
        
        .trades-table table {
            width: 100%;
            border-collapse: collapse;
        }
        
        .trades-table th,
        .trades-table td {
            padding: 15px;
            text-align: left;
            border-bottom: 1px solid #ecf0f1;
        }
        
        .trades-table th {
            background: #f8f9fa;
            font-weight: 600;
            color: #2c3e50;
        }
        
        .trades-table tr:hover {
            background: rgba(52, 152, 219, 0.05);
        }
        
        .profit {
            color: #2ecc71;
            font-weight: bold;
        }
        
        .loss {
            color: #e74c3c;
            font-weight: bold;
        }
        
        .logs-container {
            background: rgba(0, 0, 0, 0.9);
            color: #00ff00;
            font-family: 'Courier New', monospace;
            border-radius: 15px;
            padding: 20px;
            max-height: 300px;
            overflow-y: auto;
            margin-top: 20px;
        }
        
        .log-entry {
            margin: 5px 0;
            padding: 5px;
            border-left: 3px solid #00ff00;
            padding-left: 10px;
        }
        
        .log-error {
            color: #ff4444;
            border-left-color: #ff4444;
        }
        
        .log-warning {
            color: #ffaa00;
            border-left-color: #ffaa00;
        }
        
        .toggle-switch {
            position: relative;
            display: inline-block;
            width: 60px;
            height: 34px;
        }
        
        .toggle-switch input {
            opacity: 0;
            width: 0;
            height: 0;
        }
        
        .slider {
            position: absolute;
            cursor: pointer;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: #ccc;
            transition: .4s;
            border-radius: 34px;
        }
        
        .slider:before {
            position: absolute;
            content: "";
            height: 26px;
            width: 26px;
            left: 4px;
            bottom: 4px;
            background-color: white;
            transition: .4s;
            border-radius: 50%;
        }
        
        input:checked + .slider {
            background-color: #2196F3;
        }
        
        input:checked + .slider:before {
            transform: translateX(26px);
        }
        
        .notification {
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 15px 25px;
            border-radius: 10px;
            color: white;
            font-weight: 600;
            z-index: 1000;
            transform: translateX(400px);
            transition: transform 0.3s ease;
        }
        
        .notification.show {
            transform: translateX(0);
        }
        
        .notification.success {
            background: #2ecc71;
        }
        
        .notification.error {
            background: #e74c3c;
        }
        
        .notification.info {
            background: #3498db;
        }
        
        .strategy-info {
            background: rgba(52, 152, 219, 0.1);
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
        }
        
        .strategy-table {
            width: 100%;
            margin-top: 10px;
        }
        
        .strategy-table th,
        .strategy-table td {
            padding: 8px;
            text-align: left;
        }
        
        .strategy-table th {
            font-weight: 600;
            color: #2c3e50;
        }
        
        @media (max-width: 768px) {
            .header h1 {
                font-size: 1.5em;
            }
            
            .header-content {
                flex-direction: column;
                gap: 15px;
            }
            
            .status-bar {
                flex-direction: column;
                align-items: center;
            }
            
            .control-panel {
                grid-template-columns: 1fr;
            }
            
            .stats-grid {
                grid-template-columns: repeat(2, 1fr);
            }
        }
    </style>
</head>
<body>
    <!-- Форма авторизации -->
    <div class="login-container" id="loginContainer">
        <div class="login-form">
            <h2>🔐 Вход в систему</h2>
            <div class="login-error" id="loginError"></div>
            <form id="loginForm" onsubmit="return handleLogin(event)">
                <div class="login-input-group">
                    <label for="username">Имя пользователя</label>
                    <input type="text" id="username" name="username" required autofocus>
                </div>
                <div class="login-input-group">
                    <label for="password">Пароль</label>
                    <input type="password" id="password" name="password" required>
                </div>
                <button type="submit" class="login-btn">Войти</button>
            </form>
        </div>
    </div>

    <!-- Основной дашборд -->
    <div class="main-container" id="mainContainer">
        <div class="header">
            <div class="header-content">
                <h1>🚀 Криптотрейдинг Бот</h1>
                <div class="user-info">
                    <div class="user-badge">👤 <span id="currentUser">Admin</span></div>
                    <button class="logout-btn" onclick="handleLogout()">Выход</button>
                </div>
            </div>
            <div class="status-bar">
                <div class="status-item" id="bot-status">
                    <span class="status-dot" id="bot-dot"></span>
                    <span>Статус: <span id="bot-status-text">Остановлен</span></span>
                </div>
                <div class="status-item" id="connection-status">
                    <span class="status-dot"></span>
                    <span>Соединение: <span id="connection-text">Отключено</span></span>
                </div>
                <div class="status-item">
                    <span class="status-dot active"></span>
                    <span>База данных: Подключена</span>
                </div>
                <div class="status-item">
                    <span class="status-dot active"></span>
                    <span>Биржа: Bybit (Testnet)</span>
                </div>
            </div>
        </div>

        <div class="container">
            <!-- Статистика -->
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-number" id="total-trades">0</div>
                    <div class="stat-label">Всего сделок</div>
                </div>
                <div class="stat-card positive">
                    <div class="stat-number" id="total-profit">+0.00 USDT</div>
                    <div class="stat-label">Общая прибыль</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="success-rate">0%</div>
                    <div class="stat-label">Успешные сделки</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="active-positions">0</div>
                    <div class="stat-label">Активные позиции</div>
                </div>
            </div>

            <!-- Панель управления -->
            <div class="control-panel">
                <!-- Управление ботом -->
                <div class="card">
                    <h3>🤖 Управление ботом</h3>
                    <div class="strategy-info">
                        <strong>🧠 Автоматический выбор стратегий</strong>
                        <p style="margin-top: 10px; color: #7f8c8d; font-size: 0.9em;">
                            Система автоматически анализирует рынок и выбирает оптимальную стратегию для каждой пары
                        </p>
                    </div>
                    <div style="text-align: center;">
                        <button id="start-bot" class="btn btn-success">▶️ Запустить бота</button>
                        <button id="stop-bot" class="btn btn-danger">⏹️ Остановить бота</button>
                    </div>
                </div>

                <!-- Текущие стратегии -->
                <div class="card" id="current-strategies-card">
                    <h3>🧠 Активные стратегии</h3>
                    <div id="current-strategies">
                        <p style="color: #7f8c8d; text-align: center; padding: 20px;">
                            Запустите бота для отображения стратегий
                        </p>
                    </div>
                </div>

                <!-- Торговые пары -->
                <div class="card">
                    <h3>💱 Торговые пары</h3>
                    <div style="margin-bottom: 15px;">
                        <label>
                            <input type="checkbox" checked value="BTCUSDT"> BTCUSDT - Bitcoin/USDT
                        </label>
                    </div>
                    <div style="margin-bottom: 15px;">
                        <label>
                            <input type="checkbox" checked value="ETHUSDT"> ETHUSDT - Ethereum/USDT
                        </label>
                    </div>
                    <div style="margin-bottom: 15px;">
                        <label>
                            <input type="checkbox" checked value="BNBUSDT"> BNBUSDT - BNB/USDT
                        </label>
                    </div>
                    <div style="margin-bottom: 15px;">
                        <label>
                            <input type="checkbox" checked value="SOLUSDT"> SOLUSDT - Solana/USDT
                        </label>
                    </div>
                    <div style="margin-bottom: 15px;">
                        <label>
                            <input type="checkbox" value="ADAUSDT"> ADAUSDT - Cardano/USDT
                        </label>
                    </div>
                    <div style="margin-bottom: 15px;">
                        <label>
                            <input type="checkbox" value="XRPUSDT"> XRPUSDT - Ripple/USDT
                        </label>
                    </div>
                    <button class="btn" onclick="saveTradingPairs()">💾 Сохранить настройки</button>
                </div>

                <!-- Управление рисками -->
                <div class="card">
                    <h3>⚠️ Управление рисками</h3>
                    <div class="input-group">
                        <label for="max-position">Максимальный размер позиции (%):</label>
                        <input type="number" id="max-position" value="5" min="1" max="100" step="0.5">
                    </div>
                    <div class="input-group">
                        <label for="stop-loss">Стоп-лосс (%):</label>
                        <input type="number" id="stop-loss" value="2" min="0.5" max="10" step="0.5">
                    </div>
                    <div class="input-group">
                        <label for="take-profit">Тейк-профит (%):</label>
                        <input type="number" id="take-profit" value="4" min="1" max="20" step="0.5">
                    </div>
                    <div class="input-group">
                        <label for="max-trades">Максимум сделок в день:</label>
                        <input type="number" id="max-trades" value="10" min="1" max="50" step="1">
                    </div>
                </div>

                <!-- Системная информация -->
                <div class="card">
                    <h3>🖥️ Система</h3>
                    <p><strong>Время работы:</strong> <span id="uptime">00:00:00</span></p>
                    <p><strong>Последнее обновление:</strong> <span id="last-cycle">Никогда</span></p>
                    <p><strong>Количество циклов:</strong> <span id="cycles-count">0</span></p>
                    <p><strong>Использование памяти:</strong> <span id="memory-usage">0 MB</span></p>
                    <div style="margin-top: 15px;">
                        <button class="btn" onclick="exportTrades()">📊 Экспорт сделок</button>
                        <button class="btn" onclick="clearLogs()">🗑️ Очистить логи</button>
                    </div>
                </div>

                <!-- Быстрые действия -->
                <div class="card">
                    <h3>⚡ Быстрые действия</h3>
                    <button class="btn" onclick="closeAllPositions()">❌ Закрыть все позиции</button>
                    <button class="btn" onclick="refreshStats()">🔄 Обновить статистику</button>
                    <button class="btn" onclick="testNotification()">🔔 Тест уведомлений</button>
                    <button class="btn btn-danger" onclick="emergencyStop()">🚨 Экстренная остановка</button>
                </div>
            </div>

            <!-- Таблица сделок -->
            <div class="trades-table">
                <h3 style="padding: 20px; margin: 0; background: #f8f9fa; border-bottom: 1px solid #ecf0f1;">📈 Последние сделки</h3>
                <table>
                    <thead>
                        <tr>
                            <th>Время</th>
                            <th>Пара</th>
                            <th>Тип</th>
                            <th>Количество</th>
                            <th>Цена</th>
                            <th>Прибыль/Убыток</th>
                            <th>Стратегия</th>
                            <th>Статус</th>
                        </tr>
                    </thead>
                    <tbody id="trades-tbody">
                        <tr>
                            <td colspan="8" style="text-align: center; padding: 40px; color: #7f8c8d;">
                                Пока нет сделок
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>

            <!-- Логи -->
            <div class="logs-container">
                <h3 style="color: #00ff00; margin-bottom: 15px;">📋 Системные логи</h3>
                <div id="logs-content">
                    <div class="log-entry">[СИСТЕМА] Ожидание авторизации...</div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Глобальные переменные
        let wsConnection = null;
        let botStatus = 'stopped';
        let isConnected = false;
        let currentStrategies = {};
        let authToken = null;
        let currentUsername = null;

        // Проверка авторизации при загрузке
        document.addEventListener('DOMContentLoaded', function() {
            checkAuth();
        });

        // Проверка сохраненного токена
        function checkAuth() {
            authToken = localStorage.getItem('authToken');
            currentUsername = localStorage.getItem('username');
            
            if (authToken) {
                // Проверяем валидность токена
                showDashboard();
            } else {
                showLoginForm();
            }
        }

        // Показать форму входа
        function showLoginForm() {
            document.getElementById('loginContainer').style.display = 'flex';
            document.getElementById('mainContainer').style.display = 'none';
        }

        // Показать дашборд
        function showDashboard() {
            document.getElementById('loginContainer').style.display = 'none';
            document.getElementById('mainContainer').style.display = 'block';
            
            if (currentUsername) {
                document.getElementById('currentUser').textContent = currentUsername;
            }
            
            // Инициализация дашборда
            initializeDashboard();
        }

        // Обработка входа
        async function handleLogin(event) {
            event.preventDefault();
            
            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;
            const errorDiv = document.getElementById('loginError');
            
            try {
                const response = await fetch('/api/login', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ username, password })
                });
                
                const data = await response.json();
                
                if (response.ok && data.access_token) {
                    // Сохраняем токен
                    authToken = data.access_token;
                    localStorage.setItem('authToken', authToken);
                    localStorage.setItem('username', data.user.username);
                    currentUsername = data.user.username;
                    
                    // Показываем дашборд
                    showDashboard();
                    
                    errorDiv.style.display = 'none';
                } else {
                    errorDiv.textContent = data.detail || 'Неверные учетные данные';
                    errorDiv.style.display = 'block';
                }
            } catch (error) {
                errorDiv.textContent = 'Ошибка подключения к серверу';
                errorDiv.style.display = 'block';
            }
        }

        // Выход из системы
        function handleLogout() {
            localStorage.removeItem('authToken');
            localStorage.removeItem('username');
            authToken = null;
            currentUsername = null;
            
            if (wsConnection) {
                wsConnection.close();
            }
            
            showLoginForm();
        }

        // Инициализация дашборда
        function initializeDashboard() {
            connectWebSocket();
            loadBotStatus();
            loadStats();
            setupEventListeners();
            updateUptime();
            setInterval(updateUptime, 1000);
            
            addLog('[СИСТЕМА] Дашборд загружен успешно');
        }

        // WebSocket соединение
        function connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws`;
            
            addLog('[СИСТЕМА] Подключаемся к WebSocket...', 'info');
            
            wsConnection = new WebSocket(wsUrl);
            
            wsConnection.onopen = function() {
                isConnected = true;
                addLog('[СИСТЕМА] WebSocket соединение установлено', 'info');
                updateConnectionStatus(true);
                
                // Отправляем токен для аутентификации
                if (authToken) {
                    wsConnection.send(JSON.stringify({
                        type: 'auth',
                        token: authToken
                    }));
                }
                
                // Запрашиваем текущий статус
                wsConnection.send(JSON.stringify({type: 'get_status'}));
            };
            
            wsConnection.onmessage = function(event) {
                try {
                    const data = JSON.parse(event.data);
                    handleWebSocketMessage(data);
                } catch (e) {
                    console.error('Ошибка парсинга WebSocket сообщения:', e);
                }
            };
            
            wsConnection.onclose = function() {
                isConnected = false;
                addLog('[СИСТЕМА] WebSocket соединение потеряно. Переподключение...', 'warning');
                updateConnectionStatus(false);
                setTimeout(connectWebSocket, 5000);
            };
            
            wsConnection.onerror = function(error) {
                addLog('[ОШИБКА] Ошибка WebSocket: ' + error, 'error');
                console.error('WebSocket error:', error);
            };
        }

        // Обработка WebSocket сообщений
        function handleWebSocketMessage(data) {
            console.log('WebSocket message:', data);
            
            switch(data.type) {
                case 'initial_status':
                case 'status_update':
                case 'status_response':
                    updateFromStatusData(data.data);
                    break;
                    
                case 'bot_started':
                    showNotification('🚀 Бот запущен успешно!', 'success');
                    addLog('[БОТ] Бот запущен с автоматическим выбором стратегий');
                    document.getElementById('bot-status-text').textContent = 'Запускается...';
                    break;
                    
                case 'bot_stopped':
                    showNotification('🛑 Бот остановлен', 'info');
                    addLog('[БОТ] Бот остановлен');
                    updateBotStatus('stopped');
                    currentStrategies = {};
                    updateStrategyDisplay();
                    break;
                    
                case 'new_trade':
                    addTradeToTable(data.data);
                    updateStats();
                    showNotification(`💰 Новая сделка: ${data.data.symbol}`, 'info');
                    break;
                    
                case 'strategy_selected':
                    updateStrategyInfo(data.data);
                    break;
                    
                case 'settings_updated':
                    showNotification('✅ Настройки сохранены', 'success');
                    addLog('[НАСТРОЙКИ] Настройки обновлены');
                    break;
            }
        }

        // Обновление данных из статуса
        function updateFromStatusData(statusData) {
            if (!statusData) return;
            
            if (statusData.status) {
                updateBotStatus(statusData.status);
            }
            
            if (statusData.open_positions !== undefined) {
                document.getElementById('active-positions').textContent = statusData.open_positions;
            }
            
            if (statusData.statistics) {
                const stats = statusData.statistics;
                if (stats.cycles_count !== undefined) {
                    document.getElementById('cycles-count').textContent = stats.cycles_count;
                }
                if (stats.trades_today !== undefined) {
                    document.getElementById('total-trades').textContent = stats.trades_today;
                }
            }
            
            if (statusData.process_info) {
                const info = statusData.process_info;
                if (info.memory_mb) {
                    document.getElementById('memory-usage').textContent = `${info.memory_mb} MB`;
                }
            }
            
            if (statusData.active_pairs) {
                updateActivePairs(statusData.active_pairs);
            }
        }

        // Обновление информации о стратегиях
        function updateStrategyInfo(data) {
            const { symbol, strategy, confidence } = data;
            currentStrategies[symbol] = { strategy, confidence };
            
            addLog(`[СТРАТЕГИЯ] ${symbol}: выбрана ${strategy} (уверенность: ${(confidence * 100).toFixed(1)}%)`, 'info');
            updateStrategyDisplay();
        }

        // Отображение текущих стратегий
        function updateStrategyDisplay() {
            const container = document.getElementById('current-strategies');
            
            if (Object.keys(currentStrategies).length === 0) {
                container.innerHTML = '<p style="color: #7f8c8d; text-align: center; padding: 20px;">Запустите бота для отображения стратегий</p>';
                return;
            }
            
            let html = '<table class="strategy-table">';
            html += '<tr><th>Пара</th><th>Стратегия</th><th>Уверенность</th></tr>';
            
            for (const [symbol, info] of Object.entries(currentStrategies)) {
                const confidenceColor = info.confidence > 0.7 ? '#2ecc71' : 
                                       info.confidence > 0.5 ? '#f39c12' : '#e74c3c';
                html += `
                    <tr>
                        <td><strong>${symbol}</strong></td>
                        <td>${info.strategy}</td>
                        <td style="color: ${confidenceColor}">
                            ${(info.confidence * 100).toFixed(1)}%
                        </td>
                    </tr>
                `;
            }
            
            html += '</table>';
            container.innerHTML = html;
        }

        // Обновление списка активных пар
        function updateActivePairs(pairs) {
            const checkboxes = document.querySelectorAll('input[type="checkbox"]');
            checkboxes.forEach(cb => {
                const value = cb.value;
                cb.checked = pairs.includes(value);
            });
        }

        // Настройка обработчиков событий
        function setupEventListeners() {
            document.getElementById('start-bot').addEventListener('click', startBot);
            document.getElementById('stop-bot').addEventListener('click', stopBot);
        }

        // Загрузка статуса бота
        async function loadBotStatus() {
            try {
                const response = await fetch('/api/bot/status', {
                    headers: {
                        'Authorization': `Bearer ${authToken}`
                    }
                });
                
                if (response.ok) {
                    const data = await response.json();
                    updateFromStatusData(data);
                } else if (response.status === 401) {
                    handleLogout();
                }
            } catch (error) {
                addLog('[ОШИБКА] Не удалось загрузить статус бота: ' + error, 'error');
                console.error('Error loading bot status:', error);
            }
        }

        // Загрузка статистики
        async function loadStats() {
            try {
                const response = await fetch('/api/stats', {
                    headers: {
                        'Authorization': `Bearer ${authToken}`
                    }
                });
                
                if (response.ok) {
                    const data = await response.json();
                    
                    document.getElementById('total-trades').textContent = data.total_trades || 0;
                    document.getElementById('total-profit').textContent = 
                        (data.total_profit >= 0 ? '+' : '') + (data.total_profit || 0).toFixed(2) + ' USDT';
                    document.getElementById('success-rate').textContent = 
                        (data.success_rate || 0).toFixed(1) + '%';
                    
                    const profitElement = document.getElementById('total-profit').parentElement;
                    profitElement.className = 'stat-card ' + (data.total_profit >= 0 ? 'positive' : 'negative');
                    
                    loadRecentTrades();
                }
            } catch (error) {
                addLog('[ОШИБКА] Не удалось загрузить статистику: ' + error, 'error');
                console.error('Error loading stats:', error);
            }
        }

        // Загрузка последних сделок
        async function loadRecentTrades() {
            try {
                const response = await fetch('/api/trades?limit=10', {
                    headers: {
                        'Authorization': `Bearer ${authToken}`
                    }
                });
                
                if (response.ok) {
                    const data = await response.json();
                    
                    if (data.trades && data.trades.length > 0) {
                        const tbody = document.getElementById('trades-tbody');
                        tbody.innerHTML = '';
                        
                        data.trades.forEach(trade => {
                            addTradeToTable(trade);
                        });
                    }
                }
            } catch (error) {
                console.error('Error loading trades:', error);
            }
        }

        // Обновление статуса бота
        function updateBotStatus(status) {
            const statusElement = document.getElementById('bot-status-text');
            const dotElement = document.getElementById('bot-dot');
            const statusContainer = document.getElementById('bot-status');
            
            botStatus = status;
            
            const statusMap = {
                'running': { text: 'Работает', class: 'active' },
                'stopped': { text: 'Остановлен', class: '' },
                'starting': { text: 'Запускается...', class: 'active' },
                'stopping': { text: 'Останавливается...', class: '' },
                'error': { text: 'Ошибка', class: 'error' }
            };
            
            const statusInfo = statusMap[status] || statusMap['stopped'];
            
            statusElement.textContent = statusInfo.text;
            dotElement.className = 'status-dot ' + statusInfo.class;
            statusContainer.className = 'status-item ' + statusInfo.class;
            
            document.getElementById('start-bot').disabled = (status === 'running' || status === 'starting');
            document.getElementById('stop-bot').disabled = (status !== 'running');
        }

        // Обновление статуса соединения
        function updateConnectionStatus(connected) {
            const statusElement = document.getElementById('connection-status');
            const dot = statusElement.querySelector('.status-dot');
            const text = document.getElementById('connection-text');
            
            if (connected) {
                statusElement.className = 'status-item active';
                dot.className = 'status-dot active';
                text.textContent = 'Активно';
            } else {
                statusElement.className = 'status-item error';
                dot.className = 'status-dot error';
                text.textContent = 'Потеряно';
            }
        }

        // Запуск бота
        async function startBot() {
            try {
                addLog('[КОМАНДА] Запуск бота...', 'info');
                
                const response = await fetch('/api/bot/start', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${authToken}`
                    },
                    body: JSON.stringify({ 
                        strategy: 'auto'
                    })
                });
                
                const data = await response.json();
                
                if (!response.ok) {
                    throw new Error(data.detail || data.message || 'Неизвестная ошибка');
                }
                
                showNotification('🚀 Бот запускается...', 'info');
                addLog('[БОТ] Команда запуска отправлена', 'info');
                
            } catch (error) {
                showNotification('❌ Ошибка запуска бота: ' + error.message, 'error');
                addLog('[ОШИБКА] Ошибка запуска бота: ' + error.message, 'error');
                console.error('Start bot error:', error);
            }
        }

        // Остановка бота
        async function stopBot() {
            try {
                addLog('[КОМАНДА] Остановка бота...', 'info');
                
                const response = await fetch('/api/bot/stop', {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${authToken}`
                    }
                });
                
                const data = await response.json();
                
                if (!response.ok) {
                    throw new Error(data.detail || data.message || 'Неизвестная ошибка');
                }
                
                showNotification('🛑 Бот останавливается...', 'info');
                addLog('[БОТ] Команда остановки отправлена', 'info');
                
            } catch (error) {
                showNotification('❌ Ошибка остановки бота: ' + error.message, 'error');
                addLog('[ОШИБКА] Ошибка остановки бота: ' + error.message, 'error');
                console.error('Stop bot error:', error);
            }
        }

        // Сохранение торговых пар
        async function saveTradingPairs() {
            try {
                const checkboxes = document.querySelectorAll('input[type="checkbox"]:checked');
                const pairs = Array.from(checkboxes).map(cb => cb.value);
                
                if (pairs.length === 0) {
                    showNotification('⚠️ Выберите хотя бы одну пару', 'warning');
                    return;
                }
                
                const response = await fetch('/api/trading-pairs', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${authToken}`
                    },
                    body: JSON.stringify(pairs)
                });
                
                const data = await response.json();
                
                if (!response.ok) {
                    throw new Error(data.detail || 'Ошибка сохранения');
                }
                
                showNotification('✅ Торговые пары обновлены', 'success');
                addLog(`[НАСТРОЙКИ] Обновлены торговые пары: ${pairs.join(', ')}`);
                
            } catch (error) {
                showNotification('❌ Ошибка сохранения пар: ' + error.message, 'error');
                console.error('Save pairs error:', error);
            }
        }

        // Обновление времени работы
        function updateUptime() {
            const now = new Date();
            const timeStr = now.toLocaleTimeString('ru-RU');
            document.getElementById('last-cycle').textContent = timeStr;
        }

        // Добавление лога
        function addLog(message, type = 'info') {
            const logsContent = document.getElementById('logs-content');
            const logEntry = document.createElement('div');
            
            const timestamp = new Date().toLocaleTimeString('ru-RU');
            logEntry.textContent = `[${timestamp}] ${message}`;
            
            logEntry.className = 'log-entry';
            if (type === 'error') {
                logEntry.className += ' log-error';
            } else if (type === 'warning') {
                logEntry.className += ' log-warning';
            }
            
            logsContent.appendChild(logEntry);
            logsContent.scrollTop = logsContent.scrollHeight;
            
            if (logsContent.children.length > 100) {
                logsContent.removeChild(logsContent.firstChild);
            }
        }

        // Показ уведомлений
        function showNotification(message, type = 'info') {
            const notification = document.createElement('div');
            notification.className = `notification ${type}`;
            notification.textContent = message;
            
            document.body.appendChild(notification);
            
            setTimeout(() => {
                notification.classList.add('show');
            }, 100);
            
            setTimeout(() => {
                notification.classList.remove('show');
                setTimeout(() => {
                    document.body.removeChild(notification);
                }, 300);
            }, 3000);
        }

        // Добавление сделки в таблицу
        function addTradeToTable(trade) {
            const tbody = document.getElementById('trades-tbody');
            
            if (tbody.children.length === 1 && tbody.children[0].children.length === 1) {
                tbody.innerHTML = '';
            }
            
            const row = document.createElement('tr');
            const profitClass = (trade.profit || 0) >= 0 ? 'profit' : 'loss';
            
            const tradeTime = trade.created_at ? new Date(trade.created_at).toLocaleString('ru-RU') : 'N/A';
            const side = trade.side === 'BUY' ? 'Покупка' : 'Продажа';
            const status = trade.status === 'CLOSED' ? 'Завершена' : 'Активна';
            const profit = trade.profit !== null && trade.profit !== undefined ? 
                `${trade.profit >= 0 ? '+' : ''}${trade.profit.toFixed(2)} USDT` : 'N/A';
            
            row.innerHTML = `
                <td>${tradeTime}</td>
                <td>${trade.symbol}</td>
                <td>${side}</td>
                <td>${trade.quantity.toFixed(4)}</td>
                <td>$${trade.entry_price.toFixed(2)}</td>
                <td class="${profitClass}">${profit}</td>
                <td>${trade.strategy}</td>
                <td>${status}</td>
            `;
            
            tbody.insertBefore(row, tbody.firstChild);
            
            if (tbody.children.length > 50) {
                tbody.removeChild(tbody.lastChild);
            }
        }

        // Дополнительные функции
        function exportTrades() {
            showNotification('📊 Экспорт сделок...', 'info');
            window.open('/api/export/trades?format=csv', '_blank');
        }

        function clearLogs() {
            document.getElementById('logs-content').innerHTML = '';
            addLog('[СИСТЕМА] Логи очищены');
        }

        async function closeAllPositions() {
            if (confirm('Вы уверены, что хотите закрыть все открытые позиции?')) {
                try {
                    const response = await fetch('/api/bot/close-all-positions', {
                        method: 'POST',
                        headers: {
                            'Authorization': `Bearer ${authToken}`
                        }
                    });
                    
                    if (!response.ok) {
                        throw new Error('Ошибка закрытия позиций');
                    }
                    
                    showNotification('✅ Все позиции закрыты', 'success');
                } catch (error) {
                    showNotification('❌ Ошибка: ' + error.message, 'error');
                }
            }
        }

        function refreshStats() {
            loadStats();
            showNotification('🔄 Статистика обновлена', 'info');
        }

        function testNotification() {
            showNotification('🔔 Это тестовое уведомление', 'success');
        }

        function emergencyStop() {
            if (confirm('ВНИМАНИЕ! Это экстренная остановка. Все позиции будут закрыты. Продолжить?')) {
                stopBot();
                closeAllPositions();
                showNotification('🚨 Экстренная остановка выполнена', 'error');
            }
        }

        // Периодическое обновление статистики
        setInterval(() => {
            if (botStatus === 'running') {
                loadStats();
            }
        }, 30000); // Каждые 30 секунд
    </script>
</body>
</html>
    """
    
    return html