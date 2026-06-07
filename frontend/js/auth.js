// frontend/js/auth.js

const Auth = {

    token: localStorage.getItem('token'),
    isRegisterMode: false, // false = вход, true = регистрация

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
            console.log('Saving user to localStorage:', user);
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
            this.closeAuthModal();

            // 👇 ДОЛЖЕН БЫТЬ ВЫЗОВ
            if (typeof updateUI === 'function') {
                updateUI();
            }
            if (typeof updateUserMenu === 'function') {
                updateUserMenu();
            }

            return { success: true, user: result.data.user };
        }
        return { success: false, error: result.data.detail || 'Ошибка входа' };
    },

    async register(email, password) {
        const result = await API.register(email, password);
        if (result.ok) {
            this.isRegisterMode = false;
            this.updateUIMode();
            return { success: true, message: result.data.message };
        } else {
            return { success: false, error: result.data.detail || 'Ошибка регистрации' };
        }
    },

    loginWithGoogle() {
        window.location.href = '/auth/google/login';
    },

    // Исправленный обработчик Google токена
    async handleGoogleCallback() {
        const urlParams = new URLSearchParams(window.location.search);
        const googleToken = urlParams.get('token');

        console.log('Checking Google token in URL:', googleToken ? 'Found!' : 'Not found');

        if (googleToken) {
            this.setToken(googleToken);

            try {
                console.log('Fetching user data from /me...');
                const response = await fetch('/me', {
                    headers: { 'Authorization': `Bearer ${googleToken}` }
                });

                console.log('/me response status:', response.status);
                const data = await response.json();
                console.log('/me response data:', data);

                if (data.success && data.user) {
                    this.setUser(data.user);

                    // Очищаем URL от токена БЕЗ перезагрузки
                    const cleanUrl = window.location.origin + window.location.pathname;
                    window.history.replaceState({}, document.title, cleanUrl);

                    // Обновляем интерфейс
                    if (typeof updateUI === 'function') {
                        updateUI();
                    }
                    if (typeof updateUserMenu === 'function') {
                        updateUserMenu();
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
        this.closeAuthModal();
        window.location.reload();
    },

    isAuthenticated() {
        return !!this.token;
    },

    showAuthModal() {
        const modal = document.getElementById('authModal');
        if (modal) {
            modal.style.display = 'flex';
            this.resetForm();
            setTimeout(() => {
                const emailInput = document.getElementById('authEmail');
                if (emailInput) emailInput.focus();
            }, 100);
        }
    },

    closeAuthModal() {
        const modal = document.getElementById('authModal');
        if (modal) modal.style.display = 'none';
        this.resetForm();
    },

    resetForm() {
        const fields = ['authEmail', 'authPassword', 'authConfirmPassword'];
        fields.forEach(fieldId => {
            const field = document.getElementById(fieldId);
            if (field) field.value = '';
        });
        const errorDiv = document.getElementById('authError');
        if (errorDiv) {
            errorDiv.style.display = 'none';
            errorDiv.textContent = '';
        }
    },

    updateUIMode() {
        const title = document.getElementById('authTitle');
        const submitBtn = document.getElementById('authSubmitBtn');
        const confirmField = document.getElementById('authConfirmPassword');
        const toggleLink = document.getElementById('toggleAuthMode');

        if (this.isRegisterMode) {
            if (title) title.textContent = 'Регистрация';
            if (submitBtn) submitBtn.textContent = 'Зарегистрироваться';
            if (confirmField) confirmField.style.display = 'block';
            if (toggleLink) toggleLink.innerHTML = 'Уже есть аккаунт? Войти';
        } else {
            if (title) title.textContent = 'Вход';
            if (submitBtn) submitBtn.textContent = 'Войти';
            if (confirmField) confirmField.style.display = 'none';
            if (toggleLink) toggleLink.innerHTML = 'Нет аккаунта? Зарегистрироваться';
        }
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

        if (errorDiv) {
            errorDiv.style.display = 'none';
            errorDiv.textContent = '';
        }

        if (!email) {
            this.showError('Введите email');
            return;
        }

        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(email)) {
            this.showError('Введите корректный email');
            return;
        }

        if (!password) {
            this.showError('Введите пароль');
            return;
        }

        if (this.isRegisterMode) {
            const confirmPassword = document.getElementById('authConfirmPassword')?.value;

            if (password.length < 4) {
                this.showError('Пароль должен содержать минимум 4 символа');
                return;
            }

            if (password !== confirmPassword) {
                this.showError('Пароли не совпадают');
                return;
            }

            const submitBtn = document.getElementById('authSubmitBtn');
            const originalText = submitBtn?.textContent;
            if (submitBtn) {
                submitBtn.textContent = '⏳ Отправка кода...';
                submitBtn.disabled = true;
            }

            const result = await this.sendVerification(email, password);

            if (submitBtn) {
                submitBtn.textContent = originalText;
                submitBtn.disabled = false;
            }

            if (result.success) {
                this.showVerificationModal(result.email);
            } else {
                this.showError(result.error);
            }
        } else {
            const submitBtn = document.getElementById('authSubmitBtn');
            const originalText = submitBtn?.textContent;
            if (submitBtn) {
                submitBtn.textContent = '⏳ Вход...';
                submitBtn.disabled = true;
            }

            const result = await this.login(email, password);

            if (submitBtn) {
                submitBtn.textContent = originalText;
                submitBtn.disabled = false;
            }

            if (!result.success) {
                this.showError(result.error);
            }
        }
    },

    showError(message) {
        const errorDiv = document.getElementById('authError');
        if (errorDiv) {
            errorDiv.textContent = message;
            errorDiv.style.display = 'block';
            setTimeout(() => {
                if (errorDiv.style.display === 'block') {
                    errorDiv.style.display = 'none';
                }
            }, 5000);
        }
    },

    async sendVerification(email, password) {
        const result = await API.sendVerification(email, password);
        if (result.ok) {
            this.pendingEmail = email;
            this.pendingPassword = password;
            return { success: true, email: result.data.email };
        } else {
            return { success: false, error: result.data.detail || 'Ошибка отправки кода' };
        }
    },

    async verifyCode(code) {
        const result = await API.verifyCode(this.pendingEmail, code);
        if (result.ok) {
            this.setToken(result.data.access_token);
            this.setUser(result.data.user);
            this.closeVerificationModal();
            if (typeof updateUI === 'function') {
                updateUI();
            }
            if (typeof updateUserMenu === 'function') {
                updateUserMenu();
            }
            return { success: true };
        } else {
            return { success: false, error: result.data.detail || 'Неверный код' };
        }
    },

    showVerificationModal(email) {
        const modal = document.getElementById('verificationModal');
        const emailSpan = document.getElementById('verificationEmail');
        const codeInput = document.getElementById('verificationCode');
        const errorDiv = document.getElementById('verificationError');

        if (modal && emailSpan) {
            emailSpan.textContent = `Код отправлен на ${email}`;
            modal.style.display = 'flex';
            if (codeInput) codeInput.value = '';
            if (errorDiv) errorDiv.style.display = 'none';
        }
    },

    closeVerificationModal() {
        const modal = document.getElementById('verificationModal');
        if (modal) modal.style.display = 'none';
    },

    async resendVerificationCode() {
        if (!this.pendingEmail || !this.pendingPassword) {
            this.showError('Ошибка: email не найден');
            return;
        }
        const result = await API.sendVerification(this.pendingEmail, this.pendingPassword);
        if (result.ok) {
            alert('✅ Код отправлен повторно!');
        } else {
            alert('❌ Ошибка: ' + (result.error || 'Не удалось отправить код'));
        }
    },
};

// ========== ИНИЦИАЛИЗАЦИЯ ==========

window.showAuthModal = () => Auth.showAuthModal();
window.closeAuthModal = () => Auth.closeAuthModal();

// Обработка Google токена ПРИ ЗАГРУЗКЕ
(function handleTokenOnLoad() {
    const urlParams = new URLSearchParams(window.location.search);
    const token = urlParams.get('token');

    if (token && !Auth.getToken()) {
        console.log('Found token in URL on load, saving...');
        Auth.setToken(token);

        // Убираем токен из URL
        const cleanUrl = window.location.origin + window.location.pathname;
        window.history.replaceState({}, document.title, cleanUrl);

        // Получаем данные пользователя
        fetch('/me', {
            headers: { 'Authorization': `Bearer ${token}` }
        })
        .then(res => res.json())
        .then(data => {
            if (data.success && data.user) {
                Auth.setUser(data.user);
                if (typeof updateUI === 'function') updateUI();
                if (typeof updateUserMenu === 'function') updateUserMenu();
                alert('✅ Вход через Google выполнен успешно!');
            }
        })
        .catch(err => console.error('Token validation error:', err));
    }
})();

document.addEventListener('DOMContentLoaded', () => {
    Auth.handleGoogleCallback();
    initAuthModal();

    const authBtn = document.getElementById('authBtn');
    if (authBtn) {
        authBtn.addEventListener('click', () => Auth.showAuthModal());
    }

    // Даём время загрузиться ui.js
    setTimeout(() => {
        if (typeof updateUI === 'function') updateUI();
    }, 0);
});

function initAuthModal() {
    const modal = document.getElementById('authModal');

    if (!modal) return;

    Auth.updateUIMode();

    const submitBtn = document.getElementById('authSubmitBtn');
    if (submitBtn) {
        submitBtn.addEventListener('click', () => Auth.handleSubmit());
    }

    const inputs = ['authEmail', 'authPassword', 'authConfirmPassword'];
    inputs.forEach(inputId => {
        const input = document.getElementById(inputId);
        if (input) {
            input.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    Auth.handleSubmit();
                }
            });
        }
    });

    const toggleLink = document.getElementById('toggleAuthMode');
    if (toggleLink) {
        toggleLink.addEventListener('click', (e) => {
            e.preventDefault();
            Auth.toggleMode();
        });
    }

    const googleBtn = document.getElementById('googleLoginBtn');
    if (googleBtn) {
        googleBtn.addEventListener('click', () => Auth.loginWithGoogle());
    }

    let mouseDownOnOverlay = false;

    modal.addEventListener('mousedown', (e) => {
        if (e.target === modal) {
            mouseDownOnOverlay = true;
        } else {
            mouseDownOnOverlay = false;
        }
    });

    modal.addEventListener('mouseup', (e) => {
        if (e.target === modal && mouseDownOnOverlay === true) {
            Auth.closeAuthModal();
        }
        mouseDownOnOverlay = false;
    });

    const closeBtn = modal.querySelector('.modal-close');
    if (closeBtn) {
        closeBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            Auth.closeAuthModal();
        });
    }

    const modalContent = modal.querySelector('.modal-content');
    if (modalContent) {
        modalContent.addEventListener('mousedown', (e) => {
            mouseDownOnOverlay = false;
            e.stopPropagation();
        });
        modalContent.addEventListener('mouseup', (e) => {
            e.stopPropagation();
        });
    }

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && modal.style.display === 'flex') {
            Auth.closeAuthModal();
        }
    });

    console.log('Auth modal initialized');
}