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
            // Убедитесь, что сохраняется email
            console.log('Saving user to localStorage:', user); // Проверьте, что приходит
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
            if (typeof updateUI === 'function') {
                updateUI();
            }
            return { success: true, user: result.data.user };
        } else {
            return { success: false, error: result.data.detail || 'Ошибка входа' };
        }
    },

    async register(email, password) {
        // Отправляем email и password
        const result = await API.register(email, password);

        if (result.ok) {
            // После успешной регистрации переключаемся на режим входа
            this.isRegisterMode = false;
            this.updateUIMode();
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
                console.log('Fetching user data from /me...');
                const response = await fetch('/me', {
                    headers: { 'Authorization': `Bearer ${googleToken}` }
                });

                console.log('/me response status:', response.status);

                const data = await response.json();
                console.log('/me response data:', data);

                if (data.success && data.user) {
                    this.setUser(data.user);
                    window.history.replaceState({}, document.title, window.location.pathname);
                    this.closeAuthModal();
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
        this.closeAuthModal();
        if (typeof updateUI === 'function') {
            updateUI();
        }
    },

    isAuthenticated() {
        return !!this.token;
    },

    // ========== РАБОТА С МОДАЛЬНЫМ ОКНОМ ==========

    showAuthModal() {
        const modal = document.getElementById('authModal');

        if (modal) {
            modal.style.display = 'flex';

            // Сбрасываем форму
            this.resetForm();

            // Фокус на поле email
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
        // Очищаем все поля
        const fields = ['authEmail', 'authPassword', 'authConfirmPassword'];
        fields.forEach(fieldId => {
            const field = document.getElementById(fieldId);
            if (field) field.value = '';
        });

        // Скрываем ошибки
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
            // Режим регистрации
            if (title) title.textContent = '📝 Регистрация';
            if (submitBtn) submitBtn.textContent = 'Зарегистрироваться';
            if (confirmField) confirmField.style.display = 'block';
            if (toggleLink) toggleLink.innerHTML = '🔐 Уже есть аккаунт? Войти';
        } else {
            // Режим входа
            if (title) title.textContent = '🔐 Вход';
            if (submitBtn) submitBtn.textContent = 'Войти';
            if (confirmField) confirmField.style.display = 'none';
            if (toggleLink) toggleLink.innerHTML = '📝 Нет аккаунта? Зарегистрироваться';
        }
    },

    toggleMode() {
        this.isRegisterMode = !this.isRegisterMode;
        this.updateUIMode();
        this.resetForm();

        // Меняем autocomplete для поля пароля
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

        // Очищаем предыдущую ошибку
        if (errorDiv) {
            errorDiv.style.display = 'none';
            errorDiv.textContent = '';
        }

        // Валидация email
        if (!email) {
            this.showError('Введите email');
            return;
        }

        // Проверка формата email
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
            // РЕГИСТРАЦИЯ
            const confirmPassword = document.getElementById('authConfirmPassword')?.value;

            if (password.length < 4) {
                this.showError('Пароль должен содержать минимум 4 символа');
                return;
            }

            if (password !== confirmPassword) {
                this.showError('Пароли не совпадают');
                return;
            }

            // Показываем индикатор загрузки
            const submitBtn = document.getElementById('authSubmitBtn');
            const originalText = submitBtn?.textContent;
            if (submitBtn) {
                submitBtn.textContent = '⏳ Регистрация...';
                submitBtn.disabled = true;
            }

            const result = await this.register(email, password);

            // Восстанавливаем кнопку
            if (submitBtn) {
                submitBtn.textContent = originalText;
                submitBtn.disabled = false;
            }

            if (result.success) {
                alert('✅ Регистрация успешна! Теперь вы можете войти.');
                this.toggleMode(); // Переключаем на режим входа
                // Очищаем поля паролей
                const passwordField = document.getElementById('authPassword');
                const confirmField = document.getElementById('authConfirmPassword');
                if (passwordField) passwordField.value = '';
                if (confirmField) confirmField.value = '';
            } else {
                this.showError(result.error);
            }
        } else {
            // ВХОД
            // Показываем индикатор загрузки
            const submitBtn = document.getElementById('authSubmitBtn');
            const originalText = submitBtn?.textContent;
            if (submitBtn) {
                submitBtn.textContent = '⏳ Вход...';
                submitBtn.disabled = true;
            }

            const result = await this.login(email, password);

            // Восстанавливаем кнопку
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

            // Автоматически скрываем ошибку через 5 секунд
            setTimeout(() => {
                if (errorDiv.style.display === 'block') {
                    errorDiv.style.display = 'none';
                }
            }, 5000);
        }
    }
};

// ========== ИНИЦИАЛИЗАЦИЯ ==========

// Функции для вызова из onclick (глобальные)
window.showAuthModal = () => Auth.showAuthModal();
window.closeAuthModal = () => Auth.closeAuthModal();

// Инициализация при загрузке
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOMContentLoaded - initializing auth');

    // Обработка Google callback
    Auth.handleGoogleCallback();

    // Настройка модального окна
    initAuthModal();

    // Настройка кнопки входа в навбаре
    const authBtn = document.getElementById('authBtn');
    if (authBtn) {
        authBtn.addEventListener('click', () => Auth.showAuthModal());
    }

    // Обновляем UI если пользователь уже авторизован
    if (typeof updateUI === 'function') {
        updateUI();
    }
});

function initAuthModal() {
    const modal = document.getElementById('authModal');

    if (!modal) return;

    // Настройка UI режима
    Auth.updateUIMode();

    // Обработчик отправки формы
    const submitBtn = document.getElementById('authSubmitBtn');
    if (submitBtn) {
        submitBtn.addEventListener('click', () => Auth.handleSubmit());
    }

    // Обработчик Enter
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

    // Переключение режима
    const toggleLink = document.getElementById('toggleAuthMode');
    if (toggleLink) {
        toggleLink.addEventListener('click', (e) => {
            e.preventDefault();
            Auth.toggleMode();
        });
    }

    // Google вход
    const googleBtn = document.getElementById('googleLoginBtn');
    if (googleBtn) {
        googleBtn.addEventListener('click', () => Auth.loginWithGoogle());
    }

    // ========== ЛОГИКА ЗАКРЫТИЯ ==========

    let mouseDownOnOverlay = false;

    // Нажатие на фоне
    modal.addEventListener('mousedown', (e) => {
        if (e.target === modal) {
            mouseDownOnOverlay = true;
            console.log('mousedown on overlay'); // отладка
        } else {
            mouseDownOnOverlay = false;
        }
    });

    // Отпускание на фоне
    modal.addEventListener('mouseup', (e) => {
        console.log('mouseup on:', e.target === modal ? 'overlay' : 'content', 'mouseDownOnOverlay:', mouseDownOnOverlay); // отладка
        if (e.target === modal && mouseDownOnOverlay === true) {
            console.log('closing modal'); // отладка
            Auth.closeAuthModal();
        }
        mouseDownOnOverlay = false;
    });

    // Закрытие по крестику
    const closeBtn = modal.querySelector('.modal-close');
    if (closeBtn) {
        closeBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            Auth.closeAuthModal();
        });
    }

    // Предотвращаем закрытие при клике на содержимое
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

    // Закрытие по ESC
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && modal.style.display === 'flex') {
            Auth.closeAuthModal();
        }
    });

    console.log('Auth modal initialized');
}