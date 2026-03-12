/**
 * Gemini API Client (v2)
 * Handles custom user API keys and basic auth headers.
 * Server-side logic now exclusively manages Model selection and Fallback cascading.
 */
class GeminiClient {
    constructor(config = {}) {
        this.apiKey = localStorage.getItem('gemini_api_key') || null;
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

    getApiKey() {
        return this.apiKey;
    }

    initUI() {
        const apiKeyInput = document.getElementById('api-key-input');
        if (apiKeyInput && this.apiKey) {
            apiKeyInput.value = this.apiKey;
        }

        if (apiKeyInput) {
            apiKeyInput.addEventListener('change', (e) => {
                this.setApiKey(e.target.value.trim());
            });
        }
    }

    /**
     * Get headers required for proxy API calls
     */
    getAuthHeaders() {
        const headers = {};
        if (this.apiKey) {
            headers['X-Gemini-Api-Key'] = this.apiKey;
        }
        return headers;
    }
}

// Initialize on load
window.addEventListener('DOMContentLoaded', () => {
    window.gemini = new GeminiClient(window.GEMINI_CONFIG || {});
    
    // Override main.js getApiHeaders functionality.
    window.getApiHeaders = () => window.gemini.getAuthHeaders();
});
