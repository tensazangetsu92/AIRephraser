let pendingDetectText = null;
const CIRCLE_CIRCUMFERENCE = 2 * Math.PI * 50;

function loadTextFromLocalStorage() {
    const elements = window.elements || {};
    const savedInput = localStorage.getItem('detector_input_text');

    if (elements.input) {
        elements.input.value = savedInput || '';
        updateWordCounter();
    }

    if (!savedInput || !savedInput.trim()) {
        localStorage.removeItem('detector_result_data');
        hideResultColumns();
        return;
    }

    const savedResult = localStorage.getItem('detector_result_data');
    if (savedResult) {
        try {
            renderDetectorResult(JSON.parse(savedResult));
            showResultColumns();
        } catch {
            hideResultColumns();
        }
    } else {
        hideResultColumns();
    }
}

function showResultColumns() {
    document.getElementById('inputCol')?.style.setProperty('display', 'none');
    const resultCol = document.getElementById('resultCol');
    if (resultCol) resultCol.style.display = '';
    const reportCol = document.getElementById('detectorReportCol');
    if (reportCol) reportCol.style.display = 'flex';
    document.getElementById('editorContainer')?.classList.remove('single-col');
    const detectorBtnWrapper = document.querySelector('.detector-btn-wrapper');
    if (detectorBtnWrapper) detectorBtnWrapper.style.display = 'none'; // ← скрыть кнопку
    document.querySelectorAll('.col').forEach(col => col.style.height = '600px');
}

function hideResultColumns() {
    const inputCol = document.getElementById('inputCol');
    if (inputCol) inputCol.style.display = '';
    document.getElementById('resultCol')?.style.setProperty('display', 'none');
    document.getElementById('detectorReportCol')?.style.setProperty('display', 'none');
    document.getElementById('editorContainer')?.classList.add('single-col');
    const detectorBtnWrapper = document.querySelector('.detector-btn-wrapper');
    if (detectorBtnWrapper) detectorBtnWrapper.style.display = ''; // ← показать кнопку
    document.querySelectorAll('.col').forEach(col => col.style.height = '540px');
}

function renderDetectorResult(data) {
    const resultDiv = document.getElementById('result');
    if (resultDiv && Array.isArray(data.sentences)) {
        resultDiv.innerHTML = data.sentences.map(s =>
            `<span class="detector-sentence sentence-${s.label}">${escapeHtml(s.text)}</span>`
        ).join(' ');
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
    if (center) {
        const max = Math.max(data.ai_probability, data.human_probability, data.mixed_probability);
        const color = max === data.human_probability ? '#22c55e' :
                      max === data.mixed_probability ? '#f59e0b' : '#ef4444';
        center.textContent = 'AI';
        center.style.color = color;
    }
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
    const newCheckBtn = document.getElementById('newCheckBtn');

    if (detectBtn) {
        detectBtn.disabled = true;
        detectBtn.innerHTML = '<span class="loading"></span> Анализ...';
    }
    if (newCheckBtn) newCheckBtn.disabled = true;

    // Очищаем старые данные перед показом колонок
    if (resultDiv) resultDiv.innerHTML = '';

    const legendHuman = document.getElementById('legendHuman');
    const legendMixed = document.getElementById('legendMixed');
    const legendAi = document.getElementById('legendAi');
    if (legendHuman) legendHuman.textContent = '0%';
    if (legendMixed) legendMixed.textContent = '0%';
    if (legendAi) legendAi.textContent = '0%';

    const verdictEl = document.getElementById('detectorVerdict');
    if (verdictEl) verdictEl.innerHTML = '';

    const center = document.getElementById('detectorChartCenter');
    if (center) { center.textContent = 'AI'; center.style.color = ''; }

    // Сбрасываем график на серый
    ['chartHuman', 'chartMixed', 'chartAi'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.setAttribute('stroke-dasharray', `0 ${CIRCLE_CIRCUMFERENCE}`);
    });

    showResultColumns();
    showNotification('Анализ текста');

    try {
        const { ok, status, data } = await API.detect(text);

        if (ok) {
            renderDetectorResult(data.result);
            localStorage.setItem('detector_result_data', JSON.stringify(data.result));
            clearWarning();

            API.saveHistory('detector', text, JSON.stringify(data.result));

            if (typeof updateBalanceDisplay === 'function') updateBalanceDisplay();
            if (typeof loadCurrentSubscription === 'function') loadCurrentSubscription();
        } else if (status === 401) {
            if (resultDiv) resultDiv.textContent = '❌ Сессия истекла. Пожалуйста, войдите заново.';
            Auth.logout();
            if (typeof window.updateUI === 'function') window.updateUI();
            setTimeout(() => Auth.showAuthModal(), 1500);
        } else if (status === 429) {
            if (resultDiv) resultDiv.textContent = '❌ ' + (data.detail || 'Лимит токенов исчерпан');
            if (typeof updateBalanceDisplay === 'function') updateBalanceDisplay();
        } else {
            if (resultDiv) resultDiv.textContent = '❌ Ошибка: ' + (data.detail || 'Неизвестная ошибка');
        }
    } catch {
        if (resultDiv) resultDiv.textContent = '❌ Ошибка соединения с сервером';
    }

    if (detectBtn) {
        detectBtn.disabled = false;
        detectBtn.innerHTML = 'Проверить текст';
    }
    if (newCheckBtn) newCheckBtn.disabled = false;
}

async function send() {
    const elements = window.elements || {};
    if (!elements.input) return;

    const text = elements.input.value;
    const wordCount = countWords(text);

    clearWarning();

    if (!text.trim()) {
        showWarning('⚠️ Пожалуйста, введите текст для анализа');
        return;
    }

    if (wordCount < currentMinWords) {
        showWarning(`❌ Минимальное количество слов: ${currentMinWords}`, true);
        return;
    }

    if (!isWithinWordLimit(text)) {
        showWarning(`❌ Максимальное количество слов: ${currentMaxWords}`, true);
        return;
    }

    if (!Auth.isAuthenticated()) {
        pendingDetectText = text;
        showWarning('🔐 Для использования сервиса необходимо войти в аккаунт');
        Auth.showAuthModal();
        return;
    }

    await processDetectText(text);
}

async function pasteFromClipboard() {
    const textarea = document.getElementById('input');
    const pasteBtn = document.getElementById('pasteBtn');
    try {
        const text = await navigator.clipboard.readText();
        if (text) {
            textarea.value = text;
            textarea.dispatchEvent(new Event('input', { bubbles: true }));
            localStorage.setItem('detector_input_text', textarea.value);
            if (pasteBtn) pasteBtn.style.display = 'none';
        } else {
            showNotification('Буфер обмена пуст', 'warning');
        }
    } catch {
        showNotification('Не удалось получить доступ к буферу обмена', 'error');
    }
}

function initAutoSave() {
    const elements = window.elements || {};
    if (elements.input) {
        elements.input.addEventListener('input', () => {
            localStorage.setItem('detector_input_text', elements.input.value);
        });
    }
}

window.send = send;
window.pasteFromClipboard = pasteFromClipboard;
window.loadTextFromLocalStorage = loadTextFromLocalStorage;
window.initAutoSave = initAutoSave;

window.copyInputText = () => {
    const btn = document.getElementById('copyInputBtn');
    copyButtonText(btn, () => window.elements?.input?.value);
};

window.copyResultText = () => {
    const btn = document.getElementById('copyResultBtn');
    copyButtonText(btn, () => document.getElementById('result')?.innerText);
};

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('pasteBtn')?.addEventListener('click', pasteFromClipboard);
    document.getElementById('copyInputBtn')?.addEventListener('click', window.copyInputText);
    document.getElementById('copyResultBtn')?.addEventListener('click', window.copyResultText);
    document.getElementById('detectBtn')?.addEventListener('click', send);

    document.getElementById('newCheckBtn')?.addEventListener('click', () => {
        localStorage.removeItem('detector_input_text');
        localStorage.removeItem('detector_result_data');
        const elements = window.elements || {};
        if (elements.input) elements.input.value = '';
        hideResultColumns();
        updateWordCounter();
    });

    loadTextFromLocalStorage();
    initAutoSave();
});