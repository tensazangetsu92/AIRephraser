let cachedSubscriptionData = null;
let isFetching = false;

async function fetchSubscriptionData(force = false) {
    if (!Auth.isAuthenticated()) return null;

    if (isFetching) {
        let attempts = 0;
        while (isFetching && attempts < 50) {
            await new Promise(r => setTimeout(r, 50));
            attempts++;
        }
        return cachedSubscriptionData;
    }

    if (!force && cachedSubscriptionData) return cachedSubscriptionData;

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
    } catch {
    } finally {
        isFetching = false;
    }

    return null;
}

function updateSubscriptionUIFromData(data, activePlan = null) {
    activePlan = activePlan || data?.subscription?.plan_type;
    if (!activePlan) return;

    const planLevel = { free: 0, premium: 1, pro: 2, unlimited: 3 };
    const currentLevel = planLevel[activePlan] || 0;

    document.querySelectorAll('.tariff-card').forEach(card => {
        const plan = card.getAttribute('data-plan');
        const btn = card.querySelector('.tariff-btn');
        if (!btn) return;
        const planLevelValue = planLevel[plan] || 0;

        if (planLevelValue <= currentLevel) {
            btn.textContent = plan === activePlan ? 'Текущий план' : 'Уже доступен';
            btn.disabled = true;
            btn.classList.add('tariff-btn-current');
            if (plan !== activePlan) btn.classList.add('tariff-btn-included');
        } else {
            btn.textContent = 'Выбрать тариф';
            btn.disabled = false;
            btn.classList.remove('tariff-btn-current', 'tariff-btn-included');
            if (plan === 'premium') btn.onclick = () => upgradePlan('premium');
            if (plan === 'pro') btn.onclick = () => upgradePlan('pro');
            if (plan === 'unlimited') btn.onclick = () => upgradePlan('unlimited');
        }
    });
}

function updateBalanceDisplayFromData(data) {
    if (!data?.success) return;

    const balanceBlock = document.getElementById('balanceBlock');
    const balanceBarFill = document.getElementById('balanceBarFill');
    const balanceText = document.getElementById('balanceText');
    if (!balanceBlock || !balanceBarFill || !balanceText) return;

    const usage = data.usage;
    balanceBlock.style.display = 'block';

    if (usage.is_unlimited) {
        balanceBarFill.style.width = '100%';
        balanceBarFill.style.background = 'linear-gradient(90deg, #5787d9, #7c3aed)';
        balanceText.innerHTML = `Безлимит слов`;
        return;
    }

    const used = usage.words_used;
    const limit = usage.word_limit;
    const remaining = usage.remaining_words;
    const pct = limit > 0 ? (remaining / limit) * 100 : 0;

    balanceBarFill.style.width = `${pct}%`;
    balanceBarFill.style.background = pct <= 10
        ? 'linear-gradient(90deg, #ef4444, #f59e0b)'
        : pct <= 30
            ? 'linear-gradient(90deg, #f59e0b, #eab308)'
            : 'linear-gradient(90deg, #5787d9, #7c3aed)';

    balanceText.innerHTML = `${remaining} / ${limit} слов`;
}

function updateSubscriptionText(data) {
    const el = document.getElementById('subscribeTypeText');
    if (!el || !data?.subscription) return;
    const labels = {
        free: 'Базовая подписка',
        premium: 'Premium подписка',
        pro: 'Pro подписка',
        unlimited: 'Безлимитная подписка'
    };
    el.textContent = labels[data.subscription.plan_type] || 'Подписка';
}

function updateMaxWordsLimit(data) {
    if (typeof window.updateMaxWordsFromSubscription === 'function' && data?.subscription) {
        window.updateMaxWordsFromSubscription(data.subscription);
    }
}

async function refreshAllSubscriptionData() {
    const data = await fetchSubscriptionData(true);
    if (data) {
        updateBalanceDisplayFromData(data);
        updateSubscriptionUIFromData(data);
        updateSubscriptionText(data);
        updateMaxWordsLimit(data);
    }
}

async function upgradePlan(planType) {
    if (!Auth.isAuthenticated()) {
        showNotification('Пожалуйста, войдите в аккаунт', 'warning');
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
            body: JSON.stringify({ plan_type: planType })
        });
        const data = await response.json();

        if (response.ok) {
            const labels = { premium: 'Premium', pro: 'Pro', unlimited: 'Безлимит' };
            showNotification(`Подписка ${labels[planType]} активирована!`, 'success');
            cachedSubscriptionData = null;
            await refreshAllSubscriptionData();
            if (typeof window.updateUI === 'function') window.updateUI();
        } else {
            showNotification(data.detail || 'Не удалось активировать подписку', 'error');
        }
    } catch {
        showNotification('Ошибка соединения с сервером', 'error');
    }
}

async function loadCurrentSubscription() {
    await refreshAllSubscriptionData();
}

async function updateBalanceDisplay() {
    if (cachedSubscriptionData) {
        updateBalanceDisplayFromData(cachedSubscriptionData);
    } else {
        await refreshAllSubscriptionData();
    }
}

document.addEventListener('DOMContentLoaded', () => {
    if (Auth.isAuthenticated()) refreshAllSubscriptionData();
});

window.forceUpdateBalance = refreshAllSubscriptionData;
window.updateBalanceDisplay = updateBalanceDisplay;
window.loadCurrentSubscription = loadCurrentSubscription;
window.refreshAllSubscriptionData = refreshAllSubscriptionData;
window.upgradeToPremium = () => upgradePlan('premium');
window.upgradeToPro = () => upgradePlan('pro');
window.upgradeToUnlimited = () => upgradePlan('unlimited');