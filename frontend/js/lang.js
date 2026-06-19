const translations = {
    ru: {
        logo: 'Humary',
        login: 'Войти',
        logout: 'Выйти',
        title: 'Humary',
        subtitle: 'Превращаем ИИ-текст в живые слова',
        input_label: 'Ввод',
        result_label: 'Результат',
        input_placeholder: 'Вставьте текст для обработки...',
        result_placeholder: 'Результат появится здесь...',
        intensity_label: 'Сила изменения',
        intensity_low: 'Слабая',
        intensity_medium: 'Нормальная',
        intensity_high: 'Сильная',
        tone_label: 'Тон',
        tone_neutral: 'Нейтральный',
        tone_formal: 'Формальный',
        tone_casual: 'Повседневный',
        tone_friendly: 'Дружелюбный',
        tone_academic: 'Академический',
        style_label: 'Стиль',
        style_simple: 'Простой',
        style_creative: 'Креативный',
        style_professional: 'Профессиональный',
        length_label: 'Длина',
        length_same: 'Оставить',
        length_shorter: 'Короче',
        length_longer: 'Длиннее',
        humanize_btn: 'Очеловечить текст',
        tariffs_title: 'Выберите свой тариф',
        tariffs_subtitle: 'Премиум доступ к расширенным возможностям',
        per_month: '/месяц',
        requests_total: 'запросов всего',
        up_to: 'До',
        chars_per_request: 'символов за раз',
        basic_processing: 'Базовая обработка текста',
        extended_processing: 'Расширенная обработка текста',
        pro_processing: 'Профессиональная обработка текста',
        requests_per_day: 'запросов в день',
        priority_processing: 'Приоритетная обработка',
        priority_support: 'Приоритетная поддержка 24/7',
        badge_recommended: 'Рекомендуемый',
        badge_maximum: 'Максимум',
        plan_free: 'Бесплатно',
        plan_basic: 'Basic',
        plan_premium: 'Premium',
        plan_pro: 'Pro',
        plan_basic_desc: 'Базовый тариф для старта',
        plan_premium_desc: 'Оптимальный выбор для профессионалов',
        plan_pro_desc: 'Максимальные возможности',
        select_plan: 'Выбрать тариф',
        current_plan: 'Текущий план',
        already_available: 'Уже доступен',
        auth_login_title: 'Вход',
        auth_register_title: 'Регистрация',
        auth_login_btn: 'Войти',
        auth_register_btn: 'Зарегистрироваться',
        auth_toggle_login: 'Уже есть аккаунт? Войти',
        auth_toggle_register: 'Нет аккаунта? Зарегистрироваться',
    },
    en: {
        logo: 'Humary',
        login: 'Login',
        logout: 'Logout',
        title: 'Humary',
        subtitle: 'Turn AI text into human words',
        input_label: 'Input',
        result_label: 'Result',
        input_placeholder: 'Paste text to process...',
        result_placeholder: 'Result will appear here...',
        intensity_label: 'Intensity',
        intensity_low: 'Low',
        intensity_medium: 'Medium',
        intensity_high: 'High',
        tone_label: 'Tone',
        tone_neutral: 'Neutral',
        tone_formal: 'Formal',
        tone_casual: 'Casual',
        tone_friendly: 'Friendly',
        tone_academic: 'Academic',
        style_label: 'Style',
        style_simple: 'Simple',
        style_creative: 'Creative',
        style_professional: 'Professional',
        length_label: 'Length',
        length_same: 'Same',
        length_shorter: 'Shorter',
        length_longer: 'Longer',
        humanize_btn: 'Humanize text',
        tariffs_title: 'Choose your plan',
        tariffs_subtitle: 'Premium access to extended features',
        per_month: '/month',
        requests_total: 'requests total',
        up_to: 'Up to',
        chars_per_request: 'characters per request',
        basic_processing: 'Basic text processing',
        extended_processing: 'Extended text processing',
        pro_processing: 'Professional text processing',
        requests_per_day: 'requests per day',
        priority_processing: 'Priority processing',
        priority_support: 'Priority support 24/7',
        badge_recommended: 'Recommended',
        badge_maximum: 'Maximum',
        plan_free: 'Free',
        plan_basic: 'Basic',
        plan_premium: 'Premium',
        plan_pro: 'Pro',
        plan_basic_desc: 'Basic plan to start',
        plan_premium_desc: 'Optimal choice for professionals',
        plan_pro_desc: 'Maximum capabilities',
        select_plan: 'Select plan',
        current_plan: 'Current plan',
        already_available: 'Already available',
        auth_login_title: 'Login',
        auth_register_title: 'Register',
        auth_login_btn: 'Login',
        auth_register_btn: 'Register',
        auth_toggle_login: 'Already have an account? Login',
        auth_toggle_register: 'No account? Register',
    }
};

let currentLang = localStorage.getItem('language') || 'ru';

function t(key) {
    return translations[currentLang]?.[key] ?? translations.ru[key] ?? key;
}

function toggleLang() {
    currentLang = currentLang === 'ru' ? 'en' : 'ru';
    localStorage.setItem('language', currentLang);
    window.currentLang = currentLang;
    updateUILanguage();
    updateLanguageButton();
}

function updateLanguageButton() {
    const el = document.querySelector('.lang-text');
    if (el) el.textContent = currentLang === 'ru' ? 'Русский' : 'English';
}

function updateCustomSelect(hiddenInputId, map) {
    const select = document.querySelector(`#${hiddenInputId}`)?.previousElementSibling;
    if (!select?.classList.contains('custom-select')) return;
    select.querySelectorAll('.custom-select-option').forEach(option => {
        const translated = map[option.dataset.value];
        if (!translated) return;
        option.textContent = translated;
        if (option.classList.contains('selected')) {
            const label = select.querySelector('.custom-select-label');
            if (label) label.textContent = translated;
        }
    });
}

function updateSelectOptions() {
    updateCustomSelect('intensity', {
        low: t('intensity_low'), medium: t('intensity_medium'), high: t('intensity_high')
    });
    updateCustomSelect('tone', {
        neutral: t('tone_neutral'), formal: t('tone_formal'), casual: t('tone_casual'),
        friendly: t('tone_friendly'), academic: t('tone_academic')
    });
    updateCustomSelect('style', {
        simple: t('style_simple'), creative: t('style_creative'), professional: t('style_professional')
    });
    updateCustomSelect('length', {
        same: t('length_same'), shorter: t('length_shorter'), longer: t('length_longer')
    });
}

function updateTariffsLanguage() {
    document.querySelector('.tariffs-title') && (document.querySelector('.tariffs-title').textContent = t('tariffs_title'));
    document.querySelector('.tariffs-subtitle') && (document.querySelector('.tariffs-subtitle').textContent = t('tariffs_subtitle'));

    document.querySelectorAll('.tariff-card').forEach(card => {
        const plan = card.getAttribute('data-plan');

        const badge = card.querySelector('.tariff-badge');
        if (badge) badge.textContent = plan === 'free' ? t('plan_free') : plan === 'premium' ? t('badge_recommended') : t('badge_maximum');

        const name = card.querySelector('.tariff-name');
        if (name) name.textContent = t(`plan_${plan}`);

        const period = card.querySelector('.period');
        if (period) period.textContent = t('per_month');

        const desc = card.querySelector('.tariff-description');
        if (desc) desc.textContent = t(`plan_${plan}_desc`);

        const btn = card.querySelector('.tariff-btn');
        if (btn) {
            if (!btn.disabled) btn.textContent = t('select_plan');
            else btn.textContent = plan === 'free' ? t('current_plan') : t('already_available');
        }

        card.querySelectorAll('.tariff-features li').forEach(item => {
            const icon = item.querySelector('i')?.outerHTML || '';
            const text = item.innerText;
            const num = text.match(/\d+/)?.[0];

            if (text.match(/запросов всего|requests total/)) item.innerHTML = `${icon} ${num} ${t('requests_total')}`;
            else if (text.match(/символов за раз|символов|characters per request/)) item.innerHTML = `${icon} ${t('up_to')} ${num} ${t('chars_per_request')}`;
            else if (text.match(/запросов в день|requests per day/)) item.innerHTML = `${icon} ${t('up_to')} ${num} ${t('requests_per_day')}`;
            else if (text.match(/Базовая|Basic/)) item.innerHTML = `${icon} ${t('basic_processing')}`;
            else if (text.match(/Расширенная|Extended/)) item.innerHTML = `${icon} ${t('extended_processing')}`;
            else if (text.match(/Профессиональная|Professional/)) item.innerHTML = `${icon} ${t('pro_processing')}`;
            else if (text.match(/Приоритетная обработка|Priority processing/)) item.innerHTML = `${icon} ${t('priority_processing')}`;
            else if (text.match(/Поддержка|Priority support|support/i)) item.innerHTML = `${icon} ${t('priority_support')}`;
        });
    });
}

function updateUILanguage() {
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
            el.placeholder = t(key);
        } else {
            el.textContent = t(key);
        }
    });

    updateSelectOptions();
    updateTariffsLanguage();

    const authBtn = document.getElementById('authBtn');
    if (authBtn && typeof Auth !== 'undefined') {
        authBtn.textContent = Auth.isAuthenticated() ? t('logout') : t('login');
    }

    const authTitle = document.getElementById('authTitle');
    if (authTitle && typeof Auth !== 'undefined') {
        authTitle.textContent = Auth.isRegisterMode ? t('auth_register_title') : t('auth_login_title');
    }

    const authSubmitBtn = document.getElementById('authSubmitBtn');
    if (authSubmitBtn && typeof Auth !== 'undefined') {
        authSubmitBtn.textContent = Auth.isRegisterMode ? t('auth_register_btn') : t('auth_login_btn');
    }

    const toggleLink = document.getElementById('toggleAuthMode');
    if (toggleLink && typeof Auth !== 'undefined') {
        toggleLink.innerHTML = Auth.isRegisterMode ? t('auth_toggle_login') : t('auth_toggle_register');
    }
}

function initLanguage() {
    updateLanguageButton();
    updateUILanguage();
}

window.t = t;
window.currentLang = currentLang;
window.toggleLang = toggleLang;
window.switchLanguage = toggleLang;
window.initLanguage = initLanguage;