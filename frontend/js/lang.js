// frontend/js/lang.js

// Словарь переводов
const translations = {
    ru: {
        // Navbar
        'logo': 'Humary',
        'login': 'Войти',
        'logout': 'Выйти',

        // Main content
        'title': 'Humary',
        'subtitle': 'Превращаем ИИ-текст в живые слова',

        // Editor
        'input_label': 'Ввод',
        'result_label': 'Результат',
        'input_placeholder': 'Вставьте текст для обработки...',
        'result_placeholder': 'Результат появится здесь...',
        'char_counter': 'Количество символов',

        // Controls
        'intensity_label': 'Сила изменения',
        'intensity_low': 'Слабая',
        'intensity_medium': 'Нормальная',
        'intensity_high': 'Сильная',

        'tone_label': 'Тон',
        'tone_neutral': 'Нейтральный',
        'tone_formal': 'Формальный',
        'tone_casual': 'Повседневный',
        'tone_friendly': 'Дружелюбный',
        'tone_academic': 'Академический',

        'style_label': 'Стиль',
        'style_simple': 'Простой',
        'style_creative': 'Креативный',
        'style_professional': 'Профессиональный',

        'length_label': 'Длина',
        'length_same': 'Оставить',
        'length_shorter': 'Короче',
        'length_longer': 'Длиннее',

        'humanize_btn': 'Очеловечить текст',
        'processing': 'Обработка...',

        // Tariffs section
        'tariffs_title': 'Выберите свой тариф',
        'tariffs_subtitle': 'Премиум доступ к расширенным возможностям',

        'per_month': '/месяц',
        'requests_total': 'запросов всего',
        'up_to': 'До',
        'up_to_daily': 'До',
        'chars_per_request': 'символов за раз',
        'basic_processing': 'Базовая обработка текста',
        'extended_processing': 'Расширенная обработка текста',
        'pro_processing': 'Профессиональная обработка текста',
        'requests_per_day': 'запросов в день',
        'priority_processing': 'Приоритетная обработка',
        'priority_support': 'Приоритетная поддержка 24/7',

        'badge_recommended': 'Рекомендуемый',
        'badge_maximum': 'Максимум',

        'plan_free': 'Бесплатно',
        'plan_basic': 'Basic',
        'plan_premium': 'Premium',
        'plan_pro': 'Pro',

        'plan_basic_desc': 'Базовый тариф для старта',
        'plan_premium_desc': 'Оптимальный выбор для профессионалов',
        'plan_pro_desc': 'Максимальные возможности',

        'select_plan': 'Выбрать тариф',
        'current_plan': 'Текущий план',
        'already_available': 'Уже доступен',

        // Auth modal
        'auth_login_title': '🔐 Вход',
        'auth_register_title': '📝 Регистрация',
        'auth_email_placeholder': 'Email',
        'auth_password_placeholder': 'Пароль',
        'auth_confirm_password_placeholder': 'Подтвердите пароль',
        'auth_login_btn': 'Войти',
        'auth_register_btn': 'Зарегистрироваться',
        'auth_google_btn': '🌐 Войти через Google',
        'auth_toggle_login': '🔐 Уже есть аккаунт? Войти',
        'auth_toggle_register': '📝 Нет аккаунта? Зарегистрироваться',

        // Messages
        'error_empty_text': '⚠️ Пожалуйста, введите текст для обработки',
        'error_char_limit': '❌ Превышен лимит символов! Максимум',
        'error_not_authorized': '🔐 Для использования сервиса необходимо войти в аккаунт',
        'error_session_expired': '❌ Сессия истекла. Пожалуйста, войдите заново.',
        'error_server': '❌ Ошибка соединения с сервером',
        'processing_text': '🔄 Обработка текста...',
        'chars': 'символов',

        // Copy button
        'copy_success': '✅ Текст скопирован в буфер обмена',
        'copy_error': '❌ Не удалось скопировать текст',
        'no_text_to_copy': 'Нет текста для копирования',

        // Subscription
        'premium_activated': '✅ Подписка Premium активирована!',
        'pro_activated': '✅ Подписка Pro активирована!',
        'upgrade_error': '❌ Ошибка:',
        'please_login': 'Пожалуйста, войдите в аккаунт, чтобы оформить подписку'
    },
    en: {
        // Navbar
        'logo': 'Humary',
        'login': 'Login',
        'logout': 'Logout',

        // Main content
        'title': 'Humary',
        'subtitle': 'Turn AI text into human words',

        // Editor
        'input_label': 'Input',
        'result_label': 'Result',
        'input_placeholder': 'Paste text to process...',
        'result_placeholder': 'Result will appear here...',
        'char_counter': 'Characters',

        // Controls
        'intensity_label': 'Intensity',
        'intensity_low': 'Low',
        'intensity_medium': 'Medium',
        'intensity_high': 'High',

        'tone_label': 'Tone',
        'tone_neutral': 'Neutral',
        'tone_formal': 'Formal',
        'tone_casual': 'Casual',
        'tone_friendly': 'Friendly',
        'tone_academic': 'Academic',

        'style_label': 'Style',
        'style_simple': 'Simple',
        'style_creative': 'Creative',
        'style_professional': 'Professional',

        'length_label': 'Length',
        'length_same': 'Same',
        'length_shorter': 'Shorter',
        'length_longer': 'Longer',

        'humanize_btn': 'Humanize text',
        'processing': 'Processing...',

        // Tariffs section
        'tariffs_title': 'Choose your plan',
        'tariffs_subtitle': 'Premium access to extended features',

        'per_month': '/month',
        'requests_total': 'requests total',
        'up_to': 'Up to',
        'up_to_daily': 'Up to',
        'chars_per_request': 'characters per request',
        'basic_processing': 'Basic text processing',
        'extended_processing': 'Extended text processing',
        'pro_processing': 'Professional text processing',
        'requests_per_day': 'requests per day',
        'priority_processing': 'Priority processing',
        'priority_support': 'Priority support 24/7',

        'badge_recommended': 'Recommended',
        'badge_maximum': 'Maximum',

        'plan_free': 'Free',
        'plan_basic': 'Basic',
        'plan_premium': 'Premium',
        'plan_pro': 'Pro',

        'plan_basic_desc': 'Basic plan to start',
        'plan_premium_desc': 'Optimal choice for professionals',
        'plan_pro_desc': 'Maximum capabilities',

        'select_plan': 'Select plan',
        'current_plan': 'Current plan',
        'already_available': 'Already available',

        // Auth modal
        'auth_login_title': '🔐 Login',
        'auth_register_title': '📝 Register',
        'auth_email_placeholder': 'Email',
        'auth_password_placeholder': 'Password',
        'auth_confirm_password_placeholder': 'Confirm password',
        'auth_login_btn': 'Login',
        'auth_register_btn': 'Register',
        'auth_google_btn': '🌐 Login with Google',
        'auth_toggle_login': '🔐 Already have an account? Login',
        'auth_toggle_register': '📝 No account? Register',

        // Messages
        'error_empty_text': '⚠️ Please enter text to process',
        'error_char_limit': '❌ Character limit exceeded! Maximum',
        'error_not_authorized': '🔐 Please log in to use this service',
        'error_session_expired': '❌ Session expired. Please login again.',
        'error_server': '❌ Server connection error',
        'processing_text': '🔄 Processing text...',
        'chars': 'chars',

        // Copy button
        'copy_success': '✅ Text copied to clipboard',
        'copy_error': '❌ Failed to copy text',
        'no_text_to_copy': 'No text to copy',

        // Subscription
        'premium_activated': '✅ Premium subscription activated!',
        'pro_activated': '✅ Pro subscription activated!',
        'upgrade_error': '❌ Error:',
        'please_login': 'Please login to subscribe'
    }
};

// Текущий язык
let currentLang = localStorage.getItem('language') || 'ru';

// Функция переключения языка
function switchLanguage() {
    currentLang = currentLang === 'ru' ? 'en' : 'ru';
    localStorage.setItem('language', currentLang);
    updateUILanguage();
    updateLanguageButton();
}

// Обновление кнопки языка
function updateLanguageButton() {
    const langText = document.querySelector('.lang-text');
    if (langText) {
        langText.textContent = currentLang === 'ru' ? 'English' : 'Русский';
    }
}

// Получить перевод
function t(key) {
    return translations[currentLang][key] || translations['ru'][key] || key;
}

// Обновление текстов в тарифах
function updateTariffsLanguage() {
    // Обновляем заголовки секции
    const tariffsTitle = document.querySelector('.tariffs-title');
    const tariffsSubtitle = document.querySelector('.tariffs-subtitle');
    if (tariffsTitle) tariffsTitle.textContent = t('tariffs_title');
    if (tariffsSubtitle) tariffsSubtitle.textContent = t('tariffs_subtitle');

    // Карточки тарифов
    const cards = document.querySelectorAll('.tariff-card');
    cards.forEach(card => {
        const plan = card.getAttribute('data-plan');

        // Бейдж
        const badge = card.querySelector('.tariff-badge');
        if (badge) {
            if (plan === 'free') badge.textContent = t('plan_free');
            else if (plan === 'premium') badge.textContent = t('badge_recommended');
            else if (plan === 'pro') badge.textContent = t('badge_maximum');
        }

        // Название
        const name = card.querySelector('.tariff-name');
        if (name) {
            if (plan === 'free') name.textContent = t('plan_basic');
            else if (plan === 'premium') name.textContent = t('plan_premium');
            else if (plan === 'pro') name.textContent = t('plan_pro');
        }

        // Период
        const period = card.querySelector('.period');
        if (period) period.textContent = t('per_month');

        // Описание
        const desc = card.querySelector('.tariff-description');
        if (desc) {
            if (plan === 'free') desc.textContent = t('plan_basic_desc');
            else if (plan === 'premium') desc.textContent = t('plan_premium_desc');
            else if (plan === 'pro') desc.textContent = t('plan_pro_desc');
        }

        // Кнопка
        const btn = card.querySelector('.tariff-btn');
        if (btn && !btn.disabled) {
            btn.textContent = t('select_plan');
        } else if (btn && btn.disabled && plan === 'free') {
            btn.textContent = t('current_plan');
        } else if (btn && btn.disabled) {
            btn.textContent = t('already_available');
        }

        // Обновляем пункты списка (li)
        const items = card.querySelectorAll('.tariff-features li');
        items.forEach(item => {
            const text = item.innerText;
            if (text.includes('запросов всего') || text.includes('requests total')) {
                const number = text.match(/\d+/);
                if (number) {
                    item.innerHTML = `✅ ${number[0]} ${t('requests_total')}`;
                }
            } else if (text.includes('символов за раз') || text.includes('characters per request')) {
                const number = text.match(/\d+/);
                if (number) {
                    item.innerHTML = `✅ ${t('up_to')} ${number[0]} ${t('chars_per_request')}`;
                }
            } else if (text.includes('запросов в день') || text.includes('requests per day')) {
                const number = text.match(/\d+/);
                if (number) {
                    item.innerHTML = `✅ ${t('up_to_daily')} ${number[0]} ${t('requests_per_day')}`;
                }
            } else if (text.includes('Базовая') || text.includes('Basic text')) {
                item.innerHTML = `✅ ${t('basic_processing')}`;
            } else if (text.includes('Расширенная') || text.includes('Extended text')) {
                item.innerHTML = `✅ ${t('extended_processing')}`;
            } else if (text.includes('Профессиональная') || text.includes('Professional text')) {
                item.innerHTML = `✅ ${t('pro_processing')}`;
            } else if (text.includes('Приоритетная обработка') || text.includes('Priority processing')) {
                item.innerHTML = `✅ ${t('priority_processing')}`;
            } else if (text.includes('Приоритетная поддержка') || text.includes('Priority support')) {
                item.innerHTML = `✅ ${t('priority_support')}`;
            }
        });
    });
}

// Обновление всего UI на выбранном языке
function updateUILanguage() {
    // Обновляем все элементы с data-i18n атрибутом
    document.querySelectorAll('[data-i18n]').forEach(element => {
        const key = element.getAttribute('data-i18n');

        if (element.tagName === 'INPUT' || element.tagName === 'TEXTAREA') {
            if (element.placeholder !== undefined) {
                element.placeholder = t(key);
            } else {
                element.value = t(key);
            }
        } else {
            element.textContent = t(key);
        }
    });

    // Обновляем select опции
    updateSelectOptions();

    // Обновляем тарифы (отдельно, чтобы правильно обработать числа)
    updateTariffsLanguage();

    // Обновляем кнопку входа/выхода
    const authBtn = document.getElementById('authBtn');
    if (authBtn && window.Auth && !Auth.isAuthenticated()) {
        authBtn.textContent = t('login');
    } else if (authBtn && window.Auth && Auth.isAuthenticated()) {
        authBtn.textContent = t('logout');
    }

    // Обновляем заголовок модального окна
    const authTitle = document.getElementById('authTitle');
    if (authTitle && window.Auth && Auth.isRegisterMode) {
        authTitle.textContent = t('auth_register_title');
    } else if (authTitle) {
        authTitle.textContent = t('auth_login_title');
    }

    // Обновляем кнопку в модальном окне
    const authSubmitBtn = document.getElementById('authSubmitBtn');
    if (authSubmitBtn && window.Auth && Auth.isRegisterMode) {
        authSubmitBtn.textContent = t('auth_register_btn');
    } else if (authSubmitBtn) {
        authSubmitBtn.textContent = t('auth_login_btn');
    }

    // Обновляем ссылку переключения режима
    const toggleLink = document.getElementById('toggleAuthMode');
    if (toggleLink && window.Auth && Auth.isRegisterMode) {
        toggleLink.innerHTML = t('auth_toggle_login');
    } else if (toggleLink) {
        toggleLink.innerHTML = t('auth_toggle_register');
    }

    // Обновляем счетчик символов
    if (typeof updateCharCounter === 'function') {
        updateCharCounter();
    }
}

// Обновление опций select
function updateSelectOptions() {
    const intensityMap = {
        'low': t('intensity_low'),
        'medium': t('intensity_medium'),
        'high': t('intensity_high')
    };

    const toneMap = {
        'neutral': t('tone_neutral'),
        'formal': t('tone_formal'),
        'casual': t('tone_casual'),
        'friendly': t('tone_friendly'),
        'academic': t('tone_academic')
    };

    const styleMap = {
        'simple': t('style_simple'),
        'creative': t('style_creative'),
        'professional': t('style_professional')
    };

    const lengthMap = {
        'same': t('length_same'),
        'shorter': t('length_shorter'),
        'longer': t('length_longer')
    };

    // Обновляем intensity select
    const intensitySelect = document.getElementById('intensity');
    if (intensitySelect) {
        Array.from(intensitySelect.options).forEach(option => {
            if (intensityMap[option.value]) {
                option.textContent = intensityMap[option.value];
            }
        });
    }

    // Обновляем tone select
    const toneSelect = document.getElementById('tone');
    if (toneSelect) {
        Array.from(toneSelect.options).forEach(option => {
            if (toneMap[option.value]) {
                option.textContent = toneMap[option.value];
            }
        });
    }

    // Обновляем style select
    const styleSelect = document.getElementById('style');
    if (styleSelect) {
        Array.from(styleSelect.options).forEach(option => {
            if (styleMap[option.value]) {
                option.textContent = styleMap[option.value];
            }
        });
    }

    // Обновляем length select
    const lengthSelect = document.getElementById('length');
    if (lengthSelect) {
        Array.from(lengthSelect.options).forEach(option => {
            if (lengthMap[option.value]) {
                option.textContent = lengthMap[option.value];
            }
        });
    }
}

// Инициализация
function initLanguage() {
    updateLanguageButton();

    const langBtn = document.getElementById('langToggle');
    if (langBtn) {
        langBtn.addEventListener('click', switchLanguage);
    }

    // Применяем текущий язык
    updateUILanguage();
}

// Делаем функции глобальными
window.t = t;
window.currentLang = currentLang;
window.switchLanguage = switchLanguage;
window.initLanguage = initLanguage;