/**
 * Модуль аналитики и визуализации данных
 * Файл: src/web/static/js/analytics.js
 */

class AnalyticsManager {
    constructor() {
        this.charts = {};
        this.updateInterval = 30000; // 30 секунд
        this.updateTimer = null;
        this.ws = null;
    }

    /**
     * Инициализация модуля аналитики
     */
    async init() {
        console.log('Инициализация AnalyticsManager...');
        
        // Загружаем начальные данные
        await this.loadInitialData();
        
        // Создаем графики
        this.createCharts();
        
        // Настраиваем обновления
        this.setupAutoUpdate();
        
        // Подключаемся к WebSocket для real-time обновлений
        this.connectWebSocket();
        
        // Настраиваем обработчики событий
        this.setupEventHandlers();
    }

    /**
     * Загрузка начальных данных
     */
    async loadInitialData() {
        try {
            // Загружаем все необходимые данные параллельно
            const [performance, trades, mlMetrics, riskMetrics] = await Promise.all([
                fetch('/api/performance').then(r => r.json()),
                fetch('/api/trades/recent').then(r => r.json()),
                fetch('/api/ml/metrics').then(r => r.json()),
                fetch('/api/risk/metrics').then(r => r.json())
            ]);

            this.data = {
                performance,
                trades,
                mlMetrics,
                riskMetrics
            };

        } catch (error) {
            console.error('Ошибка загрузки данных:', error);
            this.showError('Не удалось загрузить данные аналитики');
        }
    }

    /**
     * Создание всех графиков
     */
    createCharts() {
        // График P&L
        this.createPnLChart();
        
        // График Win Rate по стратегиям
        this.createWinRateChart();
        
        // График производительности ML моделей
        this.createMLPerformanceChart();
        
        // График распределения рисков
        this.createRiskDistributionChart();
        
        // Тепловая карта корреляций
        this.createCorrelationHeatmap();
        
        // График drawdown
        this.createDrawdownChart();
    }

    /**
     * График прибыли и убытков
     */
    createPnLChart() {
        const ctx = document.getElementById('pnl-chart');
        if (!ctx) return;

        const data = this.preparePnLData();
        
        this.charts.pnl = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.labels,
                datasets: [{
                    label: 'Накопленная прибыль',
                    data: data.cumulative,
                    borderColor: 'rgb(75, 192, 192)',
                    backgroundColor: 'rgba(75, 192, 192, 0.1)',
                    tension: 0.1,
                    fill: true
                }, {
                    label: 'Дневная прибыль',
                    data: data.daily,
                    borderColor: 'rgb(255, 159, 64)',
                    backgroundColor: 'rgba(255, 159, 64, 0.1)',
                    type: 'bar',
                    yAxisID: 'y1'
                }]
            },
            options: {
                responsive: true,
                interaction: {
                    mode: 'index',
                    intersect: false,
                },
                plugins: {
                    title: {
                        display: true,
                        text: 'Прибыль и убытки'
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                let label = context.dataset.label || '';
                                if (label) {
                                    label += ': ';
                                }
                                label += '$' + context.parsed.y.toFixed(2);
                                return label;
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        title: {
                            display: true,
                            text: 'Накопленная P&L ($)'
                        }
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        title: {
                            display: true,
                            text: 'Дневная P&L ($)'
                        },
                        grid: {
                            drawOnChartArea: false
                        }
                    }
                }
            }
        });
    }

    /**
     * График Win Rate по стратегиям
     */
    createWinRateChart() {
        const ctx = document.getElementById('winrate-chart');
        if (!ctx) return;

        const data = this.prepareWinRateData();
        
        this.charts.winRate = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.strategies,
                datasets: [{
                    label: 'Win Rate (%)',
                    data: data.winRates,
                    backgroundColor: data.winRates.map(rate => 
                        rate >= 60 ? 'rgba(75, 192, 192, 0.6)' :
                        rate >= 50 ? 'rgba(255, 205, 86, 0.6)' :
                        'rgba(255, 99, 132, 0.6)'
                    ),
                    borderColor: data.winRates.map(rate => 
                        rate >= 60 ? 'rgb(75, 192, 192)' :
                        rate >= 50 ? 'rgb(255, 205, 86)' :
                        'rgb(255, 99, 132)'
                    ),
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: 'Win Rate по стратегиям'
                    },
                    datalabels: {
                        anchor: 'end',
                        align: 'end',
                        formatter: (value) => value.toFixed(1) + '%'
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        title: {
                            display: true,
                            text: 'Win Rate (%)'
                        }
                    }
                }
            }
        });
    }

    /**
     * График производительности ML моделей
     */
    createMLPerformanceChart() {
        const ctx = document.getElementById('ml-performance-chart');
        if (!ctx) return;

        const data = this.prepareMLData();
        
        this.charts.mlPerformance = new Chart(ctx, {
            type: 'radar',
            data: {
                labels: ['Точность', 'Precision', 'Recall', 'F1-Score', 'Уверенность'],
                datasets: data.models.map((model, index) => ({
                    label: model.name,
                    data: [
                        model.accuracy * 100,
                        model.precision * 100,
                        model.recall * 100,
                        model.f1_score * 100,
                        model.avg_confidence * 100
                    ],
                    borderColor: this.getColor(index),
                    backgroundColor: this.getColor(index, 0.2),
                    pointBackgroundColor: this.getColor(index),
                    pointBorderColor: '#fff',
                    pointHoverBackgroundColor: '#fff',
                    pointHoverBorderColor: this.getColor(index)
                }))
            },
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: 'Производительность ML моделей'
                    }
                },
                scales: {
                    r: {
                        beginAtZero: true,
                        max: 100,
                        ticks: {
                            callback: function(value) {
                                return value + '%';
                            }
                        }
                    }
                }
            }
        });
    }

    /**
     * График распределения рисков
     */
    createRiskDistributionChart() {
        const ctx = document.getElementById('risk-distribution-chart');
        if (!ctx) return;

        const data = this.prepareRiskData();
        
        this.charts.riskDistribution = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: data.labels,
                datasets: [{
                    data: data.values,
                    backgroundColor: [
                        'rgba(75, 192, 192, 0.8)',
                        'rgba(54, 162, 235, 0.8)',
                        'rgba(255, 206, 86, 0.8)',
                        'rgba(255, 99, 132, 0.8)',
                        'rgba(153, 102, 255, 0.8)'
                    ],
                    borderColor: [
                        'rgba(75, 192, 192, 1)',
                        'rgba(54, 162, 235, 1)',
                        'rgba(255, 206, 86, 1)',
                        'rgba(255, 99, 132, 1)',
                        'rgba(153, 102, 255, 1)'
                    ],
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: 'Распределение капитала по рискам'
                    },
                    legend: {
                        position: 'right'
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const label = context.label || '';
                                const value = context.parsed;
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = ((value / total) * 100).toFixed(1);
                                return `${label}: $${value.toFixed(2)} (${percentage}%)`;
                            }
                        }
                    }
                }
            }
        });
    }

    /**
     * Тепловая карта корреляций
     */
    createCorrelationHeatmap() {
        const container = document.getElementById('correlation-heatmap');
        if (!container) return;

        const data = this.prepareCorrelationData();
        
        const trace = {
            x: data.symbols,
            y: data.symbols,
            z: data.correlations,
            type: 'heatmap',
            colorscale: 'RdBu',
            reversescale: true,
            zmin: -1,
            zmax: 1,
            colorbar: {
                title: 'Корреляция',
                titleside: 'right'
            }
        };

        const layout = {
            title: 'Корреляционная матрица активов',
            xaxis: {
                side: 'bottom'
            },
            yaxis: {
                autorange: 'reversed'
            },
            paper_bgcolor: '#1e222d',
            plot_bgcolor: '#1e222d',
            font: {
                color: '#d1d4dc'
            }
        };

        Plotly.newPlot(container, [trace], layout, {responsive: true});
        this.charts.correlation = container;
    }

    /**
     * График просадки (Drawdown)
     */
    createDrawdownChart() {
        const ctx = document.getElementById('drawdown-chart');
        if (!ctx) return;

        const data = this.prepareDrawdownData();
        
        this.charts.drawdown = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.labels,
                datasets: [{
                    label: 'Drawdown (%)',
                    data: data.values,
                    borderColor: 'rgb(255, 99, 132)',
                    backgroundColor: 'rgba(255, 99, 132, 0.1)',
                    fill: true,
                    tension: 0.1
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: 'Максимальная просадка'
                    },
                    annotation: {
                        annotations: {
                            maxDrawdown: {
                                type: 'line',
                                yMin: data.maxDrawdown,
                                yMax: data.maxDrawdown,
                                borderColor: 'rgb(255, 99, 132)',
                                borderWidth: 2,
                                borderDash: [5, 5],
                                label: {
                                    content: `Max: ${data.maxDrawdown.toFixed(2)}%`,
                                    enabled: true,
                                    position: 'end'
                                }
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        title: {
                            display: true,
                            text: 'Drawdown (%)'
                        },
                        reverse: true
                    }
                }
            }
        });
    }

    /**
     * Подготовка данных для графиков
     */
    preparePnLData() {
        const trades = this.data.trades || [];
        const dailyPnL = {};
        let cumulative = 0;
        
        trades.forEach(trade => {
            if (trade.closed_at && trade.profit !== null) {
                const date = new Date(trade.closed_at).toLocaleDateString();
                dailyPnL[date] = (dailyPnL[date] || 0) + trade.profit;
            }
        });
        
        const sortedDates = Object.keys(dailyPnL).sort();
        const cumulativeData = [];
        const dailyData = [];
        
        sortedDates.forEach(date => {
            cumulative += dailyPnL[date];
            cumulativeData.push(cumulative);
            dailyData.push(dailyPnL[date]);
        });
        
        return {
            labels: sortedDates,
            cumulative: cumulativeData,
            daily: dailyData
        };
    }

    prepareWinRateData() {
        const performance = this.data.performance || {};
        const strategies = Object.keys(performance.by_strategy || {});
        const winRates = strategies.map(strategy => 
            (performance.by_strategy[strategy].win_rate || 0) * 100
        );
        
        return { strategies, winRates };
    }

    prepareMLData() {
        const mlMetrics = this.data.mlMetrics || {};
        return {
            models: mlMetrics.models || []
        };
    }

    prepareRiskData() {
        const riskMetrics = this.data.riskMetrics || {};
        const positions = riskMetrics.position_distribution || {};
        
        return {
            labels: Object.keys(positions),
            values: Object.values(positions)
        };
    }

    prepareCorrelationData() {
        const symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'DOGEUSDT'];
        const n = symbols.length;
        const correlations = [];
        
        // Генерируем симметричную матрицу корреляций
        for (let i = 0; i < n; i++) {
            correlations[i] = [];
            for (let j = 0; j < n; j++) {
                if (i === j) {
                    correlations[i][j] = 1;
                } else if (i < j) {
                    correlations[i][j] = Math.random() * 0.8 - 0.2;
                } else {
                    correlations[i][j] = correlations[j][i];
                }
            }
        }
        
        return { symbols, correlations };
    }

    prepareDrawdownData() {
        const performance = this.data.performance || {};
        const equity = performance.equity_curve || [];
        const drawdowns = [];
        let peak = 0;
        let maxDrawdown = 0;
        
        equity.forEach(point => {
            if (point.value > peak) {
                peak = point.value;
            }
            const drawdown = ((peak - point.value) / peak) * 100;
            drawdowns.push(drawdown);
            maxDrawdown = Math.max(maxDrawdown, drawdown);
        });
        
        return {
            labels: equity.map(p => new Date(p.timestamp).toLocaleDateString()),
            values: drawdowns,
            maxDrawdown
        };
    }

    /**
     * Настройка автообновления
     */
    setupAutoUpdate() {
        this.updateTimer = setInterval(() => {
            this.updateAllCharts();
        }, this.updateInterval);
    }

    /**
     * Обновление всех графиков
     */
    async updateAllCharts() {
        await this.loadInitialData();
        
        // Обновляем каждый график
        Object.keys(this.charts).forEach(chartName => {
            const updateMethod = `update${chartName.charAt(0).toUpperCase() + chartName.slice(1)}Chart`;
            if (typeof this[updateMethod] === 'function') {
                this[updateMethod]();
            }
        });
    }

    /**
     * WebSocket подключение
     */
    connectWebSocket() {
        const wsUrl = `ws://${window.location.host}/ws`;
        
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            
            if (data.type === 'analytics_update') {
                this.handleRealtimeUpdate(data.payload);
            }
        };
    }

    /**
     * Обработка real-time обновлений
     */
    handleRealtimeUpdate(update) {
        // Обновляем соответствующие метрики
        if (update.metric === 'trade_closed') {
            this.updatePnLChart();
            this.updateWinRateChart();
        } else if (update.metric === 'ml_prediction') {
            this.updateMLPerformanceChart();
        } else if (update.metric === 'risk_update') {
            this.updateRiskDistributionChart();
        }
    }

    /**
     * Настройка обработчиков событий
     */
    setupEventHandlers() {
        // Переключение периода
        document.querySelectorAll('.period-selector').forEach(selector => {
            selector.addEventListener('change', (e) => {
                this.changePeriod(e.target.value);
            });
        });

        // Экспорт данных
        const exportBtn = document.getElementById('export-analytics');
        if (exportBtn) {
            exportBtn.addEventListener('click', () => {
                this.exportData();
            });
        }

        // Фильтры
        document.querySelectorAll('.analytics-filter').forEach(filter => {
            filter.addEventListener('change', () => {
                this.applyFilters();
            });
        });
    }

    /**
     * Смена периода отображения
     */
    changePeriod(period) {
        // Перезагружаем данные с новым периодом
        this.loadInitialData().then(() => {
            this.updateAllCharts();
        });
    }

    /**
     * Экспорт данных
     */
    exportData() {
        const data = {
            timestamp: new Date().toISOString(),
            performance: this.data.performance,
            trades: this.data.trades,
            mlMetrics: this.data.mlMetrics,
            riskMetrics: this.data.riskMetrics
        };

        const blob = new Blob([JSON.stringify(data, null, 2)], {
            type: 'application/json'
        });
        
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `analytics_export_${new Date().toISOString().split('T')[0]}.json`;
        a.click();
        URL.revokeObjectURL(url);
    }

    /**
     * Получение цвета для графиков
     */
    getColor(index, alpha = 1) {
        const colors = [
            `rgba(75, 192, 192, ${alpha})`,
            `rgba(255, 99, 132, ${alpha})`,
            `rgba(54, 162, 235, ${alpha})`,
            `rgba(255, 206, 86, ${alpha})`,
            `rgba(153, 102, 255, ${alpha})`
        ];
        return colors[index % colors.length];
    }

    /**
     * Показ ошибки
     */
    showError(message) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'alert alert-danger';
        errorDiv.textContent = message;
        
        const container = document.querySelector('.analytics-container');
        if (container) {
            container.insertBefore(errorDiv, container.firstChild);
            setTimeout(() => errorDiv.remove(), 5000);
        }
    }
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    window.analyticsManager = new AnalyticsManager();
    window.analyticsManager.init();
});