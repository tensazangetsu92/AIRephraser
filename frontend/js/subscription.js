// frontend/js/subscription.js

// Кэш данных
let cachedSubscriptionData = null;
let isFetching = false;

async function fetchSubscriptionData(force = false) {
    if (!Auth.isAuthenticated()) return null;

    // Если уже идёт запрос, ждём его
    if (isFetching) {
        // Ждём завершения текущего запроса
        let attempts = 0;
        while (isFetching && attempts < 50) {
            await new Promise(r => setTimeout(r, 50));
            attempts++;
        }
        return cachedSubscriptionData;
    }

    // Если есть кэш и не форсируем, возвращаем его
    if (!force && cachedSubscriptionData) {
        return cachedSubscriptionData;
    }

    isFetching = true;

    try {
        const response = await fetch('/subscription', {
            headers: { 'Authorization': `Bearer ${Auth.getToken()}` }
        });
        const data = await response.json();

        if (data.success) {
            cachedSubscriptionData = data;
            window.currentSubscription = data.subscription;
            return data;
        }
    } catch (err) {
        console.error('Failed to fetch subscription:', err);
    } finally {
        isFetching = false;
    }

    return null;
}

// Обновление UI карточек подписки (без запроса, использует переданные данные)
function updateSubscriptionUIFromData(data, activePlan = null) {
    activePlan = activePlan || data?.subscription?.plan_type;
    if (!activePlan) return;

    const planLevel = { 'free': 0, 'premium': 1, 'pro': 2 };
    const currentLevel = planLevel[activePlan] || 0;

    const cards = document.querySelectorAll('.tariff-card');
    cards.forEach(card => {
        const plan = card.getAttribute('data-plan');
        const btn = card.querySelector('.tariff-btn');
        const planLevelValue = planLevel[plan] || 0;

        if (planLevelValue <= currentLevel) {
            if (plan === activePlan) {
                btn.textContent = 'Текущий план';
                btn.disabled = true;
                btn.classList.add('tariff-btn-current');
            } else {
                btn.textContent = 'Уже доступен';
                btn.disabled = true;
                btn.classList.add('tariff-btn-current', 'tariff-btn-included');
            }
        } else {
            btn.textContent = 'Выбрать тариф';
            btn.disabled = false;
            btn.classList.remove('tariff-btn-current', 'tariff-btn-included');
            if (plan === 'premium') {
                btn.onclick = () => upgradeToPremium();
            } else if (plan === 'pro') {
                btn.onclick = () => upgradeToPro();
            }
        }
    });
}

// Обновление баланса из данных (без запроса)
function updateBalanceDisplayFromData(data) {
    if (!data?.success) return;

    const balanceBlock = document.getElementById('balanceBlock');
    const balanceBarFill = document.getElementById('balanceBarFill');
    const balanceText = document.getElementById('balanceText');

    if (!balanceBlock || !balanceBarFill || !balanceText) return;

    const used = data.usage.total_requests_used;
    const limit = data.subscription.total_requests;
    const remaining = limit - used;

    balanceBlock.style.display = 'block';

    const percentRemaining = (remaining / limit) * 100;
    balanceBarFill.style.width = `${percentRemaining}%`;

    if (percentRemaining <= 10) {
        balanceBarFill.style.background = 'linear-gradient(90deg, #ef4444, #f59e0b)';
    } else if (percentRemaining <= 30) {
        balanceBarFill.style.background = 'linear-gradient(90deg, #f59e0b, #eab308)';
    } else {
        balanceBarFill.style.background = 'linear-gradient(90deg, #5787d9, #7c3aed)';
    }

    balanceText.innerHTML = `${remaining} / ${limit} токенов осталось`;
}

// ОСНОВНАЯ ФУНКЦИЯ - один запрос, обновляет всё
async function refreshAllSubscriptionData() {
    const data = await fetchSubscriptionData(true);
    if (data) {
        // Обновляем всё из одного запроса
        updateBalanceDisplayFromData(data);
        updateSubscriptionUIFromData(data);
        updateSubscriptionText(data);
        updateMaxWordsLimit(data);
    }
}

function updateSubscriptionText(data) {
    const subscribeTypeText = document.getElementById('subscribeTypeText');
    if (subscribeTypeText && data?.subscription) {
        const planType = data.subscription.plan_type;
        let planText = '';
        switch (planType) {
            case 'free': planText = 'Базовая подписка'; break;
            case 'premium': planText = 'Premium подписка'; break;
            case 'pro': planText = 'Pro подписка'; break;
            default: planText = 'Подписка';
        }
        subscribeTypeText.textContent = planText;
    }
}

function updateMaxWordsLimit(data) {
    if (typeof window.updateMaxWordsFromSubscription === 'function' && data?.subscription) {
        window.updateMaxWordsFromSubscription(data.subscription);
    }
}

// Обновление подписки Premium
async function upgradeToPremium() {
    if (!Auth.isAuthenticated()) {
        showNotification('Пожалуйста, войдите в аккаунт, чтобы оформить подписку', 'warning');
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
            showNotification('✅ Подписка Premium активирована!', 'success');
            // Сбрасываем кэш и обновляем всё
            cachedSubscriptionData = null;
            await refreshAllSubscriptionData();
            if (typeof window.updateUI === 'function') window.updateUI();
        } else {
            showNotification('❌ Ошибка: ' + (data.detail || 'Не удалось активировать подписку'), 'error');
        }
    } catch (err) {
        console.error('Upgrade error:', err);
        showNotification('❌ Ошибка соединения с сервером', 'error');
    }
}

// Обновление подписки Pro
async function upgradeToPro() {
    if (!Auth.isAuthenticated()) {
        showNotification('Пожалуйста, войдите в аккаунт, чтобы оформить подписку', 'warning');
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
            showNotification('✅ Подписка Pro активирована!', 'success');
            // Сбрасываем кэш и обновляем всё
            cachedSubscriptionData = null;
            await refreshAllSubscriptionData();
            if (typeof window.updateUI === 'function') window.updateUI();
        } else {
            showNotification('❌ Ошибка: ' + (data.detail || 'Не удалось активировать подписку'), 'error');
        }
    } catch (err) {
        console.error('Upgrade error:', err);
        showNotification('❌ Ошибка соединения с сервером', 'error');
    }
}

// Основной метод для внешних вызовов
async function loadCurrentSubscription() {
    await refreshAllSubscriptionData();
}

async function updateBalanceDisplay() {
    // Просто обновляем из кэша, без запроса
    if (cachedSubscriptionData) {
        updateBalanceDisplayFromData(cachedSubscriptionData);
    } else {
        await refreshAllSubscriptionData();
    }
}

// Инициализация - один запрос
document.addEventListener('DOMContentLoaded', () => {
    if (Auth.isAuthenticated()) {
        refreshAllSubscriptionData();
    }
});

// Экспортируем функции
window.forceUpdateBalance = refreshAllSubscriptionData;
window.updateBalanceDisplay = updateBalanceDisplay;
window.loadCurrentSubscription = loadCurrentSubscription;
window.refreshAllSubscriptionData = refreshAllSubscriptionData;