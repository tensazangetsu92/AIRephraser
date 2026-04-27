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

    logout() {
        this.setToken(null);
        this.setUser(null);
    },

    isAuthenticated() {
        return !!this.token;
    }
};