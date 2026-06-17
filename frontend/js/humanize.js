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

function loadTextFromLocalStorage() {
    const elements = window.elements || {};
    const savedInput = localStorage.getItem('saved_input_text');
    const savedResult = localStorage.getItem('saved_result_text');

    if (elements.input) {
        elements.input.value = savedInput || '';
        if (typeof window.updateWordCounter === 'function') {
            window.updateWordCounter();
        }
    }

    // Если поле ввода пустое — сбрасываем результат и скрываем колонку
    if (!savedInput || !savedInput.trim()) {
        localStorage.removeItem('saved_result_text');
        if (elements.result) elements.result.value = '';
        hideResultColumn();
        return;
    }

    if (elements.result && savedResult) {
        elements.result.value = savedResult;
        showResultColumn();
    } else {
        hideResultColumn();
    }
}

let copyInputTimer = null;

async function copyInputText() {
    const elements = window.elements || {};
    const inputTextarea = elements.input;

    if (!inputTextarea) return;

    const text = inputTextarea.value;

    if (!text || !text.trim()) {
        showNotification('Нет текста для копирования', 'warning');
        return;
    }

    try {
        await navigator.clipboard.writeText(text);

        const copyBtn = document.getElementById('copyInputBtn');
        if (copyBtn) {
            // Отменяем предыдущий таймер
            if (copyInputTimer) clearTimeout(copyInputTimer);

            // Сохраняем исходное содержимое (только если иконка не галочка)
            if (!copyBtn.hasAttribute('data-original-html')) {
                copyBtn.setAttribute('data-original-html', copyBtn.innerHTML);
            }
            const originalHtml = copyBtn.getAttribute('data-original-html');

            // Меняем на галочку
            copyBtn.innerHTML = '<i class="fas fa-check"></i>';

            // Возвращаем через 1.5 секунды
            copyInputTimer = setTimeout(() => {
                copyBtn.innerHTML = originalHtml;
                copyInputTimer = null;
            }, 1500);
        }

        showNotification('Текст из поля ввода скопирован', 'success');
    } catch (err) {
        console.error('Copy failed:', err);
        showNotification('Не удалось скопировать текст', 'error');
    }
}

// Копирование текста из поля результата
let copyResultTimer = null;

async function copyResultText() {
    const elements = window.elements || {};
    const resultTextarea = elements.result;

    if (!resultTextarea) return;

    const text = resultTextarea.value;

    if (!text || text === 'Результат появится здесь...' || text.includes('⚠️') || text.includes('❌') || text.includes('🔄')) {
        showNotification('Нет текста для копирования', 'warning');
        return;
    }

    try {
        await navigator.clipboard.writeText(text);

        const copyBtn = document.getElementById('copyResultBtn');
        if (copyBtn) {
            // Отменяем предыдущий таймер
            if (copyResultTimer) clearTimeout(copyResultTimer);

            // Сохраняем исходное содержимое (только если иконка не галочка)
            if (!copyBtn.hasAttribute('data-original-html')) {
                copyBtn.setAttribute('data-original-html', copyBtn.innerHTML);
            }
            const originalHtml = copyBtn.getAttribute('data-original-html');

            // Меняем на галочку
            copyBtn.innerHTML = '<i class="fas fa-check"></i>';

            // Возвращаем через 1.5 секунды
            copyResultTimer = setTimeout(() => {
                copyBtn.innerHTML = originalHtml;
                copyResultTimer = null;
            }, 1500);
        }

        showNotification('Текст из поля результата скопирован', 'success');
    } catch (err) {
        console.error('Copy failed:', err);
        showNotification('Не удалось скопировать текст', 'error');
    }
}

function showResultColumn() {
    const resultCol = document.getElementById('resultCol');
    const editor = document.getElementById('editorContainer');
    if (resultCol) resultCol.style.display = '';
    if (editor) editor.classList.remove('single-col');
}

function hideResultColumn() {
    const resultCol = document.getElementById('resultCol');
    const editor = document.getElementById('editorContainer');
    if (resultCol) resultCol.style.display = 'none';
    if (editor) editor.classList.add('single-col');
}

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
    if (elements.result) {
        elements.result.value = 'Обработка текста...';
        showNotification('Обработка текста');
    }

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
            localStorage.setItem('saved_result_text', data.result);
            clearWarning();
            showResultColumn();
            // 👇 СОХРАНЯЕМ В ИСТОРИЮ
            await saveToHistory(text, data.result, 'humanizer');

            // Обновляем баланс
            if (typeof updateBalanceDisplay === 'function') {
                updateBalanceDisplay();
            }
            if (typeof loadCurrentSubscription === 'function') {
                loadCurrentSubscription();
            }

        } else if (response.status === 401) {
            if (elements.result) elements.result.value = '❌ Сессия истекла. Пожалуйста, войдите заново.';
            Auth.logout();
            if (typeof window.updateUI === 'function') window.updateUI();
            setTimeout(() => Auth.showAuthModal(), 1500);
        } else if (response.status === 429) {
            if (elements.result) elements.result.value = '❌ ' + (data.detail || 'Лимит токенов исчерпан');
            if (typeof updateBalanceDisplay === 'function') {
                updateBalanceDisplay();
            }
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

async function saveToHistory(originalText, resultText, toolType = 'humanizer') {
    const token = Auth.getToken();
    if (!token) return;

    try {
        const response = await fetch('/user/history/save', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                tool_type: toolType,
                original_text: originalText,
                result_text: resultText
            })
        });

        if (!response.ok) {
            console.error('Failed to save to history:', await response.text());
        }
    } catch (err) {
        console.error('Error saving to history:', err);
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
        const errorMessage = `Минимальное количество слов: ${minWords}`;
        showWarning(errorMessage, true);
        const wordCountSpan = document.getElementById('wordCount');
        if (wordCountSpan) {
            wordCountSpan.style.color = '#ef4444';
            wordCountSpan.style.fontWeight = 'bold';
        }
        return;
    }

    if (!window.isWithinWordLimit(text)) {
        const errorMessage = `Максимальное количество слов: ${maxWords}`;
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
            localStorage.setItem('saved_input_text', text);
            if (pasteBtn) pasteBtn.style.display = 'none';
        } else {
            showNotification('Буфер обмена пуст');
        }
    } catch (err) {
        console.error('Failed to read clipboard:', err);
        showNotification('Не удалось получить доступ к буферу обмена. Разрешите доступ в настройках браузера.');
    }
}

function initAutoSave() {
    const elements = window.elements || {};

    if (elements.input) {
        elements.input.addEventListener('input', () => {
            localStorage.setItem('saved_input_text', elements.input.value);
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
window.copyInputText = copyInputText;
window.copyResultText = copyResultText;

// Инициализация кнопок и загрузка сохранённого текста
document.addEventListener('DOMContentLoaded', () => {
    const pasteBtn = document.getElementById('pasteBtn');
    if (pasteBtn) {
        pasteBtn.addEventListener('click', pasteFromClipboard);
    }

    const copyInputBtn = document.getElementById('copyInputBtn');
    if (copyInputBtn) {
        copyInputBtn.addEventListener('click', copyInputText);
    }

    const copyResultBtn = document.getElementById('copyResultBtn');
    if (copyResultBtn) {
        copyResultBtn.addEventListener('click', copyResultText);
    }

    loadTextFromLocalStorage();
    initAutoSave();
});