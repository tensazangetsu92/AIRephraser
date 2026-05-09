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

// frontend/js/ui.js

// Функция для получения аватарки из Gmail (через Gravatar)
function getAvatarUrl(email) {
    if (!email) return '';
    // Кодируем email в MD5 для Gravatar
    const md5 = CryptoJS.MD5(email.trim().toLowerCase()).toString();
    return `https://www.gravatar.com/avatar/${md5}?s=96&d=identicon`;
}

// Отображение аватарки и меню
function updateUserMenu() {
    const user = Auth.getUser();
    const userMenu = document.getElementById('userMenu');
    const authBtn = document.getElementById('authBtn');
    const avatarImg = document.getElementById('avatarImg');
    const userEmailText = document.getElementById('userEmailText');

    if (user && Auth.isAuthenticated()) {
        // Пользователь авторизован - показываем меню, скрываем кнопку входа
        userMenu.style.display = 'block';
        if (authBtn) authBtn.style.display = 'none';

        // Устанавливаем email
        if (userEmailText) userEmailText.textContent = user.email;

        // Устанавливаем аватарку
        if (avatarImg) {
            const avatarUrl = getAvatarUrl(user.email);
            avatarImg.src = avatarUrl;
            avatarImg.alt = user.email;
        }
    } else {
        // Пользователь не авторизован - скрываем меню, показываем кнопку входа
        if (userMenu) userMenu.style.display = 'none';
        if (authBtn) authBtn.style.display = 'block';
    }
}

// Инициализация выпадающего меню
function initUserMenu() {
    const userMenu = document.getElementById('userMenu');
    const dropdownLogoutBtn = document.getElementById('dropdownLogoutBtn');

    if (!userMenu) return;

    // Открытие/закрытие меню при клике на аватарку
    userMenu.addEventListener('click', (e) => {
        // Не закрываем меню при клике на кнопку выхода
        if (e.target.closest('.dropdown-item.logout')) {
            return;
        }
        userMenu.classList.toggle('open');
        e.stopPropagation();
    });

    // Закрытие меню при клике вне его
    document.addEventListener('click', () => {
        userMenu.classList.remove('open');
    });

    // Кнопка выхода из меню
    if (dropdownLogoutBtn) {
        dropdownLogoutBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            Auth.logout();
            updateUserMenu();
            updateUI();
            userMenu.classList.remove('open');
        });
    }
}

// Обновляем существующую функцию updateUI
function updateUI() {
    const user = Auth.getUser();
    const userNameSpan = document.getElementById('userName');
    const authBtn = document.getElementById('authBtn');

    if (user && Auth.isAuthenticated()) {
        // Обновляем меню с аватаркой
        updateUserMenu();

        // Загружаем информацию о подписке после входа
        if (typeof loadCurrentSubscription === 'function') {
            loadCurrentSubscription();
        }
    } else {
        // Скрываем меню, показываем кнопку входа
        const userMenu = document.getElementById('userMenu');
        if (userMenu) userMenu.style.display = 'none';
        if (authBtn) {
            authBtn.style.display = 'block';
            authBtn.textContent = t('login');
            authBtn.onclick = () => Auth.showAuthModal();
        }

        // Сбрасываем UI карточек
        if (typeof resetTariffCards === 'function') {
            resetTariffCards();
        }
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