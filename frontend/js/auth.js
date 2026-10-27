// The short-lived access token lives only in memory. The persistent session is
// an HttpOnly refresh cookie and therefore cannot be read by page scripts.
try { localStorage.removeItem('token'); } catch { /* storage can be unavailable */ }

const Auth = {
    token: null,
    pendingEmail: null,
    mode: 'login',
    refreshPromise: null,
    resendTimerId: null,
    resendDeadlineKey: 'humary_email_code_resend_deadline',

    getToken() { return this.token; },
    setToken(token) {
        this.token = token || null;
        try { localStorage.removeItem('token'); } catch { /* no-op */ }
    },
    getUser() {
        try {
            const value = localStorage.getItem('user');
            return value ? JSON.parse(value) : null;
        } catch { return null; }
    },
    setUser(user) {
        if (user) localStorage.setItem('user', JSON.stringify(user));
        else localStorage.removeItem('user');
    },
    isAuthenticated() { return Boolean(this.token); },

    getAccessTokenExpiresAt(token = this.token) {
        try {
            const payload = token?.split('.')[1];
            if (!payload) return 0;
            const normalized = payload.replace(/-/g, '+').replace(/_/g, '/');
            const data = JSON.parse(atob(normalized.padEnd(Math.ceil(normalized.length / 4) * 4, '=')));
            return Number(data.exp) * 1000 || 0;
        } catch { return 0; }
    },
    async refreshAccessToken() {
        if (this.refreshPromise) return this.refreshPromise;
        this.refreshPromise = (async () => {
            try {
                const response = await fetch('/auth/refresh', { method: 'POST', credentials: 'same-origin' });
                const data = await response.json().catch(() => ({}));
                if (!response.ok || !data.access_token) {
                    this.clearExpiredSession();
                    return null;
                }
                this.setToken(data.access_token);
                if (data.user) this.setUser(data.user);
                return data.access_token;
            } catch { return null; }
            finally { this.refreshPromise = null; }
        })();
        return this.refreshPromise;
    },
    async getValidAccessToken() {
        const expiresAt = this.getAccessTokenExpiresAt();
        return !this.token || !expiresAt || expiresAt <= Date.now() + 60_000
            ? this.refreshAccessToken() : this.token;
    },
    async authorizedFetch(url, options = {}) {
        const send = async (token) => {
            const headers = new Headers(options.headers || {});
            headers.set('Authorization', `Bearer ${token}`);
            return fetch(url, { ...options, headers, credentials: options.credentials || 'same-origin' });
        };
        let token = await this.getValidAccessToken();
        if (!token) throw new Error('Authentication required');
        let response = await send(token);
        if (response.status !== 401) return response;
        token = await this.refreshAccessToken();
        if (!token) return response;
        response = await send(token);
        if (response.status === 401) this.clearExpiredSession();
        return response;
    },

    getSafeReturnPath(value) {
        return typeof value === 'string' && value.startsWith('/') && !value.startsWith('//') && !value.startsWith('/auth') ? value : null;
    },
    getReturnPath() {
        const next = new URLSearchParams(window.location.search).get('next');
        return this.getSafeReturnPath(next) || this.getSafeReturnPath(sessionStorage.getItem('auth_return_to')) || '/';
    },
    redirectAfterAuth() {
        const path = this.getReturnPath();
        sessionStorage.removeItem('auth_return_to');
        window.location.replace(path);
    },
    clearExpiredSession() {
        this.setToken(null);
        this.setUser(null);
        if (typeof window.clearSubscriptionData === 'function') window.clearSubscriptionData();
        if (typeof updateUI === 'function') updateUI();
    },
    async restoreSession() {
        if (!await this.getValidAccessToken()) {
            this.setUser(null);
            return false;
        }
        try {
            const result = await API.getMe();
            if (result.ok && result.data?.success && result.data.user) {
                this.setUser(result.data.user);
                return true;
            }
            if (result.status === 401) this.clearExpiredSession();
        } catch { /* preserve local state while the network is unavailable */ }
        return false;
    },

    async prepareLegalConsent() {
        if (!this.ensureCookieConsent() || !this.ensureTermsAcceptance()) return false;
        try {
            const result = await API.acceptLegalDocuments();
            if (result.ok) return true;
            this.showError(result.data?.detail || (typeof t === 'function'
                ? t('auth_terms_accept_required')
                : 'Примите Условия использования и ознакомьтесь с Политикой конфиденциальности'));
        } catch {
            this.showError(typeof t === 'function' ? t('auth_network_error') : 'Ошибка сети. Проверьте подключение и попробуйте ещё раз.');
        }
        return false;
    },

    isRegistrationMode() {
        return this.mode === 'register';
    },

    setMode(mode = 'login') {
        this.mode = mode === 'register' ? 'register' : 'login';
        const legalConsent = document.getElementById('authLegalConsent');
        const termsCheckbox = document.getElementById('authTermsAccepted');
        if (legalConsent) legalConsent.hidden = !this.isRegistrationMode();
        if (termsCheckbox) {
            termsCheckbox.required = this.isRegistrationMode();
            if (!this.isRegistrationMode()) termsCheckbox.checked = false;
        }
        const toggle = document.getElementById('authModeToggle');
        if (toggle) {
            toggle.textContent = this.isRegistrationMode()
                ? 'Уже есть аккаунт? Войти'
                : 'Нет аккаунта? Регистрация';
        }
    },

    async startOAuth(provider) {
        if (!this.ensureCookieConsent()) return;
        if (this.isRegistrationMode() && !await this.prepareLegalConsent()) return;
        const registration = this.isRegistrationMode() ? '?registration=true' : '';
        window.location.assign(`/auth/${provider}/login${registration}`);
    },
    async loginWithYandex() {
        await this.startOAuth('yandex');
    },
    async loginWithVK() {
        await this.startOAuth('vk');
    },
    async handleOAuthCallback() { return false; },
    async logout() {
        try { await fetch('/auth/logout', { method: 'POST', credentials: 'same-origin' }); }
        finally { this.clearExpiredSession(); window.location.reload(); }
    },
    showAuthModal(mode = 'login') {
        if (window.location.pathname !== '/auth') {
            const next = `${window.location.pathname}${window.location.search}${window.location.hash}`;
            window.location.assign(`/auth?next=${encodeURIComponent(next)}&mode=${mode === 'register' ? 'register' : 'login'}`);
            return;
        }
        this.setMode(mode);
        this.resetForm();
        setTimeout(() => document.getElementById('authEmail')?.focus(), 100);
    },
    closeAuthModal() { this.resetForm(); },
    resetForm() {
        this.pendingEmail = null;
        this.clearResendTimer();
        document.getElementById('authForm')?.reset();
        const code = document.getElementById('verificationCode');
        if (code) code.value = '';
        this.setError('authError');
        this.setError('verificationError');
        this.closeVerificationModal();
    },
    setError(id, message = '') {
        const element = document.getElementById(id);
        if (!element) return;
        element.textContent = message;
        element.style.display = message ? 'block' : 'none';
    },
    showError(message) { this.setError('authError', message); },
    getResendButtonLabel(seconds) {
        const template = typeof t === 'function'
            ? t('auth_email_code_resend_wait')
            : 'Отправить повторно через {seconds} сек.';
        return template.replace('{seconds}', String(seconds));
    },
    clearResendTimer({ clearStoredDeadline = true } = {}) {
        if (this.resendTimerId) window.clearInterval(this.resendTimerId);
        this.resendTimerId = null;
        if (clearStoredDeadline) sessionStorage.removeItem(this.resendDeadlineKey);
    },
    startResendTimer(seconds = 60) {
        // The server-side resend window is one minute. Never display a
        // longer client timer if a legacy record has a clock-shifted date.
        const normalizedSeconds = Math.min(60, Math.max(1, Math.ceil(Number(seconds) || 60)));
        const deadline = Date.now() + normalizedSeconds * 1000;
        sessionStorage.setItem(this.resendDeadlineKey, JSON.stringify({
            email: this.pendingEmail,
            deadline,
        }));
        this.clearResendTimer({ clearStoredDeadline: false });

        const button = document.getElementById('resendCodeBtn');
        const render = () => {
            const remaining = Math.max(0, Math.ceil((deadline - Date.now()) / 1000));
            if (!button) return;
            button.disabled = remaining > 0;
            button.textContent = remaining > 0
                ? this.getResendButtonLabel(remaining)
                : (typeof t === 'function' ? t('resend_code') : 'Отправить код повторно');
            if (remaining === 0) this.clearResendTimer();
        };

        render();
        this.resendTimerId = window.setInterval(render, 250);
    },
    restoreResendTimer() {
        try {
            const saved = JSON.parse(sessionStorage.getItem(this.resendDeadlineKey) || 'null');
            if (!saved || saved.email !== this.pendingEmail || Number(saved.deadline) <= Date.now()) return;
            this.startResendTimer((Number(saved.deadline) - Date.now()) / 1000);
        } catch {
            this.clearResendTimer();
        }
    },
    ensureCookieConsent() {
        const checkbox = document.getElementById('authCookieConsent');
        const preferences = typeof window.getCookieConsentPreferences === 'function'
            ? window.getCookieConsentPreferences()
            : null;
        if (checkbox?.checked || preferences?.essential) {
            if (checkbox) checkbox.checked = true;
            return true;
        }
        this.showError(typeof t === 'function' ? t('auth_cookie_consent_required') : 'Подтвердите согласие на использование cookie для авторизации');
        checkbox?.focus();
        return false;
    },

    ensureTermsAcceptance() {
        const checkbox = document.getElementById('authTermsAccepted');
        if (checkbox?.checked) return true;
        this.showError(typeof t === 'function'
            ? t('auth_terms_accept_required')
            : 'Примите Условия использования и ознакомьтесь с Политикой конфиденциальности');
        checkbox?.focus();
        return false;
    },

    async handleSubmit() {
        const email = document.getElementById('authEmail')?.value.trim();
        if (!email) return this.showError(typeof t === 'function' ? t('auth_email_required') : 'Введите email');
        if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return this.showError(typeof t === 'function' ? t('auth_email_invalid') : 'Введите корректный email');
        if (!this.ensureCookieConsent()) return;
        if (this.isRegistrationMode() && !await this.prepareLegalConsent()) return;

        const button = document.getElementById('authSubmitBtn');
        const initialText = button?.textContent;
        this.setError('authError');
        if (button) { button.disabled = true; button.textContent = typeof t === 'function' ? t('auth_email_code_sending') : 'Отправляем код…'; }
        try {
            const result = await API.requestEmailCode(email, this.isRegistrationMode());
            // A code may have been sent just before a page reload. The server
            // deliberately does not send another one for a minute, but the
            // user must still be able to enter the existing code.
            const existingCodePending = result.status === 429
                && result.data?.detail === 'Код уже отправлен. Повторите попытку через минуту.';
            if (!result.ok && !existingCodePending) {
                this.showError(result.data?.detail || (typeof t === 'function' ? t('auth_email_code_send_error') : 'Не удалось отправить код.'));
                return;
            }
            this.pendingEmail = result.data.email || email;
            this.startResendTimer(result.retryAfter || result.data.retry_after || 60);
            this.showVerificationModal(this.pendingEmail);
        } catch {
            this.showError(typeof t === 'function' ? t('auth_network_error') : 'Ошибка сети. Проверьте подключение и попробуйте ещё раз.');
        } finally {
            if (button) { button.disabled = false; button.textContent = initialText; }
        }
    },
    showVerificationModal(email) {
        document.getElementById('authFormCard')?.classList.add('is-hidden');
        const message = document.getElementById('verificationEmail');
        if (message) message.textContent = `${typeof t === 'function' ? t('auth_email_code_sent_to') : 'Код отправлен на'} ${email}`;
        document.getElementById('verificationModal')?.classList.add('is-visible');
        this.restoreResendTimer();
        this.setError('verificationError');
        setTimeout(() => document.getElementById('verificationCode')?.focus(), 100);
    },
    closeVerificationModal() {
        document.getElementById('verificationModal')?.classList.remove('is-visible');
        document.getElementById('authFormCard')?.classList.remove('is-hidden');
    },
    async confirmEmailCode() {
        const code = document.getElementById('verificationCode')?.value.trim();
        if (!this.pendingEmail) return this.showError(typeof t === 'function' ? t('auth_email_code_restart') : 'Запросите новый код.');
        if (!/^\d{6}$/.test(code || '')) return this.setError('verificationError', typeof t === 'function' ? t('auth_email_code_invalid') : 'Введите 6-значный код из письма');
        if (this.isRegistrationMode() && !await this.prepareLegalConsent()) return;

        const button = document.getElementById('verificationSubmitBtn');
        const initialText = button?.textContent;
        this.setError('verificationError');
        if (button) { button.disabled = true; button.textContent = typeof t === 'function' ? t('auth_email_code_verifying') : 'Проверяем код…'; }
        try {
            const result = await API.confirmEmailCode(this.pendingEmail, code, this.isRegistrationMode());
            if (!result.ok) {
                this.setError('verificationError', result.data?.detail || (typeof t === 'function' ? t('auth_email_code_confirm_error') : 'Не удалось подтвердить код.'));
                return;
            }
            this.setToken(result.data.access_token);
            this.setUser(result.data.user);
            if (typeof updateUI === 'function') updateUI();
            if (typeof updateUserMenu === 'function') updateUserMenu();
            this.redirectAfterAuth();
        } catch {
            this.setError('verificationError', typeof t === 'function' ? t('auth_network_error') : 'Ошибка сети. Проверьте подключение и попробуйте ещё раз.');
        } finally {
            if (button) { button.disabled = false; button.textContent = initialText; }
        }
    },
    async resendEmailCode() {
        if (!this.pendingEmail) return this.showError(typeof t === 'function' ? t('auth_email_code_restart') : 'Запросите новый код.');
        if (!this.ensureCookieConsent()) return;
        if (this.isRegistrationMode() && !await this.prepareLegalConsent()) return;
        this.setError('verificationError');
        try {
            const result = await API.requestEmailCode(this.pendingEmail, this.isRegistrationMode());
            if (result.ok) {
                this.startResendTimer(result.retryAfter || result.data.retry_after || 60);
                if (typeof showNotification === 'function') showNotification(typeof t === 'function' ? t('auth_email_code_resent') : 'Код отправлен повторно.', 'success');
            } else {
                if (result.status === 429 && result.retryAfter) this.startResendTimer(result.retryAfter);
                this.setError('verificationError', result.data?.detail || (typeof t === 'function' ? t('auth_email_code_send_error') : 'Не удалось отправить код.'));
            }
        } catch {
            this.setError('verificationError', typeof t === 'function' ? t('auth_network_error') : 'Ошибка сети. Проверьте подключение и попробуйте ещё раз.');
        }
    },
};

function initAuthPage() {
    if (!document.getElementById('authPage')) return;
    const cookieCheckbox = document.getElementById('authCookieConsent');
    const syncCookieConsent = () => {
        const preferences = typeof window.getCookieConsentPreferences === 'function'
            ? window.getCookieConsentPreferences()
            : null;
        if (cookieCheckbox && preferences?.essential) cookieCheckbox.checked = true;
    };

    cookieCheckbox?.addEventListener('change', () => {
        if (!cookieCheckbox.checked) return;
        window.acceptEssentialCookies?.();
        Auth.setError('authError');
    });
    window.addEventListener('cookieConsentChanged', syncCookieConsent);
    syncCookieConsent();
    const search = new URLSearchParams(window.location.search);
    Auth.setMode(search.get('mode'));
    if (search.get('error') === 'registration_required') {
        Auth.showError('Аккаунт не найден. Выберите регистрацию и примите Условия использования.');
    }
    document.getElementById('authForm')?.addEventListener('submit', (event) => { event.preventDefault(); Auth.handleSubmit(); });
    document.getElementById('authModeToggle')?.addEventListener('click', () => {
        Auth.setMode(Auth.isRegistrationMode() ? 'login' : 'register');
        const next = new URLSearchParams(window.location.search);
        next.set('mode', Auth.mode);
        next.delete('error');
        window.history.replaceState(null, '', `${window.location.pathname}?${next.toString()}`);
        Auth.setError('authError');
    });
    document.getElementById('yandexLoginBtn')?.addEventListener('click', () => Auth.loginWithYandex());
    document.getElementById('vkLoginBtn')?.addEventListener('click', () => Auth.loginWithVK());
    document.getElementById('verificationSubmitBtn')?.addEventListener('click', () => Auth.confirmEmailCode());
    document.getElementById('resendCodeBtn')?.addEventListener('click', () => Auth.resendEmailCode());
    document.getElementById('verificationCode')?.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') Auth.confirmEmailCode();
    });
    setTimeout(() => document.getElementById('authEmail')?.focus(), 100);
}

window.showAuthModal = () => Auth.showAuthModal();
window.closeAuthModal = () => Auth.closeAuthModal();
document.addEventListener('DOMContentLoaded', async () => {
    const handledOAuthCallback = await Auth.handleOAuthCallback();
    initAuthPage();
    document.getElementById('authBtn')?.addEventListener('click', () => Auth.showAuthModal('login'));
    document.getElementById('registerBtn')?.addEventListener('click', () => Auth.showAuthModal('register'));
    if (!handledOAuthCallback) {
        const restored = await Auth.restoreSession();
        if (restored && window.location.pathname === '/auth') Auth.redirectAfterAuth();
    }
    if (typeof updateUI === 'function') updateUI();
});
