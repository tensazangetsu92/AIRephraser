function showLogin() { Auth.showAuthModal(); }
function showRegister() {
    Auth.showAuthModal();
}
function closeModals() { Auth.closeAuthModal(); }

async function handleLogin() {
    Auth.showAuthModal();
}

async function handleRegister() {
    Auth.showAuthModal();
}

function handleLogout() { Auth.logout(); }

function getAvatarUrl(email) {
    if (!email) return '';
    const md5 = CryptoJS.MD5(email.trim().toLowerCase()).toString();
    return `https://www.gravatar.com/avatar/${md5}?s=96&d=identicon`;
}

function getUserDisplayName(user) {
    const displayName = String(user?.display_name || '').trim();
    return displayName || String(user?.email || '').trim();
}

function setUserAvatar(image, user) {
    if (!image || !user?.email) return;
    const fallbackUrl = getAvatarUrl(user.email);
    image.onerror = () => {
        if (image.src !== fallbackUrl) {
            image.onerror = null;
            image.src = fallbackUrl;
        }
    };
    image.src = user.avatar_url || fallbackUrl;
    image.alt = user.email;
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
    const registerBtn = document.getElementById('registerBtn');
    const authActions = document.querySelector('.sidebar-auth-actions');
    const userMenuWrapper = document.getElementById('userMenuWrapper');
    const userPopup = document.getElementById('userPopup');

    if (user && Auth.isAuthenticated()) {
        if (userMenuWrapper) userMenuWrapper.hidden = false;
        if (userMenu) userMenu.style.display = 'block';
        if (authActions) authActions.style.display = 'none';
        if (authBtn) authBtn.style.display = 'none';
        if (registerBtn) registerBtn.style.display = 'none';
        const userEmailText = document.getElementById('userEmailText');
        const avatarImg = document.getElementById('avatarImg');
        if (userEmailText) userEmailText.textContent = getUserDisplayName(user);
        setUserAvatar(avatarImg, user);
        initUserMenu();
    } else {
        if (userMenuWrapper) userMenuWrapper.hidden = true;
        if (userMenu) userMenu.style.display = 'none';
        if (userPopup) userPopup.classList.remove('open');
        if (authActions) authActions.style.display = 'grid';
        if (authBtn) authBtn.style.display = 'flex';
        if (registerBtn) registerBtn.style.display = 'flex';
    }
}

function updateUI() {
    const user = Auth.getUser();
    const authBtn = document.getElementById('authBtn');
    const registerBtn = document.getElementById('registerBtn');
    const authActions = document.querySelector('.sidebar-auth-actions');
    const userMenuWrapper = document.getElementById('userMenuWrapper');

    if (user && Auth.isAuthenticated()) {
        updateUserMenu();
        if (typeof loadCurrentSubscription === 'function') loadCurrentSubscription();
    } else {
        const userMenu = document.getElementById('userMenu');
        const userPopup = document.getElementById('userPopup');
        if (userMenuWrapper) userMenuWrapper.hidden = true;
        if (userMenu) userMenu.style.display = 'none';
        if (userPopup) userPopup.classList.remove('open');
        if (authActions) authActions.style.display = 'grid';
        if (authBtn) {
            authBtn.style.display = 'flex';
            const authText = authBtn.querySelector('span');
            if (authText) authText.textContent = typeof t === 'function' ? t('login') : 'Войти';
            authBtn.onclick = () => Auth.showAuthModal();
        }
        if (registerBtn) {
            registerBtn.style.display = 'flex';
            registerBtn.onclick = () => Auth.showAuthModal();
        }
        if (typeof resetTariffCards === 'function') resetTariffCards();
        ['balanceBlock', 'extraBalanceBlock'].forEach(id => {
            const balanceBlock = document.getElementById(id);
            if (balanceBlock) balanceBlock.style.display = 'none';
        });
    }

    if (typeof updateWordCounter === 'function') updateWordCounter();
    document.querySelectorAll('.home-trial-badge').forEach((badge) => {
        badge.hidden = typeof Auth !== 'undefined' && Auth.isAuthenticated();
    });
    window.dispatchEvent(new Event('authStateChanged'));
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

    const savedSidebarState = localStorage.getItem('sidebarCollapsed');
    applyCollapsed(savedSidebarState === null || savedSidebarState === 'true');

    toggleBtn.addEventListener('click', () => {
        const collapsed = !sidebar.classList.contains('collapsed');
        applyCollapsed(collapsed);
        localStorage.setItem('sidebarCollapsed', collapsed);
    });
}

document.addEventListener('DOMContentLoaded', () => {
    initSidebarToggle();
    setTimeout(() => { if (typeof updateUI === 'function') updateUI(); }, 100);
});

window.showLogin = showLogin;
window.showRegister = showRegister;
window.closeModals = closeModals;
window.handleLogin = handleLogin;
window.handleRegister = handleRegister;
window.handleLogout = handleLogout;
window.updateUI = updateUI;
window.updateUserMenu = updateUserMenu;
