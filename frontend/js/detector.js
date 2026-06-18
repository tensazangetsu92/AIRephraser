// frontend/js/detector.js

let pendingDetectText = null;
const CIRCLE_CIRCUMFERENCE = 2 * Math.PI * 50; // r=50 в SVG

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
        hideResultColumns();
        return;
    }

    if (savedResult) {
        try {
            const data = JSON.parse(savedResult);
            renderDetectorResult(data);
            showResultColumns();
        } catch {
            hideResultColumns();
        }
    } else {
        hideResultColumns();
    }
}

function showResultColumns() {
    const inputCol = document.getElementById('inputCol');
    const resultCol = document.getElementById('resultCol');
    const reportCol = document.getElementById('detectorReportCol');
    const editor = document.getElementById('editorContainer');
    const controls = document.querySelector('.controls');

    if (inputCol) inputCol.style.display = 'none';
    if (resultCol) resultCol.style.display = '';
    if (reportCol) reportCol.style.display = 'flex';
    if (editor) editor.classList.remove('single-col');
    if (controls) controls.style.display = 'none';
}

function hideResultColumns() {
    const inputCol = document.getElementById('inputCol');
    const resultCol = document.getElementById('resultCol');
    const reportCol = document.getElementById('detectorReportCol');
    const editor = document.getElementById('editorContainer');
    const controls = document.querySelector('.controls');

    if (inputCol) inputCol.style.display = '';
    if (resultCol) resultCol.style.display = 'none';
    if (reportCol) reportCol.style.display = 'none';
    if (editor) editor.classList.add('single-col');
    if (controls) controls.style.display = '';
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function renderDetectorResult(data) {
    const resultDiv = document.getElementById('result');

    if (resultDiv && Array.isArray(data.sentences)) {
        resultDiv.innerHTML = data.sentences.map(s => {
            const cls = `detector-sentence sentence-${s.label}`;
            return `<span class="${cls}">${escapeHtml(s.text)}</span>`;
        }).join(' ');
    }

    renderDonutChart(data.human_probability, data.mixed_probability, data.ai_probability);

    const legendHuman = document.getElementById('legendHuman');
    const legendMixed = document.getElementById('legendMixed');
    const legendAi = document.getElementById('legendAi');
    if (legendHuman) legendHuman.textContent = `${data.human_probability}%`;
    if (legendMixed) legendMixed.textContent = `${data.mixed_probability}%`;
    if (legendAi) legendAi.textContent = `${data.ai_probability}%`;

    const verdictEl = document.getElementById('detectorVerdict');
    if (verdictEl) {
        verdictEl.innerHTML = `<strong>${escapeHtml(data.verdict || '')}</strong><br>${escapeHtml(data.explanation || '')}`;
    }

    const center = document.getElementById('detectorChartCenter');
    if (center) center.textContent = `${data.ai_probability}%`;
}

function renderDonutChart(humanPct, mixedPct, aiPct) {
    const chartHuman = document.getElementById('chartHuman');
    const chartMixed = document.getElementById('chartMixed');
    const chartAi = document.getElementById('chartAi');

    if (!chartHuman || !chartMixed || !chartAi) return;

    const humanLen = (humanPct / 100) * CIRCLE_CIRCUMFERENCE;
    const mixedLen = (mixedPct / 100) * CIRCLE_CIRCUMFERENCE;
    const aiLen = (aiPct / 100) * CIRCLE_CIRCUMFERENCE;

    chartHuman.setAttribute('stroke-dasharray', `${humanLen} ${CIRCLE_CIRCUMFERENCE}`);
    chartHuman.setAttribute('stroke-dashoffset', '0');

    chartMixed.setAttribute('stroke-dasharray', `${mixedLen} ${CIRCLE_CIRCUMFERENCE}`);
    chartMixed.setAttribute('stroke-dashoffset', `${-humanLen}`);

    chartAi.setAttribute('stroke-dasharray', `${aiLen} ${CIRCLE_CIRCUMFERENCE}`);
    chartAi.setAttribute('stroke-dashoffset', `${-(humanLen + mixedLen)}`);
}

async function processDetectText(text) {
    const detectBtn = document.getElementById('detectBtn');
    const resultDiv = document.getElementById('result');

    if (detectBtn) {
        detectBtn.disabled = true;
        detectBtn.innerHTML = '<span class="loading"></span> Анализ...';
    }
    if (resultDiv) {
        resultDiv.textContent = 'Анализ текста...';
    }
    showResultColumns();
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
            if (resultDiv) resultDiv.textContent = '❌ Сессия истекла. Пожалуйста, войдите заново.';
            Auth.logout();
            if (typeof window.updateUI === 'function') window.updateUI();
            setTimeout(() => Auth.showAuthModal(), 1500);
        } else if (response.status === 429) {
            if (resultDiv) resultDiv.textContent = '❌ ' + (data.detail || 'Лимит токенов исчерпан');
            if (typeof updateBalanceDisplay === 'function') updateBalanceDisplay();
        } else {
            if (resultDiv) resultDiv.textContent = '❌ Ошибка: ' + (data.detail || 'Неизвестная ошибка');
        }
    } catch (err) {
        console.error('Detect error:', err);
        if (resultDiv) resultDiv.textContent = '❌ Ошибка соединения с сервером';
    }

    if (detectBtn) {
        detectBtn.disabled = false;
        detectBtn.innerHTML = 'Проверить текст';
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
    const resultDiv = document.getElementById('result');
    if (!resultDiv) return;

    const text = resultDiv.innerText;
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

    const newCheckBtn = document.getElementById('newCheckBtn');
    if (newCheckBtn) {
        newCheckBtn.addEventListener('click', () => {
            localStorage.removeItem('detector_input_text');
            localStorage.removeItem('detector_result_data');
            const elements = window.elements || {};
            if (elements.input) elements.input.value = '';
            hideResultColumns();
            if (typeof window.updateWordCounter === 'function') window.updateWordCounter();
        });
    }

    loadDetectorTextFromLocalStorage();
    initDetectorAutoSave();
});