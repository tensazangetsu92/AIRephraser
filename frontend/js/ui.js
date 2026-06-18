function showLogin() { Auth.showAuthModal(); }
function showRegister() {
    Auth.isRegisterMode = true;
    Auth.updateUIMode();
    Auth.showAuthModal();
}
function closeModals() { Auth.closeAuthModal(); }

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

function handleGoogleLogin() { Auth.loginWithGoogle(); }
function handleLogout() { Auth.logout(); }

function getAvatarUrl(email) {
    if (!email) return '';
    const md5 = CryptoJS.MD5(email.trim().toLowerCase()).toString();
    return `https://www.gravatar.com/avatar/${md5}?s=96&d=identicon`;
}

let userMenuInited = false;

function initUserMenu() {
    if (userMenuInited) return;
    const userMenu = document.getElementById('userMenu');
    const userPopup = document.getElementById('userPopup');
    if (!userMenu || !userPopup) return;
    userMenuInited = true;

    const newUserMenu = userMenu.cloneNode(true);
    userMenu.parentNode.replaceChild(newUserMenu, userMenu);
    const newUserPopup = userPopup.cloneNode(true);
    userPopup.parentNode.replaceChild(newUserPopup, userPopup);

    const finalMenu = document.getElementById('userMenu');
    const finalPopup = document.getElementById('userPopup');

    finalMenu.addEventListener('click', (e) => {
        e.stopPropagation();
        finalPopup.classList.toggle('open');
    });

    document.addEventListener('click', () => finalPopup.classList.remove('open'));
    finalPopup.addEventListener('click', (e) => e.stopPropagation());

    document.getElementById('logoutBtn')?.addEventListener('click', () => {
        finalPopup.classList.remove('open');
        Auth.logout();
    });

    document.getElementById('langToggle')?.addEventListener('click', () => {
        if (typeof toggleLang === 'function') toggleLang();
    });

    document.getElementById('profileBtn')?.addEventListener('click', () => {
        finalPopup.classList.remove('open');
        window.location.href = '/profile';
    });

    document.getElementById('historyPopupBtn')?.addEventListener('click', () => {
        finalPopup.classList.remove('open');
        window.location.href = '/history';
    });
}

function updateUserMenu() {
    const user = Auth.getUser();
    const userMenu = document.getElementById('userMenu');
    const authBtn = document.getElementById('authBtn');

    if (user && Auth.isAuthenticated()) {
        if (userMenu) userMenu.style.display = 'block';
        if (authBtn) authBtn.style.display = 'none';
        const userEmailText = document.getElementById('userEmailText');
        const avatarImg = document.getElementById('avatarImg');
        if (userEmailText) userEmailText.textContent = user.email;
        if (avatarImg) { avatarImg.src = getAvatarUrl(user.email); avatarImg.alt = user.email; }
        initUserMenu();
    } else {
        if (userMenu) userMenu.style.display = 'none';
        if (authBtn) authBtn.style.display = 'block';
    }
}

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

function initSidebarToggle() {
    const sidebar = document.querySelector('.sidebar');
    const toggleBtn = document.getElementById('sidebarToggle');
    const container = document.querySelector('.container');
    if (!sidebar || !toggleBtn) return;

    const applyCollapsed = (collapsed) => {
        sidebar.style.overflow = 'hidden';
        setTimeout(() => { sidebar.style.overflow = ''; }, 320);
        sidebar.classList.toggle('collapsed', collapsed);
        if (container) container.style.marginLeft = collapsed ? '70px' : '240px';
    };

    applyCollapsed(localStorage.getItem('sidebarCollapsed') === 'true');

    toggleBtn.addEventListener('click', () => {
        const collapsed = !sidebar.classList.contains('collapsed');
        applyCollapsed(collapsed);
        localStorage.setItem('sidebarCollapsed', collapsed);
    });
}

let notificationTimeout = null;
let notificationHideTimeout = null;

function showNotification(message, type = 'info', duration = 3000) {
    const toast = document.getElementById('notificationToast');
    const messageSpan = document.getElementById('notificationMessage');
    const iconSpan = document.getElementById('notificationIcon');
    if (!toast || !messageSpan) return;

    if (notificationTimeout) clearTimeout(notificationTimeout);
    if (notificationHideTimeout) clearTimeout(notificationHideTimeout);

    const icons = {
        success: 'fa-check-circle',
        error: 'fa-exclamation-circle',
        warning: 'fa-exclamation-triangle',
        info: 'fa-info-circle'
    };

    const show = () => {
        toast.classList.remove('success', 'error', 'warning', 'info');
        iconSpan.innerHTML = `<i class="fas ${icons[type] || icons.info}"></i>`;
        messageSpan.textContent = message;
        toast.classList.add(type, 'show');
        notificationTimeout = setTimeout(() => toast.classList.remove('show'), duration);
    };

    if (toast.classList.contains('show')) {
        toast.classList.remove('show');
        notificationHideTimeout = setTimeout(show, 300);
    } else {
        show();
    }
}

function closeNotification() {
    const toast = document.getElementById('notificationToast');
    if (toast) toast.classList.remove('show');
    if (notificationTimeout) clearTimeout(notificationTimeout);
    if (notificationHideTimeout) clearTimeout(notificationHideTimeout);
}

window.verifyCode = async function () {
    const code = document.getElementById('verificationCode')?.value.trim();
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

window.resendCode = async function () { await Auth.resendVerificationCode(); };
window.closeVerificationModal = function () { Auth.closeVerificationModal(); };

document.addEventListener('DOMContentLoaded', () => {
    initSidebarToggle();
    setTimeout(() => { if (typeof updateUI === 'function') updateUI(); }, 100);
});

window.showLogin = showLogin;
window.showRegister = showRegister;
window.closeModals = closeModals;
window.handleLogin = handleLogin;
window.handleRegister = handleRegister;
window.handleGoogleLogin = handleGoogleLogin;
window.handleLogout = handleLogout;
window.updateUI = updateUI;
window.updateUserMenu = updateUserMenu;
window.showNotification = showNotification;
window.closeNotification = closeNotification;