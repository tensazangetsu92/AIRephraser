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
    if (!email || !password) { showNotification('Заполните все поля', 'warning'); return; }
    const result = await Auth.login(email, password);
    if (!result.success) showNotification(result.error, 'error');
}

async function handleRegister() {
    const email = document.getElementById('authEmail')?.value;
    const password = document.getElementById('authPassword')?.value;
    const confirmPassword = document.getElementById('authConfirmPassword')?.value;
    if (!email || !password) { showNotification('Заполните все поля', 'warning'); return; }
    if (password !== confirmPassword) { showNotification('Пароли не совпадают', 'warning'); return; }
    if (password.length < 4) { showNotification('Пароль должен содержать минимум 4 символа', 'warning'); return; }
    const result = await Auth.sendVerification(email, password);
    if (result.success) {
        Auth.showVerificationModal(result.email);
    } else {
        showNotification(result.error, 'error');
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
    const profileBtn = document.getElementById('profileBtn');

    if (!userMenu || !userPopup) return;

    userMenuInited = true;

    // Убираем старые обработчики, чтобы не дублировать
    const newUserMenu = userMenu.cloneNode(true);
    userMenu.parentNode.replaceChild(newUserMenu, userMenu);

    const newUserPopup = userPopup.cloneNode(true);
    userPopup.parentNode.replaceChild(newUserPopup, userPopup);

    const finalUserMenu = document.getElementById('userMenu');
    const finalUserPopup = document.getElementById('userPopup');
    const finalLogoutBtn = document.getElementById('logoutBtn');
    const finalLangToggle = document.getElementById('langToggle');
    const finalProfileBtn = document.getElementById('profileBtn');

    finalUserMenu.addEventListener('click', (e) => {
        e.stopPropagation();
        finalUserPopup.classList.toggle('open');
    });

    document.addEventListener('click', () => {
        finalUserPopup.classList.remove('open');
    });

    finalUserPopup.addEventListener('click', (e) => e.stopPropagation());

    if (finalLogoutBtn) {
        finalLogoutBtn.addEventListener('click', () => {
            finalUserPopup.classList.remove('open');
            Auth.logout();
        });
    }

    if (finalLangToggle) {
        finalLangToggle.addEventListener('click', () => {
            if (typeof toggleLang === 'function') toggleLang();
        });
    }

    if (finalProfileBtn) {
        finalProfileBtn.addEventListener('click', () => {
            finalUserPopup.classList.remove('open');
            window.location.href = '/profile';
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
        if (userMenu) {
            userMenu.style.display = 'block';
        }
        if (authBtn) authBtn.style.display = 'none';
        if (userEmailText) userEmailText.textContent = user.email;
        if (avatarImg) {
            avatarImg.src = getAvatarUrl(user.email);
            avatarImg.alt = user.email;
        }
        initUserMenu();
    } else {
        if (userMenu) {
            userMenu.style.display = 'none';
        }
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
        if (typeof updateBalanceDisplay === 'function') updateBalanceDisplay();
    } else {
        const userMenu = document.getElementById('userMenu');
        if (userMenu) userMenu.style.display = 'none';
        if (authBtn) {
            authBtn.style.display = 'block';
            authBtn.textContent = typeof t === 'function' ? t('login') : 'Войти';
            authBtn.onclick = () => Auth.showAuthModal();
        }
        if (typeof resetTariffCards === 'function') resetTariffCards();
        const balanceBlock = document.getElementById('balanceBlock');
        if (balanceBlock) balanceBlock.style.display = 'none';
    }
}

// ========== КОПИРОВАНИЕ ==========

async function copyText() {
    const elements = window.elements || {};
    const text = elements.result?.innerText;
    if (!text || text === 'Результат появится здесь...' || text.includes('⚠️') || text.includes('❌') || text.includes('🔄')) {
        showNotification('Нет текста для копирования', 'warning');
        return;
    }
    try {
        await navigator.clipboard.writeText(text);
        showNotification('Текст скопирован в буфер обмена', 'success');
    } catch {
        showNotification('Не удалось скопировать текст', 'error');
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
        showNotification('Регистрация успешно завершена!', 'success');
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

// ========== УВЕДОМЛЕНИЯ ==========

function showNotification(message, type = 'info', duration = 3000) {
    const toast = document.getElementById('notificationToast');
    const messageSpan = document.getElementById('notificationMessage');
    const iconSpan = document.getElementById('notificationIcon');

    if (!toast || !messageSpan) return;

    // Отменяем предыдущий таймер закрытия
    if (window.notificationTimeout) clearTimeout(window.notificationTimeout);
    if (window.notificationHideTimeout) clearTimeout(window.notificationHideTimeout);

    // Убираем предыдущие классы
    toast.classList.remove('show', 'hide', 'success', 'error', 'warning', 'info');

    // Устанавливаем иконку и класс
    let icon = '';
    switch (type) {
        case 'success':
            icon = '<i class="fas fa-check-circle"></i>';
            toast.classList.add('success');
            break;
        case 'error':
            icon = '<i class="fas fa-exclamation-circle"></i>';
            toast.classList.add('error');
            break;
        case 'warning':
            icon = '<i class="fas fa-exclamation-triangle"></i>';
            toast.classList.add('warning');
            break;
        default:
            icon = '<i class="fas fa-info-circle"></i>';
            toast.classList.add('info');
    }

    iconSpan.innerHTML = icon;
    messageSpan.textContent = message;

    // Показываем уведомление
    setTimeout(() => {
        toast.classList.add('show');
    }, 10);

    // Убираем через duration
    window.notificationTimeout = setTimeout(() => {
        closeNotification();
    }, duration);
}

function closeNotification() {
    const toast = document.getElementById('notificationToast');
    if (toast) {
        toast.classList.remove('show');
        toast.classList.add('hide');
        window.notificationHideTimeout = setTimeout(() => {
            toast.classList.remove('hide');
        }, 300);
    }
}

// ========== ИНИЦИАЛИЗАЦИЯ ==========

document.addEventListener('DOMContentLoaded', () => {
    initSidebarToggle();
    setTimeout(() => {
        if (typeof updateUI === 'function') {
            updateUI();
        }
    }, 100);
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
window.showNotification = showNotification;
window.closeNotification = closeNotification;