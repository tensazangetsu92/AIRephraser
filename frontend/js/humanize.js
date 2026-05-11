// frontend/js/humanize.js

let pendingText = null;

// Обработка текста (основная логика)
async function processText(text) {
    const elements = window.elements || {};

    const requestData = {
        text: text,
        intensity: elements.intensity?.value || 'medium',
        tone: elements.tone?.value || 'neutral',
        style: elements.style?.value || 'simple',
        length: elements.length?.value || 'same'
    };

    if (elements.humanizeBtn) {
        elements.humanizeBtn.disabled = true;
        elements.humanizeBtn.innerHTML = '<span class="loading"></span> Обработка...';
    }
    if (elements.result) elements.result.innerText = '🔄 Обработка текста...';

    const token = Auth.getToken();

    try {
        const response = await fetch('/humanize', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify(requestData)
        });

        const data = await response.json();

        if (response.ok) {
            if (elements.result) elements.result.innerText = data.result;
            // Очищаем предупреждение при успехе
            clearWarning();
        } else if (response.status === 401) {
            if (elements.result) elements.result.innerText = '❌ Сессия истекла. Пожалуйста, войдите заново.';
            Auth.logout();
            if (typeof window.updateUI === 'function') window.updateUI();
            setTimeout(() => Auth.showAuthModal(), 1500);
        } else if (response.status === 429) {
            if (elements.result) elements.result.innerText = '❌ ' + (data.detail || 'Лимит запросов исчерпан');
        } else {
            if (elements.result) elements.result.innerText = '❌ Ошибка: ' + (data.detail || 'Неизвестная ошибка');
        }
    } catch (err) {
        console.error('Humanize error:', err);
        if (elements.result) elements.result.innerText = '❌ Ошибка соединения с сервером';
    }

    if (elements.humanizeBtn) {
        elements.humanizeBtn.disabled = false;
        elements.humanizeBtn.innerHTML = 'Очеловечить текст';
    }
}

// Функция для отображения предупреждения
function showWarning(message, isError = false) {
    const warningSpan = document.getElementById('wordWarning');
    if (warningSpan) {
        warningSpan.textContent = message;
        warningSpan.style.color = isError ? '#ef4444' : '#f59e0b';
    }
}

// Функция для очистки предупреждения
function clearWarning() {
    const warningSpan = document.getElementById('wordWarning');
    if (warningSpan) {
        warningSpan.textContent = '';
    }
}

// Отправка текста на обработку
async function send() {
    console.log('=== SEND FUNCTION CALLED ===');

    const elements = window.elements || {};

    if (!elements.input) {
        console.error('Elements not initialized!');
        return;
    }

    const text = elements.input.value;
    const wordCount = window.countWords ? window.countWords(text) : 0;
    const maxWords = window.currentMaxWords || 1000;
    const minWords = window.currentMinWords || 50;

    // Очищаем предыдущее предупреждение
    clearWarning();

    // Проверка на пустой текст
    if (!text.trim()) {
        showWarning('⚠️ Пожалуйста, введите текст для обработки', false);
        if (elements.result) elements.result.innerText = '⚠️ Пожалуйста, введите текст для обработки';
        return;
    }

    // ========== ПРОВЕРКА МИНИМУМА СЛОВ ==========
    if (wordCount < minWords) {
        const errorMessage = `❌ Минимальное количество слов: ${minWords}.`;
        showWarning(errorMessage, true);
        return;
    }
    // ===========================================

    // Проверка лимита слов (максимум)
    if (!window.isWithinWordLimit(text)) {
        const errorMessage = `❌ Максимальное количество слов: ${maxWords}.`;
        showWarning(errorMessage, true);
        return;
    }

    // Проверка авторизации
    if (!Auth.isAuthenticated()) {
        pendingText = text;
        showWarning('🔐 Для использования сервиса необходимо войти в аккаунт', false);
        if (elements.result) elements.result.innerText = '🔐 Для использования сервиса необходимо войти в аккаунт';
        Auth.showAuthModal();
        return;
    }

    await processText(text);
}

// Обработка отложенного текста (после входа)
async function processPendingText() {
    console.log('processPendingText called, pendingText:', pendingText);

    if (pendingText && Auth.isAuthenticated()) {
        if (window.isWithinWordLimit && window.isWithinWordLimit(pendingText)) {
            const text = pendingText;
            pendingText = null;
            await processText(text);
        } else {
            const maxWords = window.currentMaxWords || 1000;
            const wordCount = window.countWords ? window.countWords(pendingText) : 0;
            const errorMessage = `❌ Максимальное количество слов: ${maxWords}. Сейчас ${wordCount} слов.`;
            const elements = window.elements || {};
            if (elements.result) elements.result.innerText = errorMessage;
            showWarning(errorMessage, true);
            pendingText = null;
        }
    }
}

// Делаем функции глобальными
window.processPendingText = processPendingText;
window.send = send;
window.showWarning = showWarning;
window.clearWarning = clearWarning;