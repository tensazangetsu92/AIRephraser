const API = {
    baseUrl: '',

    async request(endpoint, method, body, requiresAuth = false) {
        const headers = { 'Content-Type': 'application/json' };

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
        return { ok: response.ok, status: response.status, data };
    },

    login(email, password) {
        return this.request('/login', 'POST', { email, password });
    },

    register(email, password) {
        return this.request('/register', 'POST', {
            email,
            password,
            username: email.split('@')[0]
        });
    },

    getMe() {
        return this.request('/me', 'GET', null, true);
    },

    humanize(text, intensity, tone, style, length) {
        return this.request('/humanize', 'POST', { text, intensity, tone, style, length }, true);
    },

    detect(text) {
        return this.request('/detect', 'POST', { text }, true);
    },

    paraphrase(text, tone, style) {
        return this.request('/paraphrase', 'POST', { text, tone, style }, true);
    },

    checkGrammar(text) {
        return this.request('/grammar', 'POST', { text }, true);
    },

    saveHistory(toolType, originalText, resultText) {
        return this.request('/user/history/save', 'POST', {
            tool_type: toolType,
            original_text: originalText,
            result_text: resultText
        }, true);
    },

    sendVerification(email, password) {
        return this.request('/auth/send-verification', 'POST', { email, password });
    },

    verifyCode(email, code) {
        return this.request('/auth/verify-code', 'POST', { email, code });
    },
};