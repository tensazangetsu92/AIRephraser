let pendingDetectText = null;
const CIRCLE_CIRCUMFERENCE = 2 * Math.PI * 50;
const RESULT_MAX_AGE_MS = 16 * 60 * 60 * 1000;

function loadTextFromLocalStorage() {
    const elements = window.elements || {};
    const historyRestore = typeof takeHistoryRestore === 'function' ? takeHistoryRestore('detector') : null;
    if (historyRestore) {
        localStorage.setItem('detector_input_text', historyRestore.original || '');
        localStorage.setItem('detector_result_data', historyRestore.result || '');
        localStorage.setItem('detector_result_time', Date.now());
    }
    const savedInput = localStorage.getItem('detector_input_text');
    const savedResult = localStorage.getItem('detector_result_data');
    const savedTime = localStorage.getItem('detector_result_time');

    if (elements.input) {
        elements.input.value = savedInput || '';
        updateWordCounter();
    }

    if (!savedInput || !savedInput.trim()) {
        localStorage.removeItem('detector_result_data');
        localStorage.removeItem('detector_result_time');
        hideResultColumns();
        return;
    }

    const isExpired = !savedTime || (Date.now() - parseInt(savedTime)) > RESULT_MAX_AGE_MS;

    if (savedResult && !isExpired) {
        try {
            renderDetectorResult(JSON.parse(savedResult));
            showResultColumns();
        } catch {
            hideResultColumns();
        }
    } else {
        localStorage.removeItem('detector_result_data');
        localStorage.removeItem('detector_result_time');
        localStorage.removeItem('detector_input_text'); // ← добавь
        if (elements.input) elements.input.value = ''; // ← добавь
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
    if (detectorBtnWrapper) detectorBtnWrapper.style.display = 'none';
    document.querySelectorAll('.col').forEach(col => col.style.height = '600px');
}

function hideResultColumns() {
    const inputCol = document.getElementById('inputCol');
    if (inputCol) inputCol.style.display = '';
    document.getElementById('resultCol')?.style.setProperty('display', 'none');
    document.getElementById('detectorReportCol')?.style.setProperty('display', 'none');
    document.getElementById('editorContainer')?.classList.add('single-col');
    const detectorBtnWrapper = document.querySelector('.detector-btn-wrapper');
    if (detectorBtnWrapper) detectorBtnWrapper.style.display = '';
}

function renderDetectorResult(data) {
    data = data && typeof data === 'object' ? data : {};
    const humanProbability = Number.isFinite(Number(data.human_probability)) ? Number(data.human_probability) : 0;
    const mixedProbability = Number.isFinite(Number(data.mixed_probability)) ? Number(data.mixed_probability) : 0;
    const aiProbability = Number.isFinite(Number(data.ai_probability)) ? Number(data.ai_probability) : 0;
    const sentences = Array.isArray(data.sentences) ? data.sentences.filter(Boolean) : [];
    const resultDiv = document.getElementById('result');
    if (resultDiv) {
        resultDiv.innerHTML = sentences.map(s =>
            `<span class="detector-sentence sentence-${['human', 'mixed', 'ai'].includes(s.label) ? s.label : 'mixed'}">${escapeHtml(String(s.text || ''))}</span>`
        ).join(' ');
    }
    updateResultWordCounter(sentences.map(s => String(s.text || '')).join(' '));

    renderDonutChart(humanProbability, mixedProbability, aiProbability);

    const legendHuman = document.getElementById('legendHuman');
    const legendMixed = document.getElementById('legendMixed');
    const legendAi = document.getElementById('legendAi');
    if (legendHuman) legendHuman.textContent = `${humanProbability}%`;
    if (legendMixed) legendMixed.textContent = `${mixedProbability}%`;
    if (legendAi) legendAi.textContent = `${aiProbability}%`;

    const verdictEl = document.getElementById('detectorVerdict');
    if (verdictEl) {
        verdictEl.innerHTML = `<strong>${escapeHtml(data.verdict || '')}</strong><br>${escapeHtml(data.explanation || '')}`;
    }

    const center = document.getElementById('detectorChartCenter');
    if (center) {
        const max = Math.max(aiProbability, humanProbability, mixedProbability);
        const color = max === humanProbability ? '#22c55e' :
                      max === mixedProbability ? '#f59e0b' : '#ef4444';
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
    if (!startTextProcessing('detector')) return;

    if (detectBtn) {
        detectBtn.disabled = true;
        detectBtn.innerHTML = '<span class="loading"></span> Анализ...';
    }
    if (newCheckBtn) newCheckBtn.disabled = true;

    if (resultDiv) resultDiv.innerHTML = '';
    updateResultWordCounter('');

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

    ['chartHuman', 'chartMixed', 'chartAi'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.setAttribute('stroke-dasharray', `0 ${CIRCLE_CIRCUMFERENCE}`);
    });

    try {
        const { ok, status, data } = await API.detect(text);

        if (ok) {
            renderDetectorResult(data.result);
            showResultColumns();
            localStorage.setItem('detector_result_data', JSON.stringify(data.result));
            localStorage.setItem('detector_result_time', Date.now());
            clearWarning();
            API.saveHistory('detector', text, JSON.stringify(data.result));
            if (typeof refreshAllSubscriptionData === 'function') refreshAllSubscriptionData();
            showToolSuccess('detector');
        } else if (status === 401) {
            const errorMessage = showToolError(status, data);
            if (resultDiv) resultDiv.textContent = errorMessage;
            showResultColumns();
            Auth.logout();
            if (typeof window.updateUI === 'function') window.updateUI();
            setTimeout(() => Auth.showAuthModal(), 1500);
        } else if (status === 429) {
            const errorMessage = showToolError(status, data);
            if (resultDiv) resultDiv.textContent = errorMessage;
            showResultColumns();
            if (typeof refreshAllSubscriptionData === 'function') refreshAllSubscriptionData();
        } else {
            const errorMessage = showToolError(status, data, 'Не удалось проанализировать текст');
            if (resultDiv) resultDiv.textContent = errorMessage;
            showResultColumns();
        }
    } catch {
        const errorMessage = showToolNetworkError();
        if (resultDiv) resultDiv.textContent = errorMessage;
        showResultColumns();
    } finally {
        if (detectBtn) {
            detectBtn.disabled = false;
            detectBtn.innerHTML = '<img class="logo-img" src="/images/logo-no-background.svg" alt="Humary Logo" width="32" height="32">Проверить текст';
        }
        if (newCheckBtn) newCheckBtn.disabled = false;
        finishTextProcessing();
    }
}

async function send() {
    const elements = window.elements || {};
    if (!elements.input) return;

    const text = elements.input.value;
    const wordCount = countWords(text);

    clearWarning();

    if (!text.trim()) {
        showEmptyTextError(elements.input);
        return;
    }

    if (!text.trim()) {
        showWarning('⚠️ Пожалуйста, введите текст для анализа');
        return;
    }

    if (!Auth.isAuthenticated()) {
        pendingDetectText = text;
        showWarning('🔐 Для использования сервиса необходимо войти в аккаунт');
        Auth.showAuthModal();
        return;
    }

    if (wordCount < currentMinWords) {
        showWarning(`❌ Минимальное количество слов: ${currentMinWords}`, true);
        return;
    }

    if (!isWithinWordLimit(text)) {
        showRequestLimitError(text);
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
        localStorage.removeItem('detector_result_time');
        const elements = window.elements || {};
        if (elements.input) elements.input.value = '';
        hideResultColumns();
        updateWordCounter();
    });

    loadTextFromLocalStorage();
    initAutoSave();
    initPdfUpload();
    initWordUpload();
});
