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

                if (typeof window.updateMaxWordsFromSubscription === 'function') {
                    window.updateMaxWordsFromSubscription(data.subscription);
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

            // Обновляем данные подписки на сервере
            await loadCurrentSubscription();

            // Обновляем баланс
            if (typeof updateBalanceDisplay === 'function') {
                await updateBalanceDisplay();
            }

            // Обновляем UI
            if (typeof window.updateUI === 'function') {
                window.updateUI();
            }

            // Обновляем лимит слов
            if (data.subscription && typeof window.updateMaxWordsFromSubscription === 'function') {
                window.updateMaxWordsFromSubscription(data.subscription);
            }

            // Перезагружаем страницу, чтобы всё сбросилось (опционально)
            // setTimeout(() => window.location.reload(), 1500);
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

            // Обновляем данные подписки на сервере
            await loadCurrentSubscription();

            // Обновляем баланс
            if (typeof updateBalanceDisplay === 'function') {
                await updateBalanceDisplay();
            }

            // Обновляем UI
            if (typeof window.updateUI === 'function') {
                window.updateUI();
            }

            // Обновляем лимит слов
            if (data.subscription && typeof window.updateMaxWordsFromSubscription === 'function') {
                window.updateMaxWordsFromSubscription(data.subscription);
            }

            // Перезагружаем страницу, чтобы всё сбросилось (опционально)
            // setTimeout(() => window.location.reload(), 1500);
        } else {
            showNotification('❌ Ошибка: ' + (data.detail || 'Не удалось активировать подписку'), 'error');
        }
    } catch (err) {
        console.error('Upgrade error:', err);
        showNotification('❌ Ошибка соединения с сервером', 'error');
    }
}

async function loadCurrentSubscription() {
    if (!Auth.isAuthenticated()) return;

    try {
        const response = await fetch('/subscription', {
            headers: { 'Authorization': `Bearer ${Auth.getToken()}` }
        });
        const data = await response.json();

        if (data.success) {
            // Сохраняем данные подписки глобально
            window.currentSubscription = data.subscription;

            // Обновляем лимит слов
            if (typeof window.updateMaxWordsFromSubscription === 'function') {
                window.updateMaxWordsFromSubscription(data.subscription);
            }

            await updateSubscriptionUI(data.subscription.plan_type);

            if (typeof window.updateLimitsDisplay === 'function') {
                window.updateLimitsDisplay(data.subscription, data.usage);
            }

            // Обновляем текст типа подписки в UI
            const subscribeTypeText = document.getElementById('subscribeTypeText');
            if (subscribeTypeText) {
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

            // Обновляем баланс
            if (typeof updateBalanceDisplay === 'function') {
                await updateBalanceDisplay();
            }

            // Обновляем статистику использованных запросов
            if (data.usage) {
                const used = data.usage.total_requests_used;
                const limit = data.usage.total_requests_limit;
                const remaining = data.usage.remaining_requests;
                console.log(`Использовано: ${used}, Лимит: ${limit}, Осталось: ${remaining}`);
            }
        }
    } catch (err) {
        console.error('Failed to load subscription:', err);
    }
}

async function updateBalanceDisplay() {
    if (!Auth.isAuthenticated()) return;

    try {
        const response = await fetch('/subscription', {
            headers: { 'Authorization': `Bearer ${Auth.getToken()}` }
        });
        const data = await response.json();

        if (data.success) {
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

            balanceText.innerHTML = `${remaining} / ${limit} запросов осталось`;
        }
    } catch (err) {
        console.error('Failed to update balance:', err);
    }
}

// Инициализация
document.addEventListener('DOMContentLoaded', () => {
    if (Auth.isAuthenticated()) {
        loadCurrentSubscription();
        updateBalanceDisplay();
    }
});

// Экспортируем функции
window.forceUpdateBalance = updateBalanceDisplay;
window.updateBalanceDisplay = updateBalanceDisplay;
window.loadCurrentSubscription = loadCurrentSubscription;