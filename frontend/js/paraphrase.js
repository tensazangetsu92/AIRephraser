(function() {
let pendingParaphraseText  = null;
const RESULT_MAX_AGE_MS = 24 * 60 * 60 * 1000; // 24 часа

function loadTextFromLocalStorage() {
    const elements = window.elements || {};
    const historyRestore = typeof takeHistoryRestore === 'function' ? takeHistoryRestore('paraphraser') : null;
    if (historyRestore) {
        localStorage.setItem('paraphrase_input_text', historyRestore.original || '');
        localStorage.setItem('paraphrase_result_text', historyRestore.result || '');
        localStorage.setItem('paraphrase_result_time', Date.now());
    }
    const savedInput = localStorage.getItem('paraphrase_input_text');
    const savedResult = localStorage.getItem('paraphrase_result_text');
    const savedTime = localStorage.getItem('paraphrase_result_time');

    if (elements.input) {
        elements.input.value = savedInput || '';
        updateWordCounter();
    }

    if (!savedInput || !savedInput.trim()) {
        localStorage.removeItem('paraphrase_result_text');
        localStorage.removeItem('paraphrase_result_time');
        if (elements.result) elements.result.value = '';
        hideResultColumn();
        return;
    }

    const isExpired = !savedTime || (Date.now() - parseInt(savedTime)) > RESULT_MAX_AGE_MS;

    if (elements.result && savedResult && !isExpired) {
        elements.result.value = savedResult;
        updateResultWordCounter(savedResult);
        showResultColumn();
    } else {
        localStorage.removeItem('paraphrase_result_text');
        localStorage.removeItem('paraphrase_result_time');
        if (elements.input) elements.input.value = '';
        localStorage.removeItem('paraphrase_input_text');
        if (elements.result) elements.result.value = '';
        updateResultWordCounter('');
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

function initAutoSave() {
    const elements = window.elements || {};
    if (elements.input) {
        elements.input.addEventListener('input', () => {
            localStorage.setItem('paraphrase_input_text', elements.input.value);
        });
    }
}

async function processText(text) {
    const elements = window.elements || {};
    const paraphraseBtn = document.getElementById('paraphraseBtn');
    if (!startTextProcessing('paraphrase')) return;

    if (paraphraseBtn) {
        paraphraseBtn.disabled = true;
        paraphraseBtn.innerHTML = '<span class="loading"></span> Перефразирование...';
    }
    if (elements.result) {
        elements.result.value = 'Перефразирование текста...';
        updateResultWordCounter('');
    }

    try {
        const { ok, status, data } = await API.paraphrase(
            text,
            elements.tone?.value || 'neutral',
            elements.style?.value || 'similar'
        );

        if (ok) {
            if (elements.result) elements.result.value = data.result;
            updateResultWordCounter(data.result);
            localStorage.setItem('paraphrase_result_text', data.result);
            localStorage.setItem('paraphrase_result_time', Date.now());
            clearWarning();
            showResultColumn();
            API.saveHistory('paraphraser', text, data.result);
            if (typeof refreshAllSubscriptionData === 'function') refreshAllSubscriptionData();
            showToolSuccess('paraphrase');
        } else if (status === 401) {
            const errorMessage = showToolError(status, data);
            if (elements.result) elements.result.value = errorMessage;
            showResultColumn();
            Auth.logout();
            if (typeof window.updateUI === 'function') window.updateUI();
            setTimeout(() => Auth.showAuthModal(), 1500);
        } else if (status === 429) {
            const errorMessage = showToolError(status, data);
            if (elements.result) elements.result.value = errorMessage;
            showResultColumn();
            if (typeof refreshAllSubscriptionData === 'function') refreshAllSubscriptionData();
        } else {
            const errorMessage = showToolError(status, data, 'Не удалось перефразировать текст');
            if (elements.result) elements.result.value = errorMessage;
            showResultColumn();
        }
    } catch {
        const errorMessage = showToolNetworkError();
        if (elements.result) elements.result.value = errorMessage;
        showResultColumn();
    } finally {
        if (paraphraseBtn) {
            paraphraseBtn.disabled = false;
            paraphraseBtn.innerHTML = '<img class="logo-img" src="/images/logo-no-background.svg" alt="Humary Logo" width="32" height="32">Перефразировать';
        }
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
        showWarning('⚠️ Пожалуйста, введите текст для перефразирования');
        if (elements.result) elements.result.value = '⚠️ Пожалуйста, введите текст для перефразирования';
        return;
    }

    if (!Auth.isAuthenticated()) {
        pendingParaphraseText  = text;
        showWarning('🔐 Для использования сервиса необходимо войти в аккаунт');
        if (elements.result) elements.result.value = '🔐 Для использования сервиса необходимо войти в аккаунт';
        Auth.showAuthModal();
        return;
    }

    if (wordCount < currentMinWords) {
        showWarning(`Минимальное количество слов: ${currentMinWords}`, true);
        return;
    }

    if (!isWithinWordLimit(text)) {
        showRequestLimitError(text);
        return;
    }

    await processText(text);
}

async function processPendingText() {
    if (!pendingParaphraseText  || !Auth.isAuthenticated()) return;
    if (isWithinWordLimit(pendingParaphraseText )) {
        const text = pendingParaphraseText ;
        pendingParaphraseText  = null;
        await processText(text);
    } else {
        showWarning(`❌ Максимальное количество слов: ${currentMaxWords}`, true);
        pendingParaphraseText  = null;
    }
}

window.send = send;
window.processPendingText = processPendingText;
window.pasteFromClipboard = pasteFromClipboard;
window.loadTextFromLocalStorage = loadTextFromLocalStorage;
window.initAutoSave = initAutoSave;

window.copyInputText = () => {
    const btn = document.getElementById('copyInputBtn');
    copyButtonText(btn, () => window.elements?.input?.value);
};

window.copyResultText = () => {
    const btn = document.getElementById('copyResultBtn');
    copyButtonText(btn, () => {
        const val = window.elements?.result?.value;
        if (!val || val.startsWith('⚠️') || val.startsWith('❌') || val.startsWith('🔐') || val === 'Перефразирование текста...') return '';
        return val;
    });
};

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('pasteBtn')?.addEventListener('click', pasteFromClipboard);
    document.getElementById('copyInputBtn')?.addEventListener('click', window.copyInputText);
    document.getElementById('copyResultBtn')?.addEventListener('click', window.copyResultText);
    document.getElementById('paraphraseBtn')?.addEventListener('click', send);

    loadTextFromLocalStorage();
    initAutoSave();
    initPdfUpload();
    initWordUpload();
});
})();
