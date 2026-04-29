// frontend/js/main.js
// DOM элементы
const elements = {
    input: document.getElementById('input'),
    result: document.getElementById('result'),
    humanizeBtn: document.getElementById('humanizeBtn'),
    copyBtn: document.getElementById('copyBtn'),
    intensity: document.getElementById('intensity'),
    tone: document.getElementById('tone'),
    style: document.getElementById('style'),
    length: document.getElementById('length'),
    authBtn: document.getElementById('authBtn'),
    userName: document.getElementById('userName'),
    // Эти элементы НЕ СУЩЕСТВУЮТ в новой HTML структуре!
    // Убираем их, чтобы не было ошибок
    // loginModal: document.getElementById('loginModal'),
    // registerModal: document.getElementById('registerModal'),
    // loginError: document.getElementById('loginError'),
    // registerError: document.getElementById('registerError'),
    // registerSuccess: document.getElementById('registerSuccess'),
    // loginEmail: document.getElementById('loginEmail'),
    // loginPassword: document.getElementById('loginPassword'),
    // registerUsername: document.getElementById('registerUsername'),
    // registerEmail: document.getElementById('registerEmail'),
    // registerPassword: document.getElementById('registerPassword'),
    // googleLoginBtn: document.getElementById('googleLoginBtn')
};

// Функции модальных окон (устаревшие, теперь используется единая форма)
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

// Функции авторизации (устаревшие, теперь используются методы Auth)
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

// Обновление интерфейса
function updateUI() {
    const user = Auth.getUser();
    const userNameSpan = document.getElementById('userName');
    const authBtn = document.getElementById('authBtn');

    console.log('=== updateUI called ===');
    console.log('user object:', user);
    console.log('userNameSpan element:', userNameSpan);
    console.log('authBtn element:', authBtn);
    console.log('Auth.isAuthenticated():', Auth.isAuthenticated());

    if (user && Auth.isAuthenticated()) {
        const displayName = user.email || 'Пользователь';
        console.log('Setting display name to:', displayName);
        if (userNameSpan) {
            userNameSpan.textContent = displayName;
        }
        if (authBtn) {
            authBtn.textContent = '🚪 Выйти';
            authBtn.onclick = () => {
                Auth.logout();
                updateUI();
            };
        }
    } else {
        console.log('No user, showing login button');
        if (userNameSpan) {
            userNameSpan.textContent = '';
        }
        if (authBtn) {
            authBtn.textContent = '👤 Войти';
            authBtn.onclick = () => Auth.showAuthModal();
        }
    }
    console.log('=== updateUI finished ===');
}

// Отправка текста на обработку
async function send() {
    const text = elements.input.value.trim();

    if (!text) {
        elements.result.innerText = '⚠️ Пожалуйста, введите текст для обработки';
        return;
    }

    const requestData = {
        text: text,
        intensity: elements.intensity.value,
        tone: elements.tone.value,
        style: elements.style.value,
        length: elements.length.value
    };

    elements.humanizeBtn.disabled = true;
    elements.humanizeBtn.innerHTML = '<span class="loading"></span> Обработка...';
    elements.result.innerText = '🔄 Обработка текста...';

    // Получаем токен
    const token = Auth.getToken();

    // Отправляем запрос через fetch напрямую или через API
    try {
        const response = await fetch('/humanize', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify(requestData)
        });

        const data = await response.json();

        if (response.ok) {
            elements.result.innerText = data.result;
        } else if (response.status === 401) {
            elements.result.innerText = '❌ Сессия истекла. Войдите заново.';
            Auth.logout();
            updateUI();
        } else {
            elements.result.innerText = '❌ Ошибка: ' + (data.detail || 'Неизвестная ошибка');
        }
    } catch (err) {
        console.error('Humanize error:', err);
        elements.result.innerText = '❌ Ошибка соединения с сервером';
    }

    elements.humanizeBtn.disabled = false;
    elements.humanizeBtn.innerHTML = '🚀 Очеловечить текст';
}

// Копирование текста
async function copyText() {
    const text = elements.result.innerText;

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

// Event listeners
function initEventListeners() {
    if (elements.humanizeBtn) elements.humanizeBtn.addEventListener('click', send);
    if (elements.copyBtn) elements.copyBtn.addEventListener('click', copyText);

    if (elements.input) {
        elements.input.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.key === 'Enter') {
                send();
            }
        });
    }

    // Глобальные функции для вызова из onclick (если нужны)
    window.handleLogin = handleLogin;
    window.handleRegister = handleRegister;
    window.handleGoogleLogin = handleGoogleLogin;
    window.showLogin = showLogin;
    window.showRegister = showRegister;
}

// Инициализация
function init() {
    console.log('Initializing main.js');
    initEventListeners();
    // Даём время на загрузку Auth
    setTimeout(() => {
        updateUI();
    }, 100);
}

// Запуск
init();