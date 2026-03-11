/**
 * Gemini API Client (v2)
 * Handles model cascading, rate limiting, quota UI, and browser-direct file uploads.
 */
class GeminiClient {
    constructor(config = {}) {
        this.config = {
            needsRealTimeData: false,
            fallbackModel: 'gemini-2.5-flash',
            primaryModel: 'gemini-2.5-pro',
            ...config
        };
        
        // Define rate limits per tier
        this.limits = {
            free: {
                requestsPerMin: 15,
                tokensPerMin: 1000000,
                requestsPerDay: 1500
            }
        };

        this.apiKey = localStorage.getItem('gemini_api_key') || null;
        this.selectedMode = 'pro';
        this.selectedModel = this.config.primaryModel;
        
        this.initQuotaTracking();
        this.initUI();
    }

    setApiKey(key) {
        if (key) {
            this.apiKey = key;
            localStorage.setItem('gemini_api_key', key);
        } else {
            this.apiKey = null;
            localStorage.removeItem('gemini_api_key');
        }
    }

    setMode(mode) {
        this.selectedMode = mode;
        if (mode === 'pro') {
            document.getElementById('mode-pro').classList.replace('btn-outline-info', 'btn-info');
            document.getElementById('mode-pro').style.color = '#05080f';
            document.getElementById('mode-fast').classList.replace('btn-info', 'btn-outline-info');
            document.getElementById('mode-fast').style.color = '';
            
            const select = document.getElementById('model-select');
            // Prefer user's dropdown choice if it's a "pro" model, else default
            this.selectedModel = select.value.includes('pro') ? select.value : this.config.primaryModel;
            select.value = this.selectedModel;
            select.disabled = false;
        } else {
            document.getElementById('mode-fast').classList.replace('btn-outline-info', 'btn-info');
            document.getElementById('mode-fast').style.color = '#05080f';
            document.getElementById('mode-pro').classList.replace('btn-info', 'btn-outline-info');
            document.getElementById('mode-pro').style.color = '';
            
            const select = document.getElementById('model-select');
            this.selectedModel = this.config.fallbackModel;
            select.value = this.selectedModel;
            // Disable dropdown in fast mode normally, but user might want to pick a specific flash version
            select.disabled = true;
            
            // Temporary add the option if it doesn't exist
            let exists = Array.from(select.options).some(o => o.value === this.config.fallbackModel);
            if (!exists) {
                const opt = new Option('Gemini 2.5 Flash', this.config.fallbackModel);
                select.options.add(opt);
                select.value = this.config.fallbackModel;
            }
        }
    }

    initUI() {
        const proBtn = document.getElementById('mode-pro');
        const fastBtn = document.getElementById('mode-fast');
        const select = document.getElementById('model-select');
        const apiKeyInput = document.getElementById('api-key-input');

        if (apiKeyInput && this.apiKey) {
            apiKeyInput.value = this.apiKey;
        }

        if (apiKeyInput) {
            apiKeyInput.addEventListener('change', (e) => {
                this.setApiKey(e.target.value.trim());
            });
        }

        if (proBtn) {
            proBtn.addEventListener('click', () => this.setMode('pro'));
        }
        if (fastBtn) {
            fastBtn.addEventListener('click', () => this.setMode('fast'));
        }
        if (select) {
            select.addEventListener('change', (e) => {
                this.selectedModel = e.target.value;
                if (!e.target.value.includes('pro')) {
                    this.setMode('fast');
                } else {
                    this.setMode('pro');
                }
            });
        }
        
        this.updateQuotaUI();
    }

    initQuotaTracking() {
        const stored = localStorage.getItem('qpg_rate_limits');
        if (stored) {
            try {
                this.quota = JSON.parse(stored);
                // Reset if it's a new day
                const lastUsed = new Date(this.quota.lastRequestTime);
                const now = new Date();
                if (lastUsed.getDate() !== now.getDate() || lastUsed.getMonth() !== now.getMonth()) {
                     this.quota.requestsToday = 0;
                }
                
                // Clear minute tracking if > 1 minute passed
                if (now.getTime() - lastUsed.getTime() > 60000) {
                     this.quota.requestsThisMinute = 0;
                     this.quota.tokensThisMinute = 0;
                }
            } catch (e) {
                this._resetQuota();
            }
        } else {
            this._resetQuota();
        }
    }

    _resetQuota() {
        this.quota = {
            requestsThisMinute: 0,
            tokensThisMinute: 0,
            requestsToday: 0,
            lastRequestTime: new Date().toISOString()
        };
        this._saveQuota();
    }

    _saveQuota() {
        localStorage.setItem('qpg_rate_limits', JSON.stringify(this.quota));
        this.updateQuotaUI();
    }

    _trackUsage(modelName) {
        this.initQuotaTracking(); // Refresh to catch minute boundaries
        this.quota.requestsThisMinute++;
        this.quota.requestsToday++;
        this.quota.lastRequestTime = new Date().toISOString();
        this._saveQuota();
    }

    updateQuotaUI() {
        const quotaText = document.getElementById('quota-text');
        const quotaBar = document.getElementById('quota-fill');
        
        if (!quotaText || !quotaBar) return;

        const maxReq = this.limits.free.requestsPerMin;
        const used = this.quota.requestsThisMinute;
        const remaining = Math.max(0, maxReq - used);
        const percentage = Math.max(5, (remaining / maxReq) * 100); // Keep at least 5% visible

        quotaText.textContent = `Quota: ${remaining} / ${maxReq}`;
        quotaBar.style.width = `${percentage}%`;

        // Colors based on usage
        if (percentage > 50) {
            quotaBar.className = 'progress-bar bg-info';
            quotaText.className = 'badge bg-info text-dark';
        } else if (percentage > 20) {
            quotaBar.className = 'progress-bar bg-warning';
            quotaText.className = 'badge bg-warning text-dark';
        } else {
            quotaBar.className = 'progress-bar bg-danger';
            quotaText.className = 'badge bg-danger';
        }
    }

    /**
     * Get headers required for proxy API calls
     */
    getAuthHeaders() {
        const headers = {
            'X-Gemini-Model-Name': this.selectedModel
        };
        if (this.apiKey) {
            headers['X-Gemini-Api-Key'] = this.apiKey;
        }
        return headers;
    }

    /**
     * Checks if we are currently rate limited
     */
    isRateLimited() {
        this.initQuotaTracking();
        return this.quota.requestsThisMinute >= this.limits.free.requestsPerMin;
    }
}

// Initialize on load
window.addEventListener('DOMContentLoaded', () => {
    window.gemini = new GeminiClient(window.GEMINI_CONFIG || {});
    
    // Override main.js getApiHeaders functionality.
    window.getApiHeaders = () => window.gemini.getAuthHeaders();
});
