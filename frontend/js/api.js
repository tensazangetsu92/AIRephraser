const API = {
    baseUrl: '',

    async request(endpoint, method, body, requiresAuth = false) {
        const headers = { 'Content-Type': 'application/json' };

        if (requiresAuth) {
            const token = await Auth.getValidAccessToken();
            if (token) {
                headers['Authorization'] = `Bearer ${token}`;
            } else {
                throw new Error('No authentication token');
            }
        }

        const requestOptions = {
            method,
            headers,
            body: body ? JSON.stringify(body) : undefined,
            credentials: 'same-origin',
        };
        let response = await fetch(`${this.baseUrl}${endpoint}`, requestOptions);

        if (requiresAuth && response.status === 401) {
            const token = await Auth.refreshAccessToken();
            if (token) {
                requestOptions.headers = { ...headers, Authorization: `Bearer ${token}` };
                response = await fetch(`${this.baseUrl}${endpoint}`, requestOptions);
            }
        }

        let data;
        try {
            data = await response.json();
        } catch {
            data = { detail: 'Сервер вернул некорректный ответ. Попробуйте ещё раз.' };
        }
        if (requiresAuth && response.status === 401) {
            Auth.clearExpiredSession();
        }
        const retryAfter = Number(response.headers.get('Retry-After'));
        return {
            ok: response.ok,
            status: response.status,
            data,
            retryAfter: Number.isFinite(retryAfter) && retryAfter > 0 ? retryAfter : null,
        };
    },

    getMe() {
        return this.request('/me', 'GET', null, true);
    },

    humanize(text, style, targetLanguage = 'ru') {
        return this.request('/humanize', 'POST', {
            text,
            style,
            target_language: targetLanguage
        }, true);
    },

    requestEmailCode(email) {
        return this.request('/auth/email-code/request', 'POST', { email });
    },

    confirmEmailCode(email, code) {
        return this.request('/auth/email-code/confirm', 'POST', { email, code });
    },

    prepareStudyWork(text, workType) {
        return this.request('/study-work/process', 'POST', {
            text,
            style: 'academic',
            academic_work_type: workType
        }, true);
    },

    detect(text) {
        return this.request('/detect', 'POST', { text }, true);
    },

    paraphrase(text, style) {
        return this.request('/paraphrase', 'POST', { text, style }, true);
    },

    saveHistory(toolType, originalText, resultText) {
        return this.request('/user/history/save', 'POST', {
            tool_type: toolType,
            original_text: originalText,
            result_text: resultText
        }, true);
    }

};
