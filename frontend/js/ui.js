// frontend/js/ui.js

// Функции модальных окон
function showLogin() {
    Auth.showAuthModal();
}

function showRegister() {
    Auth.isRegisterMode = true;
    Auth.updateUIMode();
    Auth.showAuthModal();
}

function closeModals() {
    Auth.closeAuthModal();
}

// Функции авторизации (обёртки)
async function handleLogin() {
    const email = document.getElementById('authEmail')?.value;
    const password = document.getElementById('authPassword')?.value;

    if (!email || !password) {
        alert('Заполните все поля');
        return;
    }

    const result = await Auth.login(email, password);
    if (!result.success) {
        alert(result.error);
    }
}

async function handleRegister() {
    const email = document.getElementById('authEmail')?.value;
    const password = document.getElementById('authPassword')?.value;
    const confirmPassword = document.getElementById('authConfirmPassword')?.value;

    if (!email || !password) {
        alert('Заполните все поля');
        return;
    }

    if (password !== confirmPassword) {
        alert('Пароли не совпадают');
        return;
    }

    const result = await Auth.register(email, password);
    if (result.success) {
        alert('✅ Регистрация успешна! Теперь войдите.');
        Auth.toggleMode();
    } else {
        alert(result.error);
    }
}

function handleGoogleLogin() {
    Auth.loginWithGoogle();
}

function handleLogout() {
    Auth.logout();
}

// Обновление интерфейса (шапка, кнопки)
function updateUI() {
    const user = Auth.getUser();
    const userNameSpan = document.getElementById('userName');
    const authBtn = document.getElementById('authBtn');

    if (user && Auth.isAuthenticated()) {
        const displayName = user.email || 'Пользователь';
        if (userNameSpan) userNameSpan.textContent = displayName;
        if (authBtn) {
            authBtn.textContent = 'Выйти';
            authBtn.onclick = () => {
                Auth.logout();
                updateUI();
            };
        }
        // Загружаем информацию о подписке
        if (typeof loadCurrentSubscription === 'function') {
            loadCurrentSubscription();
        }
    } else {
        if (userNameSpan) userNameSpan.textContent = '';
        if (authBtn) {
            authBtn.textContent = 'Войти';
            authBtn.onclick = () => Auth.showAuthModal();
        }
        // Сбрасываем UI карточек
        if (typeof resetTariffCards === 'function') {
            resetTariffCards();
        }
    }
}

// Копирование текста
async function copyText() {
    const elements = window.elements || {};
    const text = elements.result?.innerText;

    if (!text || text === 'Результат появится здесь...' || text.includes('⚠️') || text.includes('❌') || text.includes('🔄')) {
        alert('Нет текста для копирования');
        return;
    }
    try {
        await navigator.clipboard.writeText(text);
        alert('✅ Текст скопирован в буфер обмена');
    } catch (err) {
        alert('❌ Не удалось скопировать текст');
    }
}

// Делаем функции глобальными
window.showLogin = showLogin;
window.showRegister = showRegister;
window.closeModals = closeModals;
window.handleLogin = handleLogin;
window.handleRegister = handleRegister;
window.handleGoogleLogin = handleGoogleLogin;
window.handleLogout = handleLogout;
window.updateUI = updateUI;
window.copyText = copyText;