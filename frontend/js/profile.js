// frontend/js/profile.js

async function loadProfile() {
    if (!Auth.isAuthenticated()) {
        window.location.href = '/';
        return;
    }

    const user = Auth.getUser();
    document.getElementById('profileEmail').textContent = user.email;
    document.getElementById('profileAvatar').src = getAvatarUrl(user.email);

    // Используем кэшированные данные, если есть
    let data = window.cachedSubscriptionData;

    if (!data) {
        // Если нет кэша, делаем запрос
        const response = await fetch('/subscription', {
            headers: { 'Authorization': `Bearer ${Auth.getToken()}` }
        });
        data = await response.json();
    }

    if (data?.success) {
        const sub = data.subscription;
        const usage = data.usage;

        document.getElementById('maxWords').textContent = sub.max_words;

        const profilePlanEl = document.getElementById('profilePlan');
        profilePlanEl.textContent =
            sub.plan_type === 'free' ? 'Бесплатный тариф' :
            sub.plan_type === 'premium' ? 'Premium тариф' : 'Pro тариф';

        const subscriptionPlanEl = document.getElementById('subscriptionPlan');
        subscriptionPlanEl.textContent = sub.plan_type.toUpperCase();

        const used = usage.total_requests_used;
        const limit = usage.total_requests_limit;
        const remaining = usage.remaining_requests;

        document.getElementById('balanceMainText').textContent =
            `${remaining} / ${limit} токенов осталось`;

        const fill = document.getElementById('requestsProgress');
        const percentRemaining = limit > 0 ? (remaining / limit) * 100 : 0;
        fill.style.width = `${percentRemaining}%`;

        if (percentRemaining <= 10) {
            fill.style.background = 'linear-gradient(90deg, #ef4444, #f59e0b)';
        } else if (percentRemaining <= 30) {
            fill.style.background = 'linear-gradient(90deg, #f59e0b, #eab308)';
        } else {
            fill.style.background = 'linear-gradient(90deg, #5787d9, #7c3aed)';
        }

        if (sub.end_date) {
            const expiryDate = new Date(sub.end_date);
            document.getElementById('subscriptionExpiry').textContent = expiryDate.toLocaleDateString('ru-RU');
            document.getElementById('expiryRow').style.display = 'flex';
        }

        const upgradeBtn = document.getElementById('upgradeBtn');
        if (sub.plan_type === 'pro') {
            upgradeBtn.textContent = 'Посмотреть тарифы';
        } else {
            upgradeBtn.textContent = 'Улучшить подписку';
        }

        await loadHistory();
    }
}

async function loadHistory() {
    try {
        const response = await fetch('/user/history', {
            headers: { 'Authorization': `Bearer ${Auth.getToken()}` }
        });
        const data = await response.json();

        const historyList = document.getElementById('historyList');
        if (data.success && data.history.length > 0) {
            historyList.innerHTML = data.history.map(item => `
                <div class="history-item">
                    <div class="history-date">${new Date(item.created_at).toLocaleString()}</div>
                    <div class="history-text">${item.original_text.substring(0, 100)}...</div>
                </div>
            `).join('');
        } else {
            historyList.innerHTML = '<div class="history-empty">История пуста</div>';
        }
    } catch (err) {
        console.error('Failed to load history:', err);
    }
}

function getAvatarUrl(email) {
    const md5 = CryptoJS.MD5(email.trim().toLowerCase()).toString();
    return `https://www.gravatar.com/avatar/${md5}?s=200&d=identicon`;
}

let passwordModal = null;

function openPasswordModal() {
    passwordModal = document.getElementById('passwordModal');
    if (passwordModal) passwordModal.style.display = 'flex';
}

function closePasswordModal() {
    if (passwordModal) passwordModal.style.display = 'none';
}

async function changePassword() {
    const oldPassword = document.getElementById('oldPassword')?.value;
    const newPassword = document.getElementById('newPassword')?.value;
    const confirmPassword = document.getElementById('confirmPassword')?.value;
    const errorDiv = document.getElementById('passwordError');

    if (!oldPassword || !newPassword) {
        errorDiv.textContent = 'Заполните все поля';
        errorDiv.style.display = 'block';
        return;
    }

    if (newPassword.length < 4) {
        errorDiv.textContent = 'Новый пароль должен быть не менее 4 символов';
        errorDiv.style.display = 'block';
        return;
    }

    if (newPassword !== confirmPassword) {
        errorDiv.textContent = 'Пароли не совпадают';
        errorDiv.style.display = 'block';
        return;
    }

    try {
        const response = await fetch('/user/change-password', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${Auth.getToken()}`
            },
            body: JSON.stringify({ old_password: oldPassword, new_password: newPassword })
        });

        const data = await response.json();
        if (response.ok) {
            showNotification('Пароль успешно изменён', 'success');
            closePasswordModal();
        } else {
            errorDiv.textContent = data.detail || 'Ошибка';
            errorDiv.style.display = 'block';
        }
    } catch (err) {
        errorDiv.textContent = 'Ошибка соединения';
        errorDiv.style.display = 'block';
    }
}

async function deleteAccount() {
    if (!confirm('Вы уверены? Аккаунт будет удалён безвозвратно.')) return;
    if (!confirm('Это последнее предупреждение! Введите "DELETE" для подтверждения.')) return;

    const confirmText = prompt('Введите DELETE для подтверждения:');
    if (confirmText !== 'DELETE') return;

    try {
        const response = await fetch('/user/delete', {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${Auth.getToken()}` }
        });

        if (response.ok) {
            Auth.logout();
            window.location.href = '/';
        }
    } catch (err) {
        showNotification('Ошибка при удалении', 'error');
    }
}

document.addEventListener('DOMContentLoaded', () => {
    loadProfile();
    document.getElementById('changePasswordBtn')?.addEventListener('click', openPasswordModal);
    document.getElementById('deleteAccountBtn')?.addEventListener('click', deleteAccount);
});

window.closePasswordModal = closePasswordModal;
window.changePassword = changePassword;

function getPlanClass(planType) {
    switch (planType) {
        case 'premium': return 'plan-premium';
        case 'pro': return 'plan-pro';
        default: return 'plan-free';
    }
}