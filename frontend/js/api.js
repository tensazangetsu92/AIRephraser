// frontend/js/api.js
const API = {
    async request(endpoint, method = 'GET', data = null, token = null) {
        const headers = {
            'Content-Type': 'application/json'
        };

        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        const config = {
            method,
            headers
        };

        if (data) {
            config.body = JSON.stringify(data);
        }

        try {
            const response = await fetch(endpoint, config);
            const responseData = await response.json();

            return {
                ok: response.ok,
                status: response.status,
                data: responseData
            };
        } catch (error) {
            console.error('API Error:', error);
            return {
                ok: false,
                status: 500,
                data: { error: 'Ошибка соединения' }
            };
        }
    },

    login(email, password) {
        return this.request('/login', 'POST', { email, password });
    },

    register(username, email, password) {
        return this.request('/register', 'POST', { username, email, password });
    },

    humanize(text, intensity, tone, style, length, token) {
        return this.request('/humanize', 'POST', {
            text,
            intensity,
            tone,
            style,
            length,
            target_language: 'ru'
        }, token);
    }
};