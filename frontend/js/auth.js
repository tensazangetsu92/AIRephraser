// frontend/js/auth.js
const Auth = {
    token: localStorage.getItem('token'),

    getToken() {
        return this.token;
    },

    setToken(token) {
        this.token = token;
        if (token) {
            localStorage.setItem('token', token);
            console.log('Token saved:', token.substring(0, 20) + '...');
        } else {
            localStorage.removeItem('token');
        }
    },

    getUser() {
        const user = localStorage.getItem('user');
        return user ? JSON.parse(user) : null;
    },

    setUser(user) {
        if (user) {
            localStorage.setItem('user', JSON.stringify(user));
            console.log('User saved:', user);
        } else {
            localStorage.removeItem('user');
        }
    },

    async login(email, password) {
        const result = await API.login(email, password);

        if (result.ok) {
            this.setToken(result.data.access_token);
            this.setUser(result.data.user);
            return { success: true, user: result.data.user };
        } else {
            return { success: false, error: result.data.detail || 'Ошибка входа' };
        }
    },

    async register(username, email, password) {
        const result = await API.register(username, email, password);

        if (result.ok) {
            return { success: true, message: result.data.message };
        } else {
            return { success: false, error: result.data.detail || 'Ошибка регистрации' };
        }
    },

    // Google OAuth
    loginWithGoogle() {
        window.location.href = '/auth/google/login';
    },

    // Обработка Google токена из URL
    async handleGoogleCallback() {
        const urlParams = new URLSearchParams(window.location.search);
        const googleToken = urlParams.get('token');

        console.log('Checking Google token in URL:', googleToken ? 'Found!' : 'Not found');

        if (googleToken) {
            this.setToken(googleToken);

            try {
                // Получаем данные пользователя
                console.log('Fetching user data from /me...');
                const response = await fetch('/me', {
                    headers: { 'Authorization': `Bearer ${googleToken}` }
                });

                console.log('/me response status:', response.status);

                const data = await response.json();
                console.log('/me response data:', data);

                if (data.success && data.user) {
                    this.setUser(data.user);
                    // Убираем токен из URL
                    window.history.replaceState({}, document.title, window.location.pathname);
                    // Обновляем UI
                    if (typeof updateUI === 'function') {
                        updateUI();
                    }
                    alert('✅ Вход через Google выполнен успешно!');
                } else {
                    console.error('No user data in response:', data);
                    alert('❌ Не удалось получить данные пользователя');
                }
            } catch (err) {
                console.error('Google auth error:', err);
                alert('❌ Ошибка при входе через Google');
            }

            return true;
        }
        return false;
    },

    logout() {
        this.setToken(null);
        this.setUser(null);
    },

    isAuthenticated() {
        return !!this.token;
    }
};

// Автоматически проверяем Google callback при загрузке
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOMContentLoaded - checking Google callback');
    Auth.handleGoogleCallback();
});