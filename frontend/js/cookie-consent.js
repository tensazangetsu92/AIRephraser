(function () {
    const STORAGE_KEY = 'humary_cookie_preferences';
    // Version 4 adds Yandex Metrica to the optional analytics category.
    const CONSENT_VERSION = 4;

    const copy = {
        ru: {
            text: 'Humary использует обязательные cookie для входа, безопасности и работы сайта. Аналитические cookie подключаются только с вашего согласия.',
            policy: 'Подробнее о cookie',
            essential: 'Только необходимые',
            acceptAll: 'Принять все',
            settings: 'Настроить',
            settingsTitle: 'Настройки cookie',
            closeSettings: 'Закрыть настройки cookie',
            requiredTitle: 'Обязательные',
            requiredText: 'Нужны для входа, защиты аккаунта и сохранения сессии. Их нельзя отключить.',
            analyticsTitle: 'Аналитические',
            analyticsText: 'Помогают понять, как используется сайт. По умолчанию выключены.',
            save: 'Сохранить выбор',
        },
        en: {
            text: 'Humary uses essential cookies for sign-in, security, and core site functionality. Analytics cookies are enabled only with your consent.',
            policy: 'Learn more about cookies',
            essential: 'Essential only',
            acceptAll: 'Accept all',
            settings: 'Settings',
            settingsTitle: 'Cookie settings',
            closeSettings: 'Close cookie settings',
            requiredTitle: 'Essential',
            requiredText: 'Required for sign-in, account security, and session storage. They cannot be disabled.',
            analyticsTitle: 'Analytics',
            analyticsText: 'Help us understand how the site is used. Disabled by default.',
            save: 'Save preferences',
        },
    };

    function getLanguage() {
        return localStorage.getItem('language') === 'en' ? 'en' : 'ru';
    }

    function getPreferences() {
        try {
            const preferences = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
            return preferences?.version === CONSENT_VERSION ? preferences : null;
        } catch {
            return null;
        }
    }

    function savePreferences(analytics) {
        const preferences = {
            version: CONSENT_VERSION,
            essential: true,
            analytics: Boolean(analytics),
            savedAt: new Date().toISOString(),
        };
        localStorage.setItem(STORAGE_KEY, JSON.stringify(preferences));
        window.cookieConsentPreferences = preferences;
        window.dispatchEvent(new CustomEvent('cookieConsentChanged', { detail: preferences }));
        const banner = document.getElementById('cookieConsentBanner');
        if (banner) {
            banner.classList.remove('cookie-consent-settings-open');
            banner.setAttribute('hidden', '');
        }
    }

    function acceptEssentialCookies() {
        savePreferences(false);
    }

    function ensureBanner() {
        let banner = document.getElementById('cookieConsentBanner');
        if (banner) return banner;

        const text = copy[getLanguage()];
        banner = document.createElement('section');
        banner.id = 'cookieConsentBanner';
        banner.className = 'cookie-consent-banner';
        banner.setAttribute('role', 'region');
        banner.setAttribute('aria-label', text.settingsTitle);
        banner.innerHTML = `
            <div class="cookie-consent-copy">
                <p>${text.text}</p>
                <a href="/cookies">${text.policy}</a>
            </div>
            <div class="cookie-consent-actions">
                <button type="button" class="cookie-consent-btn cookie-consent-settings-btn" data-cookie-settings>${text.settings}</button>
                <button type="button" class="cookie-consent-btn" data-cookie-essential>${text.essential}</button>
                <button type="button" class="cookie-consent-btn cookie-consent-primary" data-cookie-accept>${text.acceptAll}</button>
            </div>
            <div class="cookie-consent-settings" data-cookie-settings-panel hidden>
                <button type="button" class="cookie-consent-close" data-cookie-settings-close aria-label="${text.closeSettings}" title="${text.closeSettings}">
                    <i class="fa-solid fa-xmark" aria-hidden="true"></i>
                </button>
                <h2>${text.settingsTitle}</h2>
                <label class="cookie-consent-option">
                    <input type="checkbox" checked disabled>
                    <span><strong>${text.requiredTitle}</strong><small>${text.requiredText}</small></span>
                </label>
                <label class="cookie-consent-option">
                    <input type="checkbox" data-cookie-analytics>
                    <span><strong>${text.analyticsTitle}</strong><small>${text.analyticsText}</small></span>
                </label>
                <button type="button" class="cookie-consent-btn cookie-consent-primary" data-cookie-save>${text.save}</button>
            </div>
        `;
        document.body.append(banner);

        banner.querySelector('[data-cookie-essential]')?.addEventListener('click', acceptEssentialCookies);
        banner.querySelector('[data-cookie-accept]')?.addEventListener('click', () => savePreferences(true));
        banner.querySelector('[data-cookie-settings]')?.addEventListener('click', openCookieSettings);
        banner.querySelector('[data-cookie-settings-close]')?.addEventListener('click', closeCookieSettings);
        banner.querySelector('[data-cookie-save]')?.addEventListener('click', () => {
            savePreferences(banner.querySelector('[data-cookie-analytics]')?.checked);
        });
        return banner;
    }

    function openCookieSettings() {
        const banner = ensureBanner();
        const preferences = getPreferences();
        const panel = banner.querySelector('[data-cookie-settings-panel]');
        const analytics = banner.querySelector('[data-cookie-analytics]');
        if (analytics) analytics.checked = Boolean(preferences?.analytics);
        banner.removeAttribute('hidden');
        banner.setAttribute('role', 'dialog');
        banner.setAttribute('aria-modal', 'true');
        if (panel) {
            panel.hidden = false;
            banner.classList.add('cookie-consent-settings-open');
        }
    }

    function closeCookieSettings() {
        const banner = document.getElementById('cookieConsentBanner');
        const panel = banner?.querySelector('[data-cookie-settings-panel]');
        if (!banner || !panel) return;

        panel.hidden = true;
        banner.classList.remove('cookie-consent-settings-open');
        banner.setAttribute('role', 'region');
        banner.removeAttribute('aria-modal');
        if (getPreferences()) banner.setAttribute('hidden', '');
    }

    function initCookieConsent() {
        const preferences = getPreferences();
        window.cookieConsentPreferences = preferences;
        if (!preferences) ensureBanner();

        document.querySelectorAll('[data-cookie-settings-open]').forEach(button => {
            button.addEventListener('click', openCookieSettings);
        });

        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape') closeCookieSettings();
        });
    }

    window.openCookieSettings = openCookieSettings;
    window.getCookieConsentPreferences = getPreferences;
    window.acceptEssentialCookies = acceptEssentialCookies;
    document.addEventListener('DOMContentLoaded', initCookieConsent);
})();
