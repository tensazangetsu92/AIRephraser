// frontend/js/main.js
// DOM элементы - объявляем сразу и заполняем
let elements = {};

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

// Функции авторизации
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

    if (user && Auth.isAuthenticated()) {
        const displayName = user.email || 'Пользователь';
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
        if (userNameSpan) {
            userNameSpan.textContent = '';
        }
        if (authBtn) {
            authBtn.textContent = '👤 Войти';
            authBtn.onclick = () => Auth.showAuthModal();
        }
    }
}

let pendingText = null;

// Обработка текста
async function processText(text) {
    const requestData = {
        text: text,
        intensity: elements.intensity?.value || 'medium',
        tone: elements.tone?.value || 'neutral',
        style: elements.style?.value || 'simple',
        length: elements.length?.value || 'same'
    };

    if (elements.humanizeBtn) {
        elements.humanizeBtn.disabled = true;
        elements.humanizeBtn.innerHTML = '<span class="loading"></span> Обработка...';
    }
    if (elements.result) elements.result.innerText = '🔄 Обработка текста...';

    const token = Auth.getToken();

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
            if (elements.result) elements.result.innerText = data.result;
        } else if (response.status === 401) {
            if (elements.result) elements.result.innerText = '❌ Сессия истекла. Пожалуйста, войдите заново.';
            Auth.logout();
            updateUI();
            setTimeout(() => Auth.showAuthModal(), 1500);
        } else {
            if (elements.result) elements.result.innerText = '❌ Ошибка: ' + (data.detail || 'Неизвестная ошибка');
        }
    } catch (err) {
        console.error('Humanize error:', err);
        if (elements.result) elements.result.innerText = '❌ Ошибка соединения с сервером';
    }

    if (elements.humanizeBtn) {
        elements.humanizeBtn.disabled = false;
        elements.humanizeBtn.innerHTML = '🚀 Очеловечить текст';
    }
}

// Отправка текста на обработку
async function send() {
    console.log('=== SEND FUNCTION CALLED ===');

    // Проверяем что элементы загружены
    if (!elements.input) {
        console.error('Elements not initialized!');
        return;
    }

    const text = elements.input.value.trim();
    console.log('Text:', text);
    console.log('Auth.isAuthenticated():', Auth.isAuthenticated());

    if (!text) {
        if (elements.result) elements.result.innerText = '⚠️ Пожалуйста, введите текст для обработки';
        return;
    }

    // Проверка авторизации
    if (!Auth.isAuthenticated()) {
        console.log('User NOT authenticated, saving pending text');
        pendingText = text;
        if (elements.result) elements.result.innerText = '🔐 Для использования сервиса необходимо войти в аккаунт';
        Auth.showAuthModal();
        return;
    }

    await processText(text);
}

async function processPendingText() {
    console.log('processPendingText called, pendingText:', pendingText);
    if (pendingText && Auth.isAuthenticated()) {
        const text = pendingText;
        pendingText = null;
        await processText(text);
    }
}

// Копирование текста
async function copyText() {
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

// Event listeners
function initEventListeners() {
    console.log('initEventListeners called');

    if (elements.humanizeBtn) {
        elements.humanizeBtn.addEventListener('click', send);
        console.log('humanizeBtn handler attached');
    }
    if (elements.copyBtn) {
        elements.copyBtn.addEventListener('click', copyText);
        console.log('copyBtn handler attached');
    }
    if (elements.input) {
        elements.input.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.key === 'Enter') {
                send();
            }
        });
        console.log('input handler attached');
    }
}

// Инициализация
function init() {
    console.log('init called');

    // Заполняем элементы
    elements = {
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
    };

    console.log('Elements loaded:', {
        humanizeBtn: !!elements.humanizeBtn,
        input: !!elements.input,
        result: !!elements.result
    });

    initEventListeners();
    updateUI();
}

// Делаем функции глобальными
window.processPendingText = processPendingText;
window.send = send;

// Запуск
init();