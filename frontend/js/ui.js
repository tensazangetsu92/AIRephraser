// frontend/js/ui.js

// ========== МОДАЛЬНЫЕ ОКНА ==========

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

// ========== ОБЁРТКИ АВТОРИЗАЦИИ ==========

async function handleLogin() {
    const email = document.getElementById('authEmail')?.value;
    const password = document.getElementById('authPassword')?.value;
    if (!email || !password) { alert('Заполните все поля'); return; }
    const result = await Auth.login(email, password);
    if (!result.success) alert(result.error);
}

async function handleRegister() {
    const email = document.getElementById('authEmail')?.value;
    const password = document.getElementById('authPassword')?.value;
    const confirmPassword = document.getElementById('authConfirmPassword')?.value;
    if (!email || !password) { alert('Заполните все поля'); return; }
    if (password !== confirmPassword) { alert('Пароли не совпадают'); return; }
    if (password.length < 4) { alert('Пароль должен содержать минимум 4 символа'); return; }
    const result = await Auth.sendVerification(email, password);
    if (result.success) {
        Auth.showVerificationModal(result.email);
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

// ========== АВАТАРКА ==========

function getAvatarUrl(email) {
    if (!email) return '';
    const md5 = CryptoJS.MD5(email.trim().toLowerCase()).toString();
    return `https://www.gravatar.com/avatar/${md5}?s=96&d=identicon`;
}

// ========== USER MENU + ПОПАП ==========

let userMenuInited = false;

function initUserMenu() {
    if (userMenuInited) return;

    const userMenu = document.getElementById('userMenu');
    const userPopup = document.getElementById('userPopup');
    const logoutBtn = document.getElementById('logoutBtn');
    const langToggle = document.getElementById('langToggle');

    if (!userMenu || !userPopup) return;

    userMenuInited = true;

    userMenu.addEventListener('click', (e) => {
        e.stopPropagation();
        userPopup.classList.toggle('open');
    });

    document.addEventListener('click', () => {
        userPopup.classList.remove('open');
    });

    userPopup.addEventListener('click', (e) => e.stopPropagation());

    if (logoutBtn) {
        logoutBtn.addEventListener('click', () => {
            userPopup.classList.remove('open');
            Auth.logout();
            updateUserMenu();
            updateUI();
        });
    }

    if (langToggle) {
        langToggle.addEventListener('click', () => {
            // userPopup.classList.remove('open');  ← удали эту строку
            if (typeof toggleLang === 'function') toggleLang();
        });
    }
}

function updateUserMenu() {
    const user = Auth.getUser();
    const userMenu = document.getElementById('userMenu');
    const authBtn = document.getElementById('authBtn');
    const avatarImg = document.getElementById('avatarImg');
    const userEmailText = document.getElementById('userEmailText');

    if (user && Auth.isAuthenticated()) {
        if (userMenu) userMenu.style.display = 'block';
        if (authBtn) authBtn.style.display = 'none';
        if (userEmailText) userEmailText.textContent = user.email;
        if (avatarImg) {
            avatarImg.src = getAvatarUrl(user.email);
            avatarImg.alt = user.email;
        }
        initUserMenu(); // вызываем здесь — когда меню точно в DOM и видимо
    } else {
        if (userMenu) userMenu.style.display = 'none';
        if (authBtn) authBtn.style.display = 'block';
    }
}

// ========== ОБНОВЛЕНИЕ UI ==========

function updateUI() {
    const user = Auth.getUser();
    const authBtn = document.getElementById('authBtn');

    if (user && Auth.isAuthenticated()) {
        updateUserMenu();
        if (typeof loadCurrentSubscription === 'function') loadCurrentSubscription();
    } else {
        const userMenu = document.getElementById('userMenu');
        if (userMenu) userMenu.style.display = 'none';
        if (authBtn) {
            authBtn.style.display = 'block';
            authBtn.textContent = typeof t === 'function' ? t('login') : 'Войти';
            authBtn.onclick = () => Auth.showAuthModal();
        }
        if (typeof resetTariffCards === 'function') resetTariffCards();
    }
}

// ========== КОПИРОВАНИЕ ==========

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
    } catch {
        alert('❌ Не удалось скопировать текст');
    }
}

// ========== СВОРАЧИВАНИЕ САЙДБАРА ==========

function initSidebarToggle() {
    const sidebar = document.querySelector('.sidebar');
    const toggleBtn = document.getElementById('sidebarToggle');
    const container = document.querySelector('.container');

    if (!sidebar || !toggleBtn) return;

    const applyCollapsed = (collapsed) => {
        sidebar.classList.toggle('collapsed', collapsed);
        if (container) container.style.marginLeft = collapsed ? '60px' : '240px';
    };

    applyCollapsed(localStorage.getItem('sidebarCollapsed') === 'true');

    toggleBtn.addEventListener('click', () => {
        const collapsed = !sidebar.classList.contains('collapsed');
        applyCollapsed(collapsed);
        localStorage.setItem('sidebarCollapsed', collapsed);
    });
}

// ========== ВЕРИФИКАЦИЯ ==========

window.verifyCode = async function() {
    const codeInput = document.getElementById('verificationCode');
    const code = codeInput?.value.trim();
    const errorDiv = document.getElementById('verificationError');

    if (!code || code.length !== 6) {
        if (errorDiv) { errorDiv.textContent = 'Введите 6-значный код'; errorDiv.style.display = 'block'; }
        return;
    }

    const result = await Auth.verifyCode(code);
    if (result.success) {
        alert('✅ Регистрация успешно завершена!');
        Auth.closeVerificationModal();
        Auth.closeAuthModal();
    } else {
        if (errorDiv) { errorDiv.textContent = result.error; errorDiv.style.display = 'block'; }
    }
};

window.resendCode = async function() {
    await Auth.resendVerificationCode();
};

window.closeVerificationModal = function() {
    Auth.closeVerificationModal();
};

// ========== ИНИЦИАЛИЗАЦИЯ ==========

document.addEventListener('DOMContentLoaded', () => {
    initSidebarToggle();
    // initUserMenu вызывается из updateUserMenu когда пользователь авторизован
});

// ========== ГЛОБАЛЬНЫЕ ФУНКЦИИ ==========

window.showLogin = showLogin;
window.showRegister = showRegister;
window.closeModals = closeModals;
window.handleLogin = handleLogin;
window.handleRegister = handleRegister;
window.handleGoogleLogin = handleGoogleLogin;
window.handleLogout = handleLogout;
window.updateUI = updateUI;
window.copyText = copyText;
window.updateUserMenu = updateUserMenu;