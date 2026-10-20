let cachedSubscriptionData = null;
let subscriptionRequest = null;

const SUBSCRIPTION_CACHE_PREFIX = 'humary.subscription.v1.';
const SUBSCRIPTION_CACHE_TTL_MS = 60_000;

function subscriptionCacheKey() {
    const userId = Auth.getUser()?.id;
    return userId ? `${SUBSCRIPTION_CACHE_PREFIX}${userId}` : null;
}

function readStoredSubscriptionData() {
    const key = subscriptionCacheKey();
    if (!key) return null;

    try {
        const saved = JSON.parse(sessionStorage.getItem(key) || 'null');
        if (!saved?.data || Number(saved.expiresAt) <= Date.now()) {
            sessionStorage.removeItem(key);
            return null;
        }
        return saved.data;
    } catch {
        return null;
    }
}

function storeSubscriptionData(data) {
    const key = subscriptionCacheKey();
    if (!key || !data?.success) return;

    try {
        sessionStorage.setItem(key, JSON.stringify({
            data,
            expiresAt: Date.now() + SUBSCRIPTION_CACHE_TTL_MS,
        }));
    } catch {
        // The interface still works if the browser blocks sessionStorage.
    }
}

function subscriptionLabel(planType) {
    const key = `subscription_${planType}`;
    return typeof window.t === 'function' ? window.t(key) : planType;
}

function showPaymentsUnavailable() {
    const message = typeof window.t === 'function'
        ? window.t('payments_unavailable')
        : 'Онлайн-оплата пока не подключена.';
    showNotification(message, 'info');
}

function clearSubscriptionData() {
    cachedSubscriptionData = null;
    window.currentSubscription = null;
    if (typeof window.clearCachedUserData === 'function') window.clearCachedUserData();
    try {
        Object.keys(sessionStorage)
            .filter(key => key.startsWith(SUBSCRIPTION_CACHE_PREFIX))
            .forEach(key => sessionStorage.removeItem(key));
    } catch {
        // The in-memory cache has already been cleared.
    }
    ['balanceBlock', 'extraBalanceBlock'].forEach(id => {
        const element = document.getElementById(id);
        if (element) element.style.display = 'none';
    });
    setSidebarBalanceLoading(false);
    const trialBadge = document.getElementById('studyWorkTrialBadge');
    if (trialBadge) trialBadge.hidden = true;
}

window.clearSubscriptionData = clearSubscriptionData;

function resetTariffCards() {
    document.querySelectorAll('.tariff-card').forEach(card => {
        const plan = card.getAttribute('data-plan');
        const btn = card.querySelector('.tariff-btn');
        if (!btn) return;

        btn.textContent = typeof window.t === 'function' ? window.t('select_plan') : 'Оформить';
        btn.disabled = false;
        btn.classList.remove('tariff-btn-current', 'tariff-btn-included');
        btn.onclick = plan === 'free'
            ? () => Auth.showAuthModal('register')
            : showPaymentsUnavailable;
    });
}

window.resetTariffCards = resetTariffCards;

async function fetchSubscriptionData(force = false) {
    if (!Auth.isAuthenticated()) return null;

    if (!force && cachedSubscriptionData) return cachedSubscriptionData;

    if (!force) {
        const storedData = readStoredSubscriptionData();
        if (storedData) {
            cachedSubscriptionData = storedData;
            window.currentSubscription = storedData.subscription;
            return storedData;
        }
    }

    if (subscriptionRequest) return subscriptionRequest;

    subscriptionRequest = (async () => {
        try {
            const response = await Auth.authorizedFetch('/subscription', {
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
                storeSubscriptionData(data);
                return data;
            }
        } catch {
        } finally {
            subscriptionRequest = null;
        }

        return null;
    })();

    return subscriptionRequest;
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
                ? (typeof window.t === 'function' ? window.t('current_plan') : 'Текущий тариф')
                : (typeof window.t === 'function' ? window.t('already_available') : 'Уже доступен');
            btn.disabled = true;
            btn.classList.add('tariff-btn-current');
            if (plan !== activePlan) btn.classList.add('tariff-btn-included');
        } else {
            btn.textContent = typeof window.t === 'function' ? window.t('select_plan') : 'Оформить';
            btn.disabled = false;
            btn.classList.remove('tariff-btn-current', 'tariff-btn-included');
            btn.onclick = showPaymentsUnavailable;
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

    setSidebarBalanceLoading(false);
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

    if (data.subscription?.free_entitlement_available === false && limit === 0) {
        balanceText.textContent = `${remaining} ${typeof window.t === 'function' ? window.t('words') : 'Слов'}`;
    } else {
        balanceText.textContent = `${remaining} / ${limit} ${typeof window.t === 'function' ? window.t('words') : 'Слов'}`;
    }
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

function setSidebarBalanceLoading(isLoading) {
    const skeleton = document.getElementById('balanceLoadingSkeleton');
    if (!skeleton) return;

    // A temporary access token can exist while the refresh-cookie session is
    // still being restored (or has just failed).  Do not show account UI
    // until the user profile is confirmed as well.
    const hasConfirmedUser = Auth.isAuthenticated() && Boolean(Auth.getUser());
    const balanceIsVisible = document.getElementById('balanceBlock')?.style.display === 'block';
    // Keep the last known balance on screen during a background refresh. This
    // also prevents a late request from rendering both the skeleton and the
    // already populated balance card at the same time.
    const shouldShow = Boolean(isLoading && hasConfirmedUser && !balanceIsVisible);
    skeleton.hidden = !shouldShow;
    skeleton.setAttribute('aria-hidden', String(!shouldShow));
}

function updateStudyWorkMaxWordsLimit(data) {
    const maxWords = Number(data?.subscription?.study_work_max_words_per_request);
    window.currentStudyWorkMaxWords = Number.isFinite(maxWords) && maxWords > 0 ? maxWords : 5000;
    window.dispatchEvent(new CustomEvent('studyWorkLimitUpdated', {
        detail: { maxWords: window.currentStudyWorkMaxWords }
    }));
}

function updateStudyWorkTrialBadge(data) {
    const badge = document.getElementById('studyWorkTrialBadge');
    if (!badge) return;
    const isAvailable = Auth.isAuthenticated() && data?.study_work_trial?.status === 'available';
    badge.hidden = !isAvailable;
}

function markStudyWorkTrialUsed() {
    const badge = document.getElementById('studyWorkTrialBadge');
    if (badge) badge.hidden = true;
    if (cachedSubscriptionData?.study_work_trial) {
        cachedSubscriptionData.study_work_trial.status = 'used';
        storeSubscriptionData(cachedSubscriptionData);
    }
}

async function refreshAllSubscriptionData(force = false) {
    const data = await fetchSubscriptionData(force);
    if (data) {
        updateBalanceDisplayFromData(data);
        updateSubscriptionUIFromData(data);
        updateSubscriptionText(data);
        updateMaxWordsLimit(data);
        updateStudyWorkMaxWordsLimit(data);
        updateStudyWorkTrialBadge(data);
    }
}

function upgradePlan() {
    if (!Auth.isAuthenticated()) {
        showNotification('Пожалуйста, войдите в аккаунт', 'warning');
        Auth.showAuthModal();
        return;
    }
    showPaymentsUnavailable();
}

async function loadCurrentSubscription() {
    if (!Auth.isAuthenticated() || !Auth.getUser()) {
        setSidebarBalanceLoading(false);
        return;
    }

    const shouldShowLoading = !cachedSubscriptionData;
    if (shouldShowLoading) setSidebarBalanceLoading(true);
    try {
        await refreshAllSubscriptionData();
    } finally {
        if (shouldShowLoading) setSidebarBalanceLoading(false);
    }
}

async function updateBalanceDisplay() {
    if (cachedSubscriptionData) {
        updateBalanceDisplayFromData(cachedSubscriptionData);
    } else {
        await refreshAllSubscriptionData();
    }
}

document.addEventListener('DOMContentLoaded', () => {
    if (Auth.isAuthenticated()) {
        refreshAllSubscriptionData();
    } else {
        resetTariffCards();
        setSidebarBalanceLoading(false);
    }

    document.querySelectorAll('.word-pack-btn').forEach(button => {
        button.addEventListener('click', () => {
            if (!Auth.isAuthenticated()) {
                showNotification('Войдите в аккаунт, чтобы купить пакет слов', 'warning');
                Auth.showAuthModal();
                return;
            }
            showPaymentsUnavailable();
        });
    });
});

window.forceUpdateBalance = () => refreshAllSubscriptionData(true);
window.updateBalanceDisplay = updateBalanceDisplay;
window.loadCurrentSubscription = loadCurrentSubscription;
window.refreshAllSubscriptionData = refreshAllSubscriptionData;
window.getSubscriptionData = fetchSubscriptionData;
window.markStudyWorkTrialUsed = markStudyWorkTrialUsed;
window.upgradeToPremium = () => upgradePlan('premium');
window.upgradeToPro = () => upgradePlan('pro');
window.upgradeToUnlimited = () => upgradePlan('unlimited');
