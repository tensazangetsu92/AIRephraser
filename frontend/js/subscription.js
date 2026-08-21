let cachedSubscriptionData = null;
let isFetching = false;

function getSubscriptionErrorMessage(detail, fallback) {
    if (typeof detail === 'string' && detail.trim()) return detail;
    if (Array.isArray(detail)) {
        const messages = detail
            .map(item => typeof item?.msg === 'string' ? item.msg : '')
            .filter(Boolean);
        if (messages.length) return messages.join('. ');
    }
    return fallback;
}

function subscriptionLabel(planType) {
    const key = `subscription_${planType}`;
    return typeof window.t === 'function' ? window.t(key) : planType;
}

function clearSubscriptionData() {
    cachedSubscriptionData = null;
    window.currentSubscription = null;
    ['balanceBlock', 'extraBalanceBlock'].forEach(id => {
        const element = document.getElementById(id);
        if (element) element.style.display = 'none';
    });
}

window.clearSubscriptionData = clearSubscriptionData;

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

        if (response.status === 401) {
            Auth.clearExpiredSession();
            return null;
        }

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
            btn.textContent = plan === activePlan
                ? (typeof window.t === 'function' ? window.t('current_plan') : 'Текущий план')
                : (typeof window.t === 'function' ? window.t('already_available') : 'Уже доступен');
            btn.disabled = true;
            btn.classList.add('tariff-btn-current');
            if (plan !== activePlan) btn.classList.add('tariff-btn-included');
        } else {
            btn.textContent = typeof window.t === 'function' ? window.t('select_plan') : 'Выбрать тариф';
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
    const extraBalanceBlock = document.getElementById('extraBalanceBlock');
    const extraBalanceBarFill = document.getElementById('extraBalanceBarFill');
    const extraBalanceText = document.getElementById('extraBalanceText');
    if (!balanceBlock || !balanceBarFill || !balanceText) return;

    const usage = data.usage;
    balanceBlock.style.display = 'block';

    const wordBalance = data.word_balance || {};
    const extraWords = (wordBalance.bonus_words || 0) + (wordBalance.purchased_words || 0);
    if (extraBalanceBlock && extraBalanceBarFill && extraBalanceText) {
        extraBalanceBlock.style.display = extraWords > 0 ? 'block' : 'none';
        const extraTotal = (wordBalance.bonus_total_words || 0) + (wordBalance.purchased_total_words || 0);
        const extraPct = extraTotal > 0 ? Math.min(100, (extraWords / extraTotal) * 100) : 0;
        extraBalanceBarFill.style.setProperty('--visible-percent', `${extraPct}%`);
        extraBalanceText.textContent = `${extraWords} ${typeof window.t === 'function' ? window.t('words') : 'слов'}`;
    }

    if (usage.is_unlimited) {
        balanceBarFill.style.setProperty('--visible-percent', '100%');
        balanceText.textContent = typeof window.t === 'function' ? window.t('unlimited_words') : 'Безлимит';
        return;
    }

    const used = usage.words_used;
    const limit = usage.word_limit;
    const remaining = usage.remaining_words;
    const pct = limit > 0 ? (remaining / limit) * 100 : 0;

    balanceBarFill.style.setProperty('--visible-percent', `${pct}%`);

    balanceText.textContent = `${remaining} / ${limit} ${typeof window.t === 'function' ? window.t('words') : 'Слов'}`;
}

function updateSubscriptionText(data) {
    const el = document.getElementById('subscribeTypeText');
    if (!el || !data?.subscription) return;
    el.textContent = subscriptionLabel(data.subscription.plan_type);
}

function updateMaxWordsLimit(data) {
    if (typeof window.updateMaxWordsFromSubscription === 'function' && data?.subscription) {
        window.updateMaxWordsFromSubscription(data.subscription);
    }
}

function updateStudyWorkMaxWordsLimit(data) {
    const maxWords = Number(data?.subscription?.study_work_max_words_per_request);
    window.currentStudyWorkMaxWords = Number.isFinite(maxWords) && maxWords > 0 ? maxWords : 5000;
    window.dispatchEvent(new CustomEvent('studyWorkLimitUpdated', {
        detail: { maxWords: window.currentStudyWorkMaxWords }
    }));
}

async function refreshAllSubscriptionData() {
    const data = await fetchSubscriptionData(true);
    if (data) {
        updateBalanceDisplayFromData(data);
        updateSubscriptionUIFromData(data);
        updateSubscriptionText(data);
        updateMaxWordsLimit(data);
        updateStudyWorkMaxWordsLimit(data);
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
            showNotification(getSubscriptionErrorMessage(data.detail, 'Не удалось активировать подписку'), 'error');
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

    document.querySelectorAll('.word-pack-btn').forEach(button => {
        button.addEventListener('click', () => {
            if (!Auth.isAuthenticated()) {
                showNotification('Войдите в аккаунт, чтобы купить пакет слов', 'warning');
                Auth.showAuthModal();
                return;
            }
            showNotification('Оплата пакетов слов будет подключена после настройки эквайринга', 'info');
        });
    });
});

// Handle package purchases before the legacy placeholder click handler below.
document.addEventListener('click', (event) => {
    const button = event.target.closest('.word-pack-btn');
    if (!button) return;

    event.preventDefault();
    event.stopImmediatePropagation();

    if (!Auth.isAuthenticated()) {
        showNotification('Войдите в аккаунт, чтобы купить пакет слов', 'warning');
        Auth.showAuthModal();
        return;
    }

    purchaseWordPackage(button.dataset.package);
}, true);

async function purchaseWordPackage(packageId) {
    try {
        const response = await fetch('/subscription/word-packages/purchase', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${Auth.getToken()}`
            },
            body: JSON.stringify({ package_id: packageId })
        });
        const data = await response.json();
        if (!response.ok) throw new Error(getSubscriptionErrorMessage(data.detail, 'Не удалось купить пакет'));

        showNotification(`Пакет активирован: ${data.package.words} слов`, 'success');
        cachedSubscriptionData = null;
        await refreshAllSubscriptionData();
    } catch (error) {
        showNotification(error.message || 'Ошибка покупки пакета', 'error');
    }
}

window.forceUpdateBalance = refreshAllSubscriptionData;
window.updateBalanceDisplay = updateBalanceDisplay;
window.loadCurrentSubscription = loadCurrentSubscription;
window.refreshAllSubscriptionData = refreshAllSubscriptionData;
window.upgradeToPremium = () => upgradePlan('premium');
window.upgradeToPro = () => upgradePlan('pro');
window.upgradeToUnlimited = () => upgradePlan('unlimited');
