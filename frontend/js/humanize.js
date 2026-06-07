// frontend/js/humanize.js

let pendingText = null;

// Сохранение текста в localStorage
function saveTextToLocalStorage() {
    const elements = window.elements || {};
    if (elements.input) {
        localStorage.setItem('saved_input_text', elements.input.value);
    }
    if (elements.result) {
        localStorage.setItem('saved_result_text', elements.result.value);
    }
}

// Загрузка сохранённого текста из localStorage
function loadTextFromLocalStorage() {
    const elements = window.elements || {};
    const savedInput = localStorage.getItem('saved_input_text');
    const savedResult = localStorage.getItem('saved_result_text');

    if (elements.input && savedInput) {
        elements.input.value = savedInput;
        // Обновляем счетчик слов
        if (typeof window.updateWordCounter === 'function') {
            window.updateWordCounter();
        }
    }

    if (elements.result && savedResult) {
        elements.result.value = savedResult;
    }
}

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
    if (elements.result) elements.result.value = '🔄 Обработка текста...';

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
            if (elements.result) elements.result.value = data.result;
            // Сохраняем результат в localStorage
            localStorage.setItem('saved_result_text', data.result);
            clearWarning();
        } else if (response.status === 401) {
            if (elements.result) elements.result.value = '❌ Сессия истекла. Пожалуйста, войдите заново.';
            Auth.logout();
            if (typeof window.updateUI === 'function') window.updateUI();
            setTimeout(() => Auth.showAuthModal(), 1500);
        } else if (response.status === 429) {
            if (elements.result) elements.result.value = '❌ ' + (data.detail || 'Лимит запросов исчерпан');
        } else {
            if (elements.result) elements.result.value = '❌ Ошибка: ' + (data.detail || 'Неизвестная ошибка');
        }
    } catch (err) {
        console.error('Humanize error:', err);
        if (elements.result) elements.result.value = '❌ Ошибка соединения с сервером';
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

    clearWarning();

    if (!text.trim()) {
        showWarning('⚠️ Пожалуйста, введите текст для обработки', false);
        if (elements.result) elements.result.value = '⚠️ Пожалуйста, введите текст для обработки';
        return;
    }

    if (wordCount < minWords) {
        const errorMessage = `❌ Минимальное количество слов: ${minWords}.`;
        showWarning(errorMessage, true);
        const wordCountSpan = document.getElementById('wordCount');
        if (wordCountSpan) {
            wordCountSpan.style.color = '#ef4444';
            wordCountSpan.style.fontWeight = 'bold';
        }
        return;
    }

    if (!window.isWithinWordLimit(text)) {
        const errorMessage = `❌ Максимальное количество слов: ${maxWords}.`;
        showWarning(errorMessage, true);
        return;
    }

    if (!Auth.isAuthenticated()) {
        pendingText = text;
        showWarning('🔐 Для использования сервиса необходимо войти в аккаунт', false);
        if (elements.result) elements.result.value = '🔐 Для использования сервиса необходимо войти в аккаунт';
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
            if (elements.result) elements.result.value = errorMessage;
            showWarning(errorMessage, true);
            pendingText = null;
        }
    }
}

// Вставка текста из буфера обмена
async function pasteFromClipboard() {
    const textarea = document.getElementById('input');
    const pasteBtn = document.getElementById('pasteBtn');

    try {
        const text = await navigator.clipboard.readText();
        if (text) {
            textarea.value = text;
            textarea.dispatchEvent(new Event('input', { bubbles: true }));
            // Сохраняем в localStorage
            localStorage.setItem('saved_input_text', text);
            if (pasteBtn) pasteBtn.style.display = 'none';
        } else {
            alert('Буфер обмена пуст');
        }
    } catch (err) {
        console.error('Failed to read clipboard:', err);
        alert('Не удалось получить доступ к буферу обмена. Разрешите доступ в настройках браузера.');
    }
}

// Сохраняем текст при вводе
function initAutoSave() {
    const elements = window.elements || {};

    if (elements.input) {
        elements.input.addEventListener('input', () => {
            localStorage.setItem('saved_input_text', elements.input.value);
        });
    }

    if (elements.result) {
        elements.result.addEventListener('input', () => {
            localStorage.setItem('saved_result_text', elements.result.value);
        });
    }
}

// Делаем функции глобальными
window.processPendingText = processPendingText;
window.send = send;
window.showWarning = showWarning;
window.clearWarning = clearWarning;
window.pasteFromClipboard = pasteFromClipboard;
window.loadTextFromLocalStorage = loadTextFromLocalStorage;
window.initAutoSave = initAutoSave;

// Инициализация кнопки и загрузка сохранённого текста
document.addEventListener('DOMContentLoaded', () => {
    const pasteBtn = document.getElementById('pasteBtn');
    if (pasteBtn) {
        pasteBtn.addEventListener('click', pasteFromClipboard);
    }

    // Загружаем сохранённый текст
    loadTextFromLocalStorage();

    // Включаем автосохранение
    initAutoSave();
});