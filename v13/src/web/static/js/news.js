/**
 * News and Social Signals Dashboard
 */

class NewsManager {
    constructor() {
        this.newsContainer = document.getElementById('news-container');
        this.socialContainer = document.getElementById('social-container');
        this.refreshInterval = 60000; // 1 minute
        this.ws = null;
        this.initWebSocket();
        this.loadInitialData();
        this.startAutoRefresh();
    }

    initWebSocket() {
        this.ws = new WebSocket(`ws://${window.location.host}/ws`);
        
        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === 'news_update') {
                this.handleNewsUpdate(data.data);
            } else if (data.type === 'social_signal') {
                this.handleSocialSignal(data.data);
            }
        };

        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            setTimeout(() => this.initWebSocket(), 5000);
        };
    }

    async loadInitialData() {
        try {
            // Load news
            const newsResponse = await fetch('/api/news/latest');
            const newsData = await newsResponse.json();
            this.renderNews(newsData.news);

            // Load social signals
            const socialResponse = await fetch('/api/social/signals');
            const socialData = await socialResponse.json();
            this.renderSocialSignals(socialData.signals);

        } catch (error) {
            console.error('Error loading initial data:', error);
        }
    }

    renderNews(newsItems) {
        if (!newsItems || newsItems.length === 0) {
            this.newsContainer.innerHTML = '<p class="text-muted">No news available</p>';
            return;
        }

        const newsHtml = newsItems.map(item => `
            <div class="news-item mb-3 p-3 border rounded">
                <div class="d-flex justify-content-between align-items-start">
                    <h5 class="mb-1">${this.escapeHtml(item.title)}</h5>
                    <span class="badge ${this.getSentimentBadgeClass(item.sentiment_score)}">
                        ${this.getSentimentLabel(item.sentiment_score)}
                    </span>
                </div>
                <p class="text-muted small mb-2">
                    ${item.source} • ${this.formatDate(item.published_at)}
                    ${item.impact_score ? `• Impact: ${this.renderImpactScore(item.impact_score)}` : ''}
                </p>
                ${item.summary ? `<p class="mb-2">${this.escapeHtml(item.summary)}</p>` : ''}
                ${item.affected_coins && item.affected_coins.length > 0 ? `
                    <div class="affected-coins">
                        <strong>Affected coins:</strong>
                        ${item.affected_coins.map(coin => 
                            `<span class="badge badge-info mx-1">${coin}</span>`
                        ).join('')}
                    </div>
                ` : ''}
                ${item.url ? `<a href="${item.url}" target="_blank" class="btn btn-sm btn-outline-primary mt-2">Read more</a>` : ''}
            </div>
        `).join('');

        this.newsContainer.innerHTML = newsHtml;
    }

    renderSocialSignals(signals) {
        if (!signals || signals.length === 0) {
            this.socialContainer.innerHTML = '<p class="text-muted">No social signals available</p>';
            return;
        }

        const signalsHtml = signals.map(signal => `
            <div class="social-signal mb-3 p-3 border rounded ${signal.influence_score > 7 ? 'border-warning' : ''}">
                <div class="d-flex justify-content-between align-items-start">
                    <div>
                        <span class="badge badge-${this.getPlatformBadgeClass(signal.platform)}">
                            ${signal.platform}
                        </span>
                        ${signal.is_verified_author ? '<i class="fas fa-check-circle text-primary ml-2"></i>' : ''}
                    </div>
                    <span class="badge ${this.getSentimentBadgeClass(signal.sentiment)}">
                        ${this.getSentimentLabel(signal.sentiment)}
                    </span>
                </div>
                <p class="mb-2 mt-2">${this.escapeHtml(signal.content)}</p>
                <div class="signal-meta text-muted small">
                    ${signal.author ? `<span>@${signal.author}</span>` : ''}
                    ${signal.author_followers ? `<span class="ml-2">${this.formatNumber(signal.author_followers)} followers</span>` : ''}
                    ${signal.influence_score ? `<span class="ml-2">Influence: ${signal.influence_score.toFixed(1)}/10</span>` : ''}
                    <span class="ml-2">${this.formatDate(signal.created_at)}</span>
                </div>
                ${signal.mentioned_coins && signal.mentioned_coins.length > 0 ? `
                    <div class="mentioned-coins mt-2">
                        ${signal.mentioned_coins.map(coin => 
                            `<span class="badge badge-secondary mx-1">${coin}</span>`
                        ).join('')}
                    </div>
                ` : ''}
            </div>
        `).join('');

        this.socialContainer.innerHTML = signalsHtml;
    }

    handleNewsUpdate(news) {
        // Prepend new news item
        const currentNews = this.newsContainer.innerHTML;
        const newNewsHtml = this.renderSingleNews(news);
        this.newsContainer.innerHTML = newNewsHtml + currentNews;
        
        // Highlight new item
        const firstItem = this.newsContainer.firstElementChild;
        firstItem.classList.add('new-item-highlight');
        setTimeout(() => firstItem.classList.remove('new-item-highlight'), 3000);
    }

    handleSocialSignal(signal) {
        // Similar to handleNewsUpdate
        const currentSignals = this.socialContainer.innerHTML;
        const newSignalHtml = this.renderSingleSignal(signal);
        this.socialContainer.innerHTML = newSignalHtml + currentSignals;
        
        const firstItem = this.socialContainer.firstElementChild;
        firstItem.classList.add('new-item-highlight');
        setTimeout(() => firstItem.classList.remove('new-item-highlight'), 3000);
    }

    renderSingleNews(item) {
        // Same as news item in renderNews method
        return `<div class="news-item mb-3 p-3 border rounded">...</div>`;
    }

    renderSingleSignal(signal) {
        // Same as signal item in renderSocialSignals method
        return `<div class="social-signal mb-3 p-3 border rounded">...</div>`;
    }

    getSentimentBadgeClass(sentiment) {
        if (sentiment > 0.3) return 'badge-success';
        if (sentiment < -0.3) return 'badge-danger';
        return 'badge-secondary';
    }

    getSentimentLabel(sentiment) {
        if (sentiment > 0.3) return 'Positive';
        if (sentiment < -0.3) return 'Negative';
        return 'Neutral';
    }

    getPlatformBadgeClass(platform) {
        const classes = {
            'twitter': 'info',
            'reddit': 'warning',
            'telegram': 'primary'
        };
        return classes[platform.toLowerCase()] || 'secondary';
    }

    renderImpactScore(score) {
        const stars = '★'.repeat(Math.round(score / 2)) + '☆'.repeat(5 - Math.round(score / 2));
        return `<span class="impact-score">${stars}</span>`;
    }

    formatDate(dateString) {
        const date = new Date(dateString);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffMins < 1440) return `${Math.floor(diffMins / 60)}h ago`;
        return date.toLocaleDateString();
    }

    formatNumber(num) {
        if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
        if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
        return num.toString();
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    startAutoRefresh() {
        setInterval(() => this.loadInitialData(), this.refreshInterval);
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.newsManager = new NewsManager();
});