// frontend/js/api.js
const API = {
    baseUrl: '',

    async request(endpoint, method, body, requiresAuth = false) {
        const headers = {
            'Content-Type': 'application/json',
        };

        if (requiresAuth) {
            const token = Auth.getToken();
            if (token) {
                headers['Authorization'] = `Bearer ${token}`;
            } else {
                throw new Error('No authentication token');
            }
        }

        const response = await fetch(`${this.baseUrl}${endpoint}`, {
            method,
            headers,
            body: body ? JSON.stringify(body) : undefined,
        });

        const data = await response.json();

        // Логируем ответ для отладки (НО НЕ В ПРОДАКШЕНЕ!)
        console.log(`API Response ${endpoint}:`, { ok: response.ok, data });

        return { ok: response.ok, data };
    },

    login(email, password) {
        return this.request('/login', 'POST', { email, password });
    },

    register(email, password) {
        const username = email.split('@')[0];
        return this.request('/register', 'POST', {
            email,
            password,
            username
        });
    },

    getMe() {
        return this.request('/me', 'GET', null, true);
    },

    humanize(text, intensity, tone, style, length, targetLanguage = 'ru') {
        return this.request('/humanize', 'POST', {
            text,
            intensity,
            tone,
            style,
            length,
            target_language: targetLanguage
        }, true);
    }
};