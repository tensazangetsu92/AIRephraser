// frontend/js/humanize.js

let pendingText = null;

// Обработка текста (основная логика)
async function processText(text) {
    // Получаем элементы глобально
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

// Отправка текста на обработку
async function send() {
    console.log('=== SEND FUNCTION CALLED ===');

    // Получаем элементы глобально
    const elements = window.elements || {};

    if (!elements.input) {
        console.error('Elements not initialized!');
        return;
    }

    const text = elements.input.value;
    const textLength = text.length;

    // Проверка на пустой текст
    if (!text.trim()) {
        if (elements.result) elements.result.innerText = '⚠️ Пожалуйста, введите текст для обработки';
        return;
    }

    // Проверка лимита символов
    if (typeof window.isWithinCharLimit === 'function' && !window.isWithinCharLimit(text)) {
        const maxChars = window.MAX_CHARS || 1000;
        const errorMessage = `❌ Превышен лимит символов! Максимум ${maxChars} символов. Сейчас ${textLength}/${maxChars}.`;
        if (elements.result) elements.result.innerText = errorMessage;
        if (elements.charCounter) {
            elements.charCounter.style.color = '#ef4444';
            elements.charCounter.style.fontWeight = 'bold';
        }
        return;
    }

    // Проверка авторизации
    if (!Auth.isAuthenticated()) {
        pendingText = text;
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
        if (window.isWithinCharLimit && window.isWithinCharLimit(pendingText)) {
            const text = pendingText;
            pendingText = null;
            await processText(text);
        } else {
            const maxChars = window.MAX_CHARS || 1000;
            const textLength = pendingText.length;
            const errorMessage = `❌ Превышен лимит символов! Максимум ${maxChars} символов. Сейчас ${textLength}/${maxChars}.`;
            const elements = window.elements || {};
            if (elements.result) elements.result.innerText = errorMessage;
            pendingText = null;
        }
    }
}

// Делаем функции глобальными
window.processPendingText = processPendingText;
window.send = send;