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
    loginModal: document.getElementById('loginModal'),
    registerModal: document.getElementById('registerModal'),
    loginError: document.getElementById('loginError'),
    registerError: document.getElementById('registerError'),
    registerSuccess: document.getElementById('registerSuccess'),
    loginEmail: document.getElementById('loginEmail'),
    loginPassword: document.getElementById('loginPassword'),
    registerUsername: document.getElementById('registerUsername'),
    registerEmail: document.getElementById('registerEmail'),
    registerPassword: document.getElementById('registerPassword')
};

// Функции модальных окон
function showLogin() {
    closeModals();
    elements.loginModal.classList.add('active');
    elements.loginEmail.value = '';
    elements.loginPassword.value = '';
    elements.loginError.textContent = '';
}

function showRegister() {
    closeModals();
    elements.registerModal.classList.add('active');
    elements.registerUsername.value = '';
    elements.registerEmail.value = '';
    elements.registerPassword.value = '';
    elements.registerError.textContent = '';
    elements.registerSuccess.textContent = '';
}

function closeModals() {
    elements.loginModal.classList.remove('active');
    elements.registerModal.classList.remove('active');
}

// Функции авторизации
async function handleLogin() {
    const email = elements.loginEmail.value;
    const password = elements.loginPassword.value;

    elements.loginError.textContent = '';

    if (!email || !password) {
        elements.loginError.textContent = 'Заполните все поля';
        return;
    }

    const result = await Auth.login(email, password);

    if (result.success) {
        closeModals();
        updateUI();
        alert('✅ Вход выполнен успешно!');
    } else {
        elements.loginError.textContent = result.error;
    }
}

async function handleRegister() {
    const username = elements.registerUsername.value;
    const email = elements.registerEmail.value;
    const password = elements.registerPassword.value;

    elements.registerError.textContent = '';
    elements.registerSuccess.textContent = '';

    if (!username || !email || !password) {
        elements.registerError.textContent = 'Заполните все поля';
        return;
    }

    if (password.length < 4) {
        elements.registerError.textContent = 'Пароль должен быть не менее 4 символов';
        return;
    }

    const result = await Auth.register(username, email, password);

    if (result.success) {
        elements.registerSuccess.textContent = '✅ Регистрация успешна! Теперь войдите.';
        setTimeout(() => {
            showLogin();
            elements.loginEmail.value = email;
        }, 1500);
    } else {
        elements.registerError.textContent = result.error;
    }
}

function handleLogout() {
    Auth.logout();
    updateUI();
    alert('👋 Вы вышли из аккаунта');
}

// Обновление интерфейса
function updateUI() {
    const user = Auth.getUser();

    if (user) {
        elements.userName.textContent = `👤 ${user.username}`;
        elements.authBtn.textContent = '🚪 Выйти';
        elements.authBtn.onclick = handleLogout;
    } else {
        elements.userName.textContent = '';
        elements.authBtn.textContent = '👤 Войти';
        elements.authBtn.onclick = showLogin;
    }
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

    const result = await API.humanize(
        requestData.text,
        requestData.intensity,
        requestData.tone,
        requestData.style,
        requestData.length,
        Auth.getToken()
    );

    if (result.ok) {
        elements.result.innerText = result.data.result;
    } else if (result.status === 401) {
        elements.result.innerText = '❌ Сессия истекла. Войдите заново.';
        Auth.logout();
        updateUI();
    } else {
        elements.result.innerText = '❌ Ошибка сервера';
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
    elements.humanizeBtn.addEventListener('click', send);
    elements.copyBtn.addEventListener('click', copyText);

    elements.input.addEventListener('keydown', (e) => {
        if (e.ctrlKey && e.key === 'Enter') {
            send();
        }
    });

    window.onclick = (event) => {
        if (event.target.classList.contains('modal')) {
            closeModals();
        }
    };

    window.login = handleLogin;
    window.register = handleRegister;
    window.showLogin = showLogin;
    window.showRegister = showRegister;
}

// Инициализация
function init() {
    initEventListeners();
    updateUI();
}

// Запуск
init();