// frontend/js/utils.js

// Константа для максимального количества символов
const MAX_CHARS = 1000;

// Проверка лимита символов
function isWithinCharLimit(text) {
    return text.length <= MAX_CHARS;
}

// Обновление счетчика символов
function updateCharCounter(elements) {
    if (!elements.input || !elements.charCounter) return;

    const currentLength = elements.input.value.length;
    const subscription = window.currentSubscription || { max_text_length: 1000 };
    const maxLength = subscription.max_text_length || MAX_CHARS;

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

// Отображение лимитов пользователю
function updateLimitsDisplay(subscription, usage) {
    const charCounter = document.getElementById('charCounter');
    const input = document.getElementById('input');

    if (charCounter && input) {
        const maxLength = subscription.max_text_length || 1000;
        const currentLength = input.value.length || 0;
        charCounter.textContent = `Количество символов ${currentLength}/${maxLength}`;
        charCounter.style.color = currentLength > maxLength ? '#ef4444' : '#f0f0f0';
    }
}

// Делаем функции глобальными
window.MAX_CHARS = MAX_CHARS;
window.isWithinCharLimit = isWithinCharLimit;
window.updateCharCounter = updateCharCounter;
window.updateLimitsDisplay = updateLimitsDisplay;