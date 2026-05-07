// frontend/js/subscription.js

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
            await updateSubscriptionUI('premium');
            if (typeof updateUI === 'function') updateUI();
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
            await updateSubscriptionUI('pro');
            if (typeof updateUI === 'function') updateUI();
        } else {
            alert('❌ Ошибка: ' + (data.detail || 'Не удалось активировать подписку'));
        }
    } catch (err) {
        console.error('Upgrade error:', err);
        alert('❌ Ошибка соединения с сервером');
    }
}

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
                if (typeof updateLimitsDisplay === 'function') {
                    updateLimitsDisplay(data.subscription, data.usage);
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

// Сброс карточек для неавторизованного пользователя
function resetTariffCards() {
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
            if (plan === 'premium') btn.onclick = () => upgradeToPremium();
            else if (plan === 'pro') btn.onclick = () => upgradeToPro();
        }
    });
}

// Загрузка текущей подписки
async function loadCurrentSubscription() {
    if (!Auth.isAuthenticated()) return;
    await updateSubscriptionUI();
}

// Делаем функции глобальными
window.upgradeToPremium = upgradeToPremium;
window.upgradeToPro = upgradeToPro;
window.updateSubscriptionUI = updateSubscriptionUI;
window.resetTariffCards = resetTariffCards;
window.loadCurrentSubscription = loadCurrentSubscription;