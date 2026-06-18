const Auth = {
    token: localStorage.getItem('token'),
    isRegisterMode: false,
    pendingEmail: null,
    pendingPassword: null,

    getToken() { return this.token; },

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

    isAuthenticated() { return !!this.token; },

    async login(email, password) {
        const result = await API.login(email, password);
        if (result.ok) {
            this.setToken(result.data.access_token);
            this.setUser(result.data.user);
            this.closeAuthModal();
            if (typeof updateUI === 'function') updateUI();
            if (typeof updateUserMenu === 'function') updateUserMenu();
            return { success: true, user: result.data.user };
        }
        return { success: false, error: result.data.detail || 'Ошибка входа' };
    },

    loginWithGoogle() {
        window.location.href = '/auth/google/login';
    },

    async handleGoogleCallback() {
        const urlParams = new URLSearchParams(window.location.search);
        const googleToken = urlParams.get('token');
        if (!googleToken) return false;

        this.setToken(googleToken);

        try {
            const response = await fetch('/me', {
                headers: { 'Authorization': `Bearer ${googleToken}` }
            });
            const data = await response.json();

            if (data.success && data.user) {
                this.setUser(data.user);
                window.history.replaceState({}, document.title, window.location.origin + window.location.pathname);
                if (typeof updateUI === 'function') updateUI();
                if (typeof updateUserMenu === 'function') updateUserMenu();
                showNotification('Вход через Google выполнен успешно!', 'success');
            } else {
                showNotification('Не удалось получить данные пользователя', 'error');
            }
        } catch {
            showNotification('Ошибка при входе через Google', 'error');
        }

        return true;
    },

    logout() {
        this.setToken(null);
        this.setUser(null);
        this.closeAuthModal();
        window.location.reload();
    },

    showAuthModal() {
        const modal = document.getElementById('authModal');
        if (modal) {
            modal.style.display = 'flex';
            this.resetForm();
            setTimeout(() => document.getElementById('authEmail')?.focus(), 100);
        }
    },

    closeAuthModal() {
        const modal = document.getElementById('authModal');
        if (modal) modal.style.display = 'none';
        this.resetForm();
    },

    resetForm() {
        ['authEmail', 'authPassword', 'authConfirmPassword'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.value = '';
        });
        const errorDiv = document.getElementById('authError');
        if (errorDiv) { errorDiv.style.display = 'none'; errorDiv.textContent = ''; }
    },

    showError(message) {
        const errorDiv = document.getElementById('authError');
        if (errorDiv) {
            errorDiv.textContent = message;
            errorDiv.style.display = 'block';
            setTimeout(() => { errorDiv.style.display = 'none'; }, 5000);
        }
    },

    updateUIMode() {
        const isReg = this.isRegisterMode;
        const title = document.getElementById('authTitle');
        const submitBtn = document.getElementById('authSubmitBtn');
        const confirmField = document.getElementById('authConfirmPassword');
        const toggleLink = document.getElementById('toggleAuthMode');

        if (title) title.textContent = isReg ? 'Регистрация' : 'Вход';
        if (submitBtn) submitBtn.textContent = isReg ? 'Зарегистрироваться' : 'Войти';
        if (confirmField) confirmField.style.display = isReg ? 'block' : 'none';
        if (toggleLink) toggleLink.innerHTML = isReg ? 'Уже есть аккаунт? Войти' : 'Нет аккаунта? Зарегистрироваться';
    },

    toggleMode() {
        this.isRegisterMode = !this.isRegisterMode;
        this.updateUIMode();
        this.resetForm();
        const passwordField = document.getElementById('authPassword');
        if (passwordField) {
            if (this.isRegisterMode) {
                passwordField.setAttribute('autocomplete', 'new-password');
                passwordField.setAttribute('placeholder', 'Пароль (мин. 4 символа)');
            } else {
                passwordField.setAttribute('autocomplete', 'current-password');
                passwordField.setAttribute('placeholder', 'Пароль');
            }
        }
    },

    async handleSubmit() {
        const email = document.getElementById('authEmail')?.value.trim();
        const password = document.getElementById('authPassword')?.value;

        const errorDiv = document.getElementById('authError');
        if (errorDiv) { errorDiv.style.display = 'none'; errorDiv.textContent = ''; }

        if (!email) { this.showError('Введите email'); return; }
        if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { this.showError('Введите корректный email'); return; }
        if (!password) { this.showError('Введите пароль'); return; }

        const submitBtn = document.getElementById('authSubmitBtn');
        const originalText = submitBtn?.textContent;

        const setLoading = (loading, text) => {
            if (submitBtn) { submitBtn.textContent = loading ? text : originalText; submitBtn.disabled = loading; }
        };

        if (this.isRegisterMode) {
            const confirmPassword = document.getElementById('authConfirmPassword')?.value;
            if (password.length < 4) { this.showError('Пароль должен содержать минимум 4 символа'); return; }
            if (password !== confirmPassword) { this.showError('Пароли не совпадают'); return; }

            setLoading(true, 'Отправка кода...');
            const result = await this.sendVerification(email, password);
            setLoading(false);

            if (result.success) {
                this.showVerificationModal(result.email);
            } else {
                this.showError(result.error);
            }
        } else {
            setLoading(true, 'Вход...');
            const result = await this.login(email, password);
            setLoading(false);
            if (!result.success) this.showError(result.error);
        }
    },

    async sendVerification(email, password) {
        const result = await API.sendVerification(email, password);
        if (result.ok) {
            this.pendingEmail = email;
            this.pendingPassword = password;
            return { success: true, email: result.data.email };
        }
        return { success: false, error: result.data.detail || 'Ошибка отправки кода' };
    },

    async verifyCode(code) {
        const result = await API.verifyCode(this.pendingEmail, code);
        if (result.ok) {
            this.setToken(result.data.access_token);
            this.setUser(result.data.user);
            this.closeVerificationModal();
            if (typeof updateUI === 'function') updateUI();
            if (typeof updateUserMenu === 'function') updateUserMenu();
            return { success: true };
        }
        return { success: false, error: result.data.detail || 'Неверный код' };
    },

    showVerificationModal(email) {
        const modal = document.getElementById('verificationModal');
        const emailSpan = document.getElementById('verificationEmail');
        if (modal && emailSpan) {
            emailSpan.textContent = `Код отправлен на ${email}`;
            modal.style.display = 'flex';
            const codeInput = document.getElementById('verificationCode');
            if (codeInput) codeInput.value = '';
            const errorDiv = document.getElementById('verificationError');
            if (errorDiv) errorDiv.style.display = 'none';
        }
    },

    closeVerificationModal() {
        const modal = document.getElementById('verificationModal');
        if (modal) modal.style.display = 'none';
    },

    async resendVerificationCode() {
        if (!this.pendingEmail || !this.pendingPassword) {
            showNotification('Ошибка: email не найден', 'error');
            return;
        }
        const result = await API.sendVerification(this.pendingEmail, this.pendingPassword);
        if (result.ok) {
            showNotification('Код отправлен повторно', 'success');
        } else {
            showNotification('Не удалось отправить код', 'error');
        }
    },
};

function initAuthModal() {
    const modal = document.getElementById('authModal');
    if (!modal) return;

    Auth.updateUIMode();

    document.getElementById('authSubmitBtn')?.addEventListener('click', () => Auth.handleSubmit());

    ['authEmail', 'authPassword', 'authConfirmPassword'].forEach(id => {
        document.getElementById(id)?.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') { e.preventDefault(); Auth.handleSubmit(); }
        });
    });

    document.getElementById('toggleAuthMode')?.addEventListener('click', (e) => {
        e.preventDefault();
        Auth.toggleMode();
    });

    document.getElementById('googleLoginBtn')?.addEventListener('click', () => Auth.loginWithGoogle());

    let mouseDownOnOverlay = false;
    modal.addEventListener('mousedown', (e) => { mouseDownOnOverlay = e.target === modal; });
    modal.addEventListener('mouseup', (e) => {
        if (e.target === modal && mouseDownOnOverlay) Auth.closeAuthModal();
        mouseDownOnOverlay = false;
    });

    modal.querySelector('.modal-close')?.addEventListener('click', (e) => {
        e.stopPropagation();
        Auth.closeAuthModal();
    });

    const modalContent = modal.querySelector('.modal-content');
    if (modalContent) {
        modalContent.addEventListener('mousedown', (e) => { mouseDownOnOverlay = false; e.stopPropagation(); });
        modalContent.addEventListener('mouseup', (e) => e.stopPropagation());
    }

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && modal.style.display === 'flex') Auth.closeAuthModal();
    });
}

(function handleTokenOnLoad() {
    const token = new URLSearchParams(window.location.search).get('token');
    if (!token || Auth.getToken()) return;

    Auth.setToken(token);
    window.history.replaceState({}, document.title, window.location.origin + window.location.pathname);

    fetch('/me', { headers: { 'Authorization': `Bearer ${token}` } })
        .then(r => r.json())
        .then(data => {
            if (data.success && data.user) {
                Auth.setUser(data.user);
                if (typeof updateUI === 'function') updateUI();
                if (typeof updateUserMenu === 'function') updateUserMenu();
                showNotification('Вход через Google выполнен успешно!', 'success');
            }
        })
        .catch(() => {});
})();

window.showAuthModal = () => Auth.showAuthModal();
window.closeAuthModal = () => Auth.closeAuthModal();

document.addEventListener('DOMContentLoaded', () => {
    Auth.handleGoogleCallback();
    initAuthModal();
    document.getElementById('authBtn')?.addEventListener('click', () => Auth.showAuthModal());
    setTimeout(() => { if (typeof updateUI === 'function') updateUI(); }, 0);
});