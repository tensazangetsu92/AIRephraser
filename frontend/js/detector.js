// frontend/js/detector.js

let pendingDetectText = null;

function loadDetectorTextFromLocalStorage() {
    const elements = window.elements || {};
    const savedInput = localStorage.getItem('detector_input_text');

    if (elements.input) {
        elements.input.value = savedInput || '';
        if (typeof window.updateWordCounter === 'function') {
            window.updateWordCounter();
        }
    }

    const savedResult = localStorage.getItem('detector_result_data');
    if (!savedInput || !savedInput.trim()) {
        localStorage.removeItem('detector_result_data');
        hideResultColumn();
        return;
    }

    if (savedResult) {
        try {
            const data = JSON.parse(savedResult);
            renderDetectorResult(data);
            showResultColumn();
        } catch {
            hideResultColumn();
        }
    } else {
        hideResultColumn();
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

function renderDetectorResult(data) {
    const elements = window.elements || {};
    if (!elements.result) return;

    const aiPct = data.ai_probability;
    const humanPct = data.human_probability;

    const text = `Вероятность ИИ: ${aiPct}%\nВероятность человека: ${humanPct}%\n\n${data.verdict}\n\n${data.explanation}`;
    elements.result.value = text;
}

async function processDetectText(text) {
    const elements = window.elements || {};

    if (elements.detectBtn) {
        elements.detectBtn.disabled = true;
        elements.detectBtn.innerHTML = '<span class="loading"></span> Анализ...';
    }
    if (elements.result) {
        elements.result.value = 'Анализ текста...';
    }
    showResultColumn();
    showNotification('Анализ текста');

    const token = Auth.getToken();

    try {
        const response = await fetch('/detect', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ text })
        });

        const data = await response.json();

        if (response.ok) {
            renderDetectorResult(data.result);
            localStorage.setItem('detector_result_data', JSON.stringify(data.result));
            clearWarning();

            if (typeof updateBalanceDisplay === 'function') updateBalanceDisplay();
            if (typeof loadCurrentSubscription === 'function') loadCurrentSubscription();

        } else if (response.status === 401) {
            if (elements.result) elements.result.value = '❌ Сессия истекла. Пожалуйста, войдите заново.';
            Auth.logout();
            if (typeof window.updateUI === 'function') window.updateUI();
            setTimeout(() => Auth.showAuthModal(), 1500);
        } else if (response.status === 429) {
            if (elements.result) elements.result.value = '❌ ' + (data.detail || 'Лимит токенов исчерпан');
            if (typeof updateBalanceDisplay === 'function') updateBalanceDisplay();
        } else {
            if (elements.result) elements.result.value = '❌ Ошибка: ' + (data.detail || 'Неизвестная ошибка');
        }
    } catch (err) {
        console.error('Detect error:', err);
        if (elements.result) elements.result.value = '❌ Ошибка соединения с сервером';
    }

    if (elements.detectBtn) {
        elements.detectBtn.disabled = false;
        elements.detectBtn.innerHTML = 'Проверить текст';
    }
}

function showWarning(message, isError = false) {
    const warningSpan = document.getElementById('wordWarning');
    if (warningSpan) {
        warningSpan.textContent = message;
        warningSpan.style.color = isError ? '#ef4444' : '#f59e0b';
    }
}

function clearWarning() {
    const warningSpan = document.getElementById('wordWarning');
    if (warningSpan) warningSpan.textContent = '';
}

async function sendDetect() {
    const elements = window.elements || {};

    if (!elements.input) return;

    const text = elements.input.value;
    const wordCount = window.countWords ? window.countWords(text) : 0;
    const maxWords = window.currentMaxWords || 1000;
    const minWords = window.currentMinWords || 50;

    clearWarning();

    if (!text.trim()) {
        showWarning('⚠️ Пожалуйста, введите текст для анализа', false);
        return;
    }

    if (wordCount < minWords) {
        showWarning(`❌ Минимальное количество слов: ${minWords}.`, true);
        return;
    }

    if (window.isWithinWordLimit && !window.isWithinWordLimit(text)) {
        showWarning(`❌ Максимальное количество слов: ${maxWords}.`, true);
        return;
    }

    if (!Auth.isAuthenticated()) {
        pendingDetectText = text;
        showWarning('🔐 Для использования сервиса необходимо войти в аккаунт', false);
        Auth.showAuthModal();
        return;
    }

    await processDetectText(text);
}

async function pasteFromClipboardDetect() {
    const textarea = document.getElementById('input');
    const pasteBtn = document.getElementById('pasteBtn');

    try {
        const text = await navigator.clipboard.readText();
        if (text) {
            textarea.value = text;
            textarea.dispatchEvent(new Event('input', { bubbles: true }));
            localStorage.setItem('detector_input_text', text);
            if (pasteBtn) pasteBtn.style.display = 'none';
        } else {
            showNotification('Буфер обмена пуст');
        }
    } catch (err) {
        console.error('Failed to read clipboard:', err);
        showNotification('Не удалось получить доступ к буферу обмена.');
    }
}

function initDetectorAutoSave() {
    const elements = window.elements || {};
    if (elements.input) {
        elements.input.addEventListener('input', () => {
            localStorage.setItem('detector_input_text', elements.input.value);
        });
    }
}

async function copyDetectResultText() {
    const elements = window.elements || {};
    const resultTextarea = elements.result;
    if (!resultTextarea) return;

    const text = resultTextarea.value;
    if (!text || !text.trim()) {
        showNotification('Нет текста для копирования', 'warning');
        return;
    }

    try {
        await navigator.clipboard.writeText(text);
        showNotification('Результат скопирован', 'success');
    } catch (err) {
        console.error('Copy failed:', err);
        showNotification('Не удалось скопировать текст', 'error');
    }
}

window.send = sendDetect;
window.showWarning = showWarning;
window.clearWarning = clearWarning;
window.pasteFromClipboard = pasteFromClipboardDetect;
window.loadTextFromLocalStorage = loadDetectorTextFromLocalStorage;
window.initAutoSave = initDetectorAutoSave;
window.copyResultText = copyDetectResultText;
window.copyInputText = async function() {
    const elements = window.elements || {};
    const text = elements.input?.value;
    if (!text || !text.trim()) {
        showNotification('Нет текста для копирования', 'warning');
        return;
    }
    try {
        await navigator.clipboard.writeText(text);
        showNotification('Текст скопирован', 'success');
    } catch {
        showNotification('Не удалось скопировать текст', 'error');
    }
};

document.addEventListener('DOMContentLoaded', () => {
    const pasteBtn = document.getElementById('pasteBtn');
    if (pasteBtn) pasteBtn.addEventListener('click', pasteFromClipboardDetect);

    const copyInputBtn = document.getElementById('copyInputBtn');
    if (copyInputBtn) copyInputBtn.addEventListener('click', window.copyInputText);

    const copyResultBtn = document.getElementById('copyResultBtn');
    if (copyResultBtn) copyResultBtn.addEventListener('click', copyDetectResultText);

    const detectBtn = document.getElementById('detectBtn');
    if (detectBtn) {
        detectBtn.addEventListener('click', () => sendDetect());
    }

    loadDetectorTextFromLocalStorage();
    initDetectorAutoSave();
});