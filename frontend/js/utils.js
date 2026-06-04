// frontend/js/utils.js

// Константы для лимитов слов
const DEFAULT_MAX_WORDS = 1000;
const DEFAULT_MIN_WORDS = 50;

// Глобальная переменная для текущего лимита слов
let currentMaxWords = DEFAULT_MAX_WORDS;
let currentMinWords = DEFAULT_MIN_WORDS;

// Функция подсчёта слов в тексте
function countWords(text) {
    if (!text || !text.trim()) return 0;
    return text.trim().split(/\s+/).length;
}

// Проверка лимита слов (максимум)
function isWithinWordLimit(text) {
    const wordCount = countWords(text);
    return wordCount <= currentMaxWords;
}

// Проверка минимального количества слов
function isAboveMinWords(text) {
    const wordCount = countWords(text);
    return wordCount >= currentMinWords;
}

// Обновление лимита слов из подписки
function updateMaxWordsFromSubscription(subscription) {
    if (subscription && subscription.max_words) {
        currentMaxWords = subscription.max_words;
    } else {
        currentMaxWords = DEFAULT_MAX_WORDS;
    }
    if (typeof updateWordCounter === 'function') {
        updateWordCounter();
    }
}

// Обновление счетчика слов
function updateWordCounter() {
    const elements = window.elements || {};
    if (!elements.input) return;

    const text = elements.input.value;
    const currentWords = countWords(text);
    const maxWords = currentMaxWords;
    const minWords = currentMinWords;

    // Обновляем только счетчик слов (слева)
    const wordCountSpan = document.getElementById('wordCount');
    if (wordCountSpan) {
        wordCountSpan.textContent = `${currentWords}/${maxWords}`;

        // Меняем цвет счетчика
        if (currentWords > maxWords) {
            wordCountSpan.style.color = '#ef4444';
            wordCountSpan.style.fontWeight = 'bold';
        } else if (currentWords < minWords) {
            wordCountSpan.style.fontWeight = 'bold';
        } else if (currentWords > maxWords * 0.9) {
            wordCountSpan.style.color = '#f59e0b';
            wordCountSpan.style.fontWeight = 'normal';
        } else {
            wordCountSpan.style.color = '#c4c4c4';
            wordCountSpan.style.fontWeight = 'normal';
        }
    }


}

// Получить текущие лимиты
function getCurrentMaxWords() {
    return currentMaxWords;
}

function getCurrentMinWords() {
    return currentMinWords;
}

// Делаем функции и переменные глобальными
window.DEFAULT_MAX_WORDS = DEFAULT_MAX_WORDS;
window.DEFAULT_MIN_WORDS = DEFAULT_MIN_WORDS;
window.currentMaxWords = currentMaxWords;
window.currentMinWords = currentMinWords;
window.countWords = countWords;
window.isWithinWordLimit = isWithinWordLimit;
window.isAboveMinWords = isAboveMinWords;
window.updateMaxWordsFromSubscription = updateMaxWordsFromSubscription;
window.updateWordCounter = updateWordCounter;
window.getCurrentMaxWords = getCurrentMaxWords;
window.getCurrentMinWords = getCurrentMinWords;