// frontend/js/subscription.js

// Обновление UI карточек подписки
async function updateSubscriptionUI(activePlan = null) {
    if (!activePlan && Auth.isAuthenticated()) {
        try {
            const response = await fetch('/subscription', {
                headers: { 'Authorization': `Bearer ${Auth.getToken()}` }
            });
            const data = await response.json();
            if (data.success) {
                activePlan = data.subscription.plan_type;
                window.currentSubscription = data.subscription;

                // 👇 ВАЖНО: обновляем лимит символов
                if (typeof window.updateMaxCharsFromSubscription === 'function') {
                    window.updateMaxCharsFromSubscription(data.subscription);
                }

                if (typeof window.updateLimitsDisplay === 'function') {
                    window.updateLimitsDisplay(data.subscription, data.usage);
                }
            }
        } catch (err) {
            console.error('Failed to get subscription:', err);
            return;
        }
    }

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

// Обновление подписки Premium
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

            // Обновляем лимит символов
            if (data.subscription && typeof window.updateMaxCharsFromSubscription === 'function') {
                window.updateMaxCharsFromSubscription(data.subscription);
            }

            await updateSubscriptionUI('premium');
            if (typeof window.updateUI === 'function') window.updateUI();
        } else {
            alert('❌ Ошибка: ' + (data.detail || 'Не удалось активировать подписку'));
        }
    } catch (err) {
        console.error('Upgrade error:', err);
        alert('❌ Ошибка соединения с сервером');
    }
}

// Обновление подписки Pro
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

            // 👇 ВАЖНО: обновляем лимит символов
            if (data.subscription && typeof window.updateMaxCharsFromSubscription === 'function') {
                window.updateMaxCharsFromSubscription(data.subscription);
            }

            await updateSubscriptionUI('pro');
            if (typeof window.updateUI === 'function') window.updateUI();
        } else {
            alert('❌ Ошибка: ' + (data.detail || 'Не удалось активировать подписку'));
        }
    } catch (err) {
        console.error('Upgrade error:', err);
        alert('❌ Ошибка соединения с сервером');
    }
}

// Загрузка текущей подписки
async function loadCurrentSubscription() {
    if (!Auth.isAuthenticated()) return;

    try {
        const response = await fetch('/subscription', {
            headers: { 'Authorization': `Bearer ${Auth.getToken()}` }
        });
        const data = await response.json();

        if (data.success) {
            // 👇 ВАЖНО: обновляем лимит символов
            if (typeof window.updateMaxCharsFromSubscription === 'function') {
                window.updateMaxCharsFromSubscription(data.subscription);
            }

            await updateSubscriptionUI(data.subscription.plan_type);

            if (typeof window.updateLimitsDisplay === 'function') {
                window.updateLimitsDisplay(data.subscription, data.usage);
            }
        }
    } catch (err) {
        console.error('Failed to load subscription:', err);
    }
}

