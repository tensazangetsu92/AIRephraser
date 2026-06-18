function getProgressColor(pct) {
    if (pct <= 10) return 'linear-gradient(90deg, #ef4444, #f59e0b)';
    if (pct <= 30) return 'linear-gradient(90deg, #f59e0b, #eab308)';
    return 'linear-gradient(90deg, #5787d9, #7c3aed)';
}

async function loadProfile() {
    if (!Auth.isAuthenticated()) {
        window.location.href = '/';
        return;
    }

    const user = Auth.getUser();
    const profileEmail = document.getElementById('profileEmail');
    const profileAvatar = document.getElementById('profileAvatar');
    if (profileEmail) profileEmail.textContent = user.email;
    if (profileAvatar) profileAvatar.src = getAvatarUrl(user.email);

    try {
        const response = await fetch('/subscription', {
            headers: { 'Authorization': `Bearer ${Auth.getToken()}` }
        });
        const data = await response.json();

        if (!data?.success) return;

        const sub = data.subscription;
        const usage = data.usage;

        const planLabels = { free: 'Бесплатный тариф', premium: 'Premium тариф', pro: 'Pro тариф' };

        document.getElementById('maxWords')?.setAttribute('textContent', sub.max_words) ||
            (document.getElementById('maxWords') && (document.getElementById('maxWords').textContent = sub.max_words));
        const profilePlanEl = document.getElementById('profilePlan');
        if (profilePlanEl) profilePlanEl.textContent = planLabels[sub.plan_type] || 'Тариф';

        const subscriptionPlanEl = document.getElementById('subscriptionPlan');
        if (subscriptionPlanEl) subscriptionPlanEl.textContent = sub.plan_type.toUpperCase();

        const remaining = usage.remaining_requests;
        const limit = usage.total_requests_limit;
        const pct = limit > 0 ? (remaining / limit) * 100 : 0;

        const balanceText = document.getElementById('balanceMainText');
        if (balanceText) balanceText.textContent = `${remaining} / ${limit} токенов осталось`;

        const fill = document.getElementById('requestsProgress');
        if (fill) {
            fill.style.width = `${pct}%`;
            fill.style.background = getProgressColor(pct);
        }

        if (sub.end_date) {
            const expiryEl = document.getElementById('subscriptionExpiry');
            const expiryRow = document.getElementById('expiryRow');
            if (expiryEl) expiryEl.textContent = new Date(sub.end_date).toLocaleDateString('ru-RU');
            if (expiryRow) expiryRow.style.display = 'flex';
        }

        const upgradeBtn = document.getElementById('upgradeBtn');
        if (upgradeBtn) {
            upgradeBtn.textContent = sub.plan_type === 'pro' ? 'Посмотреть тарифы' : 'Улучшить подписку';
        }

        loadRecentHistory();
    } catch {
        showNotification('Ошибка загрузки профиля', 'error');
    }
}

async function loadRecentHistory() {
    const historyList = document.getElementById('historyList');
    if (!historyList) return;

    try {
        const response = await fetch('/user/history', {
            headers: { 'Authorization': `Bearer ${Auth.getToken()}` }
        });
        const data = await response.json();

        if (data.success && data.history?.length > 0) {
            historyList.innerHTML = data.history.map(item => `
                <div class="history-item">
                    <div class="history-date">${new Date(item.created_at).toLocaleString()}</div>
                    <div class="history-text">${escapeHtml(item.original_text.substring(0, 100))}...</div>
                </div>
            `).join('');
        } else {
            historyList.innerHTML = '<div class="history-empty">История пуста</div>';
        }
    } catch {
        historyList.innerHTML = '<div class="history-empty">Ошибка загрузки</div>';
    }
}

function openPasswordModal() {
    const modal = document.getElementById('passwordModal');
    if (modal) modal.style.display = 'flex';
}

function closePasswordModal() {
    const modal = document.getElementById('passwordModal');
    if (modal) modal.style.display = 'none';
}

async function changePassword() {
    const oldPassword = document.getElementById('oldPassword')?.value;
    const newPassword = document.getElementById('newPassword')?.value;
    const confirmPassword = document.getElementById('confirmPassword')?.value;
    const errorDiv = document.getElementById('passwordError');

    const showError = (msg) => {
        if (errorDiv) { errorDiv.textContent = msg; errorDiv.style.display = 'block'; }
    };

    if (!oldPassword || !newPassword) { showError('Заполните все поля'); return; }
    if (newPassword.length < 4) { showError('Новый пароль должен быть не менее 4 символов'); return; }
    if (newPassword !== confirmPassword) { showError('Пароли не совпадают'); return; }

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
            showError(data.detail || 'Ошибка');
        }
    } catch {
        showError('Ошибка соединения');
    }
}

async function deleteAccount() {
    if (!confirm('Вы уверены? Аккаунт будет удалён безвозвратно.')) return;
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
    } catch {
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