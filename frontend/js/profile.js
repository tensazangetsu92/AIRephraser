function getProgressColor(pct) {
    if (pct <= 10) return 'linear-gradient(90deg, #ef4444, #f59e0b)';
    if (pct <= 30) return 'linear-gradient(90deg, #f59e0b, #eab308)';
    return 'linear-gradient(90deg, var(--accent-blue), var(--main-color))';
}

function profileText(key, fallback) {
    return typeof window.t === 'function' ? window.t(key) : fallback;
}

function setProfileLoading(isLoading) {
    document.getElementById('profileContainer')?.setAttribute('aria-busy', String(isLoading));
    if (isLoading) return;
    document.querySelectorAll('#profileContainer .skeleton').forEach(element => {
        element.classList.remove('skeleton', 'skeleton-text', 'skeleton-text--short', 'skeleton-text--medium', 'skeleton-text--title');
    });
}

async function loadProfile() {
    if (!Auth.isAuthenticated()) {
        // The access token deliberately exists only in memory. After a normal
        // page navigation it must be restored from the HttpOnly refresh cookie
        // before treating the visitor as logged out.
        await Auth.restoreSession();
    }

    if (!Auth.isAuthenticated()) {
        window.location.href = '/auth?next=/profile';
        return;
    }

    const user = Auth.getUser();
    const profileEmail = document.getElementById('profileEmail');
    const profileAvatar = document.getElementById('profileAvatar');
    if (profileEmail) profileEmail.textContent = user.email || '—';
    if (profileAvatar) setUserAvatar(profileAvatar, user);

    try {
        const data = typeof window.getSubscriptionData === 'function'
            ? await window.getSubscriptionData()
            : null;

        if (!data?.success) return;

        const sub = data.subscription;
        const usage = data.usage;

        const maxWordsEl = document.getElementById('maxWords');
        if (maxWordsEl) {
            maxWordsEl.textContent = sub.max_words_per_request;
        }

        const profilePlanEl = document.getElementById('profilePlan');
        if (profilePlanEl) profilePlanEl.textContent = profileText(`plan_label_${sub.plan_type}`, 'Тариф');

        const subscriptionPlanEl = document.getElementById('subscriptionPlan');
        if (subscriptionPlanEl) subscriptionPlanEl.textContent = sub.plan_type.toUpperCase();

        const balanceText = document.getElementById('balanceMainText');
        const fill = document.getElementById('requestsProgress');

        if (usage.is_unlimited) {
            if (balanceText) balanceText.textContent = profileText('unlimited_words', 'Безлимит');
            if (fill) {
                fill.style.width = '100%';
                fill.style.background = 'linear-gradient(90deg, var(--accent-blue), var(--main-color))';
            }
        } else {
            const remaining = usage.remaining_words;
            const limit = usage.word_limit;
            const pct = limit > 0 ? (remaining / limit) * 100 : 0;

            if (balanceText) {
                balanceText.textContent = sub.free_entitlement_available === false && limit === 0
                    ? `${remaining} ${profileText('words', 'слов')}`
                    : `${remaining} / ${limit} ${profileText('words_remaining', 'слов осталось')}`;
            }
            if (fill) {
                fill.style.width = `${pct}%`;
                fill.style.background = getProgressColor(pct);
            }
        }

        if (sub.end_date) {
            const expiryEl = document.getElementById('subscriptionExpiry');
            const expiryRow = document.getElementById('expiryRow');
            if (expiryEl) expiryEl.textContent = new Date(sub.end_date).toLocaleDateString(window.currentLang === 'en' ? 'en-US' : 'ru-RU');
            if (expiryRow) expiryRow.style.display = 'flex';
        }

        const upgradeBtn = document.getElementById('upgradeBtn');
        if (upgradeBtn) {
            upgradeBtn.textContent = sub.plan_type === 'unlimited'
                ? profileText('view_pricing', 'Посмотреть тарифы')
                : profileText('upgrade_subscription', 'Улучшить подписку');
        }

        loadRecentHistory();
    } catch {
        showNotification('Ошибка загрузки профиля', 'error');
    } finally {
        setProfileLoading(false);
    }
}

async function loadRecentHistory() {
    const historyList = document.getElementById('historyList');
    if (!historyList) return;

    try {
        const cacheKey = 'history:profile-recent';
        let data = typeof window.getCachedUserData === 'function'
            ? window.getCachedUserData(cacheKey)
            : null;

        if (!data) {
            const response = await Auth.authorizedFetch('/user/history', {
                headers: { 'Authorization': `Bearer ${Auth.getToken()}` }
            });
            data = await response.json();
            if (data?.success && typeof window.setCachedUserData === 'function') {
                window.setCachedUserData(cacheKey, data, 60_000);
            }
        }

        if (data.success && data.history?.length > 0) {
            const items = data.history.map(item => {
                const preview = String(item.original_preview || '');
                const shortPreview = preview.substring(0, 100);
                const suffix = item.original_is_truncated || preview.length > shortPreview.length ? '...' : '';
                const historyItem = document.createElement('div');
                historyItem.className = 'history-item';
                const date = document.createElement('div');
                date.className = 'history-date';
                date.textContent = new Date(item.created_at).toLocaleString();
                const text = document.createElement('div');
                text.className = 'history-text';
                text.textContent = `${shortPreview}${suffix}`;
                historyItem.append(date, text);
                return historyItem;
            });
            historyList.replaceChildren(...items);
        } else {
            const empty = document.createElement('div');
            empty.className = 'history-empty';
            empty.textContent = 'История пуста';
            historyList.replaceChildren(empty);
        }
    } catch {
        const error = document.createElement('div');
        error.className = 'history-empty';
        error.textContent = 'Ошибка загрузки';
        historyList.replaceChildren(error);
    }
}

function setDeleteAccountError(message = '') {
    const error = document.getElementById('deleteAccountError');
    if (!error) return;
    error.textContent = message;
    error.hidden = !message;
}

function closeDeleteAccountModal() {
    const modal = document.getElementById('deleteAccountModal');
    if (!modal) return;
    modal.classList.remove('active');
    modal.setAttribute('aria-hidden', 'true');
    document.getElementById('deleteAccountConfirmation').value = '';
    document.getElementById('deleteAccountConfirm').disabled = true;
    setDeleteAccountError();
}

function openDeleteAccountModal() {
    const modal = document.getElementById('deleteAccountModal');
    if (!modal) return;
    modal.classList.add('active');
    modal.setAttribute('aria-hidden', 'false');
    document.getElementById('deleteAccountConfirmation').value = '';
    document.getElementById('deleteAccountConfirm').disabled = true;
    setDeleteAccountError();
    window.setTimeout(() => document.getElementById('deleteAccountConfirmation')?.focus(), 100);
}

async function deleteAccount() {
    const confirmButton = document.getElementById('deleteAccountConfirm');
    const confirmation = document.getElementById('deleteAccountConfirmation')?.value.trim();
    if (confirmation !== 'DELETE' || !confirmButton) return;

    const originalText = confirmButton.textContent;
    confirmButton.disabled = true;
    confirmButton.textContent = profileText('profile_deleting', 'Удаляем…');
    setDeleteAccountError();
    try {
        const response = await Auth.authorizedFetch('/user/delete', {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${Auth.getToken()}`
            },
            body: JSON.stringify({ confirmation })
        });
        if (response.ok) {
            Auth.clearExpiredSession();
            window.location.assign('/');
            return;
        }
        const data = await response.json().catch(() => ({}));
        setDeleteAccountError(data.detail || profileText('profile_delete_error', 'Не удалось удалить аккаунт. Попробуйте позже.'));
    } catch {
        setDeleteAccountError(profileText('profile_network_error', 'Ошибка соединения. Проверьте интернет и повторите попытку.'));
    } finally {
        if (!document.getElementById('deleteAccountModal')?.classList.contains('active')) return;
        confirmButton.disabled = confirmation !== 'DELETE';
        confirmButton.textContent = originalText;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    loadProfile();
    document.getElementById('langToggle')?.addEventListener('click', () => {
        if (typeof toggleLang === 'function') toggleLang();
    });
    document.getElementById('deleteAccountBtn')?.addEventListener('click', openDeleteAccountModal);
    document.getElementById('deleteAccountClose')?.addEventListener('click', closeDeleteAccountModal);
    document.getElementById('deleteAccountCancel')?.addEventListener('click', closeDeleteAccountModal);
    document.getElementById('deleteAccountConfirm')?.addEventListener('click', deleteAccount);
    document.getElementById('deleteAccountConfirmation')?.addEventListener('input', (event) => {
        document.getElementById('deleteAccountConfirm').disabled = event.target.value.trim() !== 'DELETE';
        setDeleteAccountError();
    });
    document.getElementById('deleteAccountModal')?.addEventListener('click', (event) => {
        if (event.target.id === 'deleteAccountModal') closeDeleteAccountModal();
    });
    document.addEventListener('keydown', (event) => {
        if (event.key !== 'Escape') return;
        closeDeleteAccountModal();
    });
});
