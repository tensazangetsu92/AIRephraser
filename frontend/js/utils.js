// frontend/js/utils.js

// Константа для максимального количества символов (по умолчанию для free)
const DEFAULT_MAX_CHARS = 1000;

// Глобальная переменная для текущего лимита
let currentMaxChars = DEFAULT_MAX_CHARS;

// Проверка лимита символов
function isWithinCharLimit(text) {
    return text.length <= currentMaxChars;
}

// Обновление лимита символов из подписки
function updateMaxCharsFromSubscription(subscription) {
    if (subscription && subscription.max_text_length) {
        currentMaxChars = subscription.max_text_length;
        console.log(`Max chars updated to: ${currentMaxChars}`);
    } else {
        currentMaxChars = DEFAULT_MAX_CHARS;
    }
    // Обновляем отображение счетчика
    if (typeof updateCharCounter === 'function') {
        updateCharCounter();
    }
}

// Обновление счетчика символов
function updateCharCounter() {
    const elements = window.elements || {};

    if (!elements.input || !elements.charCounter) return;

    const currentLength = elements.input.value.length;
    const maxLength = currentMaxChars;

    elements.charCounter.textContent = `Количество символов ${currentLength}/${maxLength}`;

    if (currentLength > maxLength) {
        elements.charCounter.style.color = '#ef4444';
        elements.charCounter.style.fontWeight = 'bold';
    } else if (currentLength > maxLength * 0.9) {
        elements.charCounter.style.color = '#f59e0b';
        elements.charCounter.style.fontWeight = 'normal';
    } else {
        elements.charCounter.style.color = '#f0f0f0';
        elements.charCounter.style.fontWeight = 'normal';
    }
}

// Получить текущий лимит символов
function getCurrentMaxChars() {
    return currentMaxChars;
}

// Делаем функции и переменные глобальными
window.DEFAULT_MAX_CHARS = DEFAULT_MAX_CHARS;
window.currentMaxChars = currentMaxChars;
window.isWithinCharLimit = isWithinCharLimit;
window.updateMaxCharsFromSubscription = updateMaxCharsFromSubscription;
window.updateCharCounter = updateCharCounter;
window.getCurrentMaxChars = getCurrentMaxChars;