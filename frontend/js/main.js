// frontend/js/main.js
// DOM элементы - объявляем сразу и заполняем
let elements = {};

// Константа для максимального количества символов
const MAX_CHARS = 1000;

// Функция для обновления счетчика символов
function updateCharCounter() {
    if (!elements.input || !elements.charCounter) return;

    const currentLength = elements.input.value.length;
    const remaining = MAX_CHARS - currentLength;

    // Обновляем текст счетчика
    elements.charCounter.textContent = `Количество символов ${currentLength}/${MAX_CHARS}`;

    // Меняем цвет в зависимости от количества символов
    if (currentLength > MAX_CHARS) {
        elements.charCounter.style.color = '#ef4444'; // Красный - превышение
        elements.charCounter.style.fontWeight = 'bold';
    } else if (currentLength > MAX_CHARS * 0.9) {
        elements.charCounter.style.color = '#f59e0b'; // Оранжевый -接近 лимит
        elements.charCounter.style.fontWeight = 'normal';
    } else {
        elements.charCounter.style.color = '#f0f0f0'; // Обычный цвет
        elements.charCounter.style.fontWeight = 'normal';
    }
}

// Проверка лимита символов
function isWithinCharLimit(text) {
    return text.length <= MAX_CHARS;
}

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
            authBtn.textContent = 'Выйти';
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
            authBtn.textContent = 'Войти';
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

    const text = elements.input.value; // Не используем trim() чтобы не терять пробелы
    const textLength = text.length;

    console.log('Text length:', textLength);
    console.log('Auth.isAuthenticated():', Auth.isAuthenticated());

    // Проверка на пустой текст
    if (!text.trim()) {
        if (elements.result) elements.result.innerText = '⚠️ Пожалуйста, введите текст для обработки';
        return;
    }

    // ========== ПРОВЕРКА ЛИМИТА СИМВОЛОВ ==========
    if (!isWithinCharLimit(text)) {
        const errorMessage = `❌ Превышен лимит символов! Максимум ${MAX_CHARS} символов. Сейчас ${textLength}/${MAX_CHARS}.`;
        if (elements.result) elements.result.innerText = errorMessage;

        // Подсвечиваем счетчик красным
        if (elements.charCounter) {
            elements.charCounter.style.color = '#ef4444';
            elements.charCounter.style.fontWeight = 'bold';
        }

        return;
    }
    // =============================================

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
        // Проверяем лимит для отложенного текста
        if (isWithinCharLimit(pendingText)) {
            const text = pendingText;
            pendingText = null;
            await processText(text);
        } else {
            const textLength = pendingText.length;
            const errorMessage = `❌ Превышен лимит символов! Максимум ${MAX_CHARS} символов. Сейчас ${textLength}/${MAX_CHARS}.`;
            if (elements.result) elements.result.innerText = errorMessage;
            alert(`⚠️ Превышен лимит символов!\n\nМаксимум: ${MAX_CHARS} символов\nВы ввели: ${textLength} символов`);
            pendingText = null;
        }
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
        // Обновление счетчика при вводе
        elements.input.addEventListener('input', updateCharCounter);

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
        charCounter: document.getElementById('charCounter'), // Добавляем счетчик
    };

    console.log('Elements loaded:', {
        humanizeBtn: !!elements.humanizeBtn,
        input: !!elements.input,
        result: !!elements.result,
        charCounter: !!elements.charCounter
    });

    // Инициализируем счетчик
    if (elements.input && elements.charCounter) {
        updateCharCounter();
    }

    initEventListeners();
    updateUI();
}

// frontend/js/main.js - добавьте эти функции

// Обновление подписки
async function upgradeToPremium() {
    if (!Auth.isAuthenticated()) {
        alert('Пожалуйста, войдите в аккаунт, чтобы оформить подписку');
        Auth.showAuthModal();
        return;
    }

    try {
        const response = await fetch('/subscription/upgrade', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${Auth.getToken()}`
            },
            body: JSON.stringify({ plan_type: "premium" })
        });

        const data = await response.json();

        if (response.ok) {
            alert('✅ Подписка Premium активирована!');
            updateSubscriptionUI('premium');
            updateUI();
        } else {
            alert('❌ Ошибка: ' + (data.detail || 'Не удалось активировать подписку'));
        }
    } catch (err) {
        console.error('Upgrade error:', err);
        alert('❌ Ошибка соединения с сервером');
    }
}

async function upgradeToPro() {
    if (!Auth.isAuthenticated()) {
        alert('Пожалуйста, войдите в аккаунт, чтобы оформить подписку');
        Auth.showAuthModal();
        return;
    }

    try {
        const response = await fetch('/subscription/upgrade', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${Auth.getToken()}`
            },
            body: JSON.stringify({ plan_type: "pro" })
        });

        const data = await response.json();

        if (response.ok) {
            alert('✅ Подписка Pro активирована!');
            updateSubscriptionUI('pro');
            updateUI();
        } else {
            alert('❌ Ошибка: ' + (data.detail || 'Не удалось активировать подписку'));
        }
    } catch (err) {
        console.error('Upgrade error:', err);
        alert('❌ Ошибка соединения с сервером');
    }
}

// Обновление UI карточек подписки
// Обновление UI карточек подписки
async function updateSubscriptionUI(activePlan = null) {
    // Если план не передан, получаем текущий с сервера
    if (!activePlan && Auth.isAuthenticated()) {
        try {
            const response = await fetch('/subscription', {
                headers: { 'Authorization': `Bearer ${Auth.getToken()}` }
            });
            const data = await response.json();
            if (data.success) {
                activePlan = data.subscription.plan_type;
            }
        } catch (err) {
            console.error('Failed to get subscription:', err);
            return;
        }
    }

    // Приоритет планов (чем выше уровень, тем больше)
    const planLevel = { 'free': 0, 'premium': 1, 'pro': 2 };
    const currentLevel = planLevel[activePlan] || 0;

    // Обновляем кнопки в карточках
    const cards = document.querySelectorAll('.tariff-card');
    cards.forEach(card => {
        const plan = card.getAttribute('data-plan');
        const btn = card.querySelector('.tariff-btn');
        const planLevelValue = planLevel[plan] || 0;

        if (planLevelValue <= currentLevel) {
            // План равен текущему или ниже - считаем доступным
            if (plan === activePlan) {
                // Текущий активный план
                btn.textContent = 'Текущий план';
                btn.disabled = true;
                btn.classList.add('tariff-btn-current');
            } else {
                // Более низкий план (уже включён в текущий)
                btn.textContent = 'Уже доступен';
                btn.disabled = true;
                btn.classList.add('tariff-btn-current', 'tariff-btn-included');
            }
        } else {
            // Более высокий план - нужно апгрейдить
            btn.textContent = 'Выбрать тариф';
            btn.disabled = false;
            btn.classList.remove('tariff-btn-current', 'tariff-btn-included');

            // Назначаем правильную функцию
            if (plan === 'premium') {
                btn.onclick = () => upgradeToPremium();
            } else if (plan === 'pro') {
                btn.onclick = () => upgradeToPro();
            }
        }
    });
}

// Получить текущую подписку при загрузке
async function loadCurrentSubscription() {
    if (!Auth.isAuthenticated()) return;

    try {
        const response = await fetch('/subscription', {
            headers: { 'Authorization': `Bearer ${Auth.getToken()}` }
        });
        const data = await response.json();

        if (data.success) {
            updateSubscriptionUI(data.subscription.plan_type);

            // Обновляем лимиты в интерфейсе
            updateLimitsDisplay(data.subscription, data.usage);
        }
    } catch (err) {
        console.error('Failed to load subscription:', err);
    }
}

// Отображение лимитов пользователю
function updateLimitsDisplay(subscription, usage) {
    const charCounter = document.getElementById('charCounter');
    if (charCounter) {
        const maxLength = subscription.max_text_length || 1000;
        const currentLength = document.getElementById('input')?.value.length || 0;
        charCounter.textContent = `Количество символов ${currentLength}/${maxLength}`;

        if (currentLength > maxLength) {
            charCounter.style.color = '#ef4444';
        } else {
            charCounter.style.color = 'var(--text-secondary)';
        }
    }

    // Можно добавить отображение оставшихся запросов
    if (usage && usage.remaining_requests !== undefined) {
        const remainingSpan = document.getElementById('remainingRequests');
        if (remainingSpan) {
            remainingSpan.textContent = `Осталось запросов: ${usage.remaining_requests}`;
        }
    }
}

// Обновляем существующую функцию updateUI, добавив вызов loadCurrentSubscription
// Найдите существующую функцию updateUI и добавьте в неё вызов loadCurrentSubscription()
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
            authBtn.textContent = 'Выйти';
            authBtn.onclick = () => {
                Auth.logout();
                updateUI();
            };
        }

        // Загружаем информацию о подписке после входа
        loadCurrentSubscription();
    } else {
        if (userNameSpan) {
            userNameSpan.textContent = '';
        }
        if (authBtn) {
            authBtn.textContent = 'Войти';
            authBtn.onclick = () => Auth.showAuthModal();
        }

        // Сбрасываем UI карточек, если не авторизован
        const cards = document.querySelectorAll('.tariff-card');
        cards.forEach(card => {
            const plan = card.getAttribute('data-plan');
            const btn = card.querySelector('.tariff-btn');

            if (plan === 'free') {
                btn.textContent = 'Текущий план';
                btn.disabled = true;
            } else {
                btn.textContent = 'Выбрать тариф';
                btn.disabled = false;
                if (plan === 'premium') {
                    btn.onclick = () => upgradeToPremium();
                } else if (plan === 'pro') {
                    btn.onclick = () => upgradeToPro();
                }
            }
        });
    }
}

// Делаем функции глобальными
window.processPendingText = processPendingText;
window.send = send;

// Запуск
init();