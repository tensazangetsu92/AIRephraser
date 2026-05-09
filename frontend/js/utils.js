// frontend/js/utils.js

// Константа для максимального количества слов (по умолчанию для free)
const DEFAULT_MAX_WORDS = 200;

// Глобальная переменная для текущего лимита слов
let currentMaxWords = DEFAULT_MAX_WORDS;

// Функция подсчёта слов в тексте
function countWords(text) {
    if (!text || !text.trim()) return 0;
    return text.trim().split(/\s+/).length;
}

// Проверка лимита слов
function isWithinWordLimit(text) {
    const wordCount = countWords(text);
    return wordCount <= currentMaxWords;
}

// Обновление лимита слов из подписки
function updateMaxWordsFromSubscription(subscription) {
    if (subscription && subscription.max_words) {
        currentMaxWords = subscription.max_words;
        // console.log(`Max words updated to: ${currentMaxWords}`); // 👈 ЗАКОММЕНТИРОВАТЬ ИЛИ УДАЛИТЬ
    } else {
        currentMaxWords = DEFAULT_MAX_WORDS;
    }
    // Обновляем отображение счетчика
    if (typeof updateWordCounter === 'function') {
        updateWordCounter();
    }
}

// Обновление счетчика слов
function updateWordCounter() {
    const elements = window.elements || {};
    if (!elements.input || !elements.wordCounter) return;

    const text = elements.input.value;
    const currentWords = countWords(text);
    const maxWords = currentMaxWords;
    // Обновляем текст счетчика
    elements.wordCounter.textContent = `Количество слов ${currentWords}/${maxWords}`;

    // Меняем цвет
    if (currentWords > maxWords) {
        elements.wordCounter.style.color = '#ef4444';
        elements.wordCounter.style.fontWeight = 'bold';
    } else if (currentWords > maxWords * 0.9) {
        elements.wordCounter.style.color = '#f59e0b';
        elements.wordCounter.style.fontWeight = 'normal';
    } else {
        elements.wordCounter.style.color = '#f0f0f0';
        elements.wordCounter.style.fontWeight = 'normal';
    }
}

// Получить текущий лимит слов
function getCurrentMaxWords() {
    return currentMaxWords;
}

// Делаем функции и переменные глобальными
window.DEFAULT_MAX_WORDS = DEFAULT_MAX_WORDS;
window.currentMaxWords = currentMaxWords;
window.countWords = countWords;
window.isWithinWordLimit = isWithinWordLimit;
window.updateMaxWordsFromSubscription = updateMaxWordsFromSubscription;
window.updateWordCounter = updateWordCounter;
window.getCurrentMaxWords = getCurrentMaxWords;