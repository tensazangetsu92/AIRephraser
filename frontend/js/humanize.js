(function() {
let pendingText = null;

const RESULT_MAX_AGE_MS = 16 * 60 * 60 * 1000;

async function loadTextFromLocalStorage() {
    const elements = window.elements || {};
    const historyRestore = typeof getHistoryRestore === 'function' ? await getHistoryRestore('humanizer') : null;
    if (historyRestore) {
        localStorage.setItem('saved_input_text', historyRestore.original || '');
        localStorage.setItem('saved_result_text', historyRestore.result || '');
        localStorage.setItem('saved_result_time', Date.now());
    }
    const savedInput = localStorage.getItem('saved_input_text');
    const savedResult = localStorage.getItem('saved_result_text');
    const savedTime = localStorage.getItem('saved_result_time');

    if (elements.input) {
        elements.input.value = savedInput || '';
        updateWordCounter();
    }

    if (!savedInput || !savedInput.trim()) {
        localStorage.removeItem('saved_result_text');
        localStorage.removeItem('saved_result_time');
        if (elements.result) elements.result.value = '';
        hideResultColumn();
        setNewCheckButtonVisible(false);
        return;
    }

    const isExpired = !savedTime || (Date.now() - parseInt(savedTime)) > RESULT_MAX_AGE_MS;

    if (elements.result && savedResult && !isExpired) {
        elements.result.value = savedResult;
        updateResultWordCounter(savedResult);
        showResultColumn();
        setNewCheckButtonVisible(true);
    } else {
        localStorage.removeItem('saved_result_text');
        localStorage.removeItem('saved_result_time');
        if (elements.result) elements.result.value = '';
        updateResultWordCounter('');
        hideResultColumn();
        setNewCheckButtonVisible(false);
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

function setNewCheckButtonVisible(isVisible) {
    const button = document.getElementById('humanizeNewCheckBtn');
    if (button) button.style.display = isVisible ? 'inline-flex' : 'none';
}

function initAutoSave() {
    const elements = window.elements || {};
    if (elements.input) {
        elements.input.addEventListener('input', () => {
            localStorage.setItem('saved_input_text', elements.input.value);
        });
    }
}

async function processText(text) {
    const elements = window.elements || {};
    const humanizeButtonMarkup = elements.humanizeBtn?.innerHTML;
    if (!startTextProcessing('humanize')) return;

    if (elements.humanizeBtn) {
        elements.humanizeBtn.disabled = true;
        elements.humanizeBtn.innerHTML = '<span class="loading"></span> Обработка...';
    }
    setNewCheckButtonVisible(false);

    try {
        const { ok, status, data } = await API.humanize(
            text,
            elements.style?.value || 'human',
            elements.targetLanguage?.value || 'ru'
        );

        if (ok) {
            clearWarning();
            if (typeof refreshAllSubscriptionData === 'function') await refreshAllSubscriptionData(true);
            if (await redirectToSavedHistory('humanizer', text, data.result)) return;

            if (elements.result) elements.result.value = data.result;
            updateResultWordCounter(data.result);
            localStorage.setItem('saved_result_text', data.result);
            localStorage.setItem('saved_result_time', Date.now());
            showResultColumn();
            setNewCheckButtonVisible(true);
            showToolSuccess('humanize');
        } else if (status === 401) {
            showToolError(status, data);
            Auth.logout();
            if (typeof window.updateUI === 'function') window.updateUI();
            setTimeout(() => Auth.showAuthModal(), 1500);
        } else if (status === 429) {
            showToolError(status, data);
            if (typeof refreshAllSubscriptionData === 'function') refreshAllSubscriptionData(true);
        } else {
            showToolError(status, data, 'Не удалось обработать текст');
        }
    } catch {
        showToolNetworkError();
    } finally {
        if (elements.humanizeBtn) {
            elements.humanizeBtn.disabled = false;
            elements.humanizeBtn.innerHTML = humanizeButtonMarkup;
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
        showWarning('⚠️ Пожалуйста, введите текст для обработки');
        if (elements.result) elements.result.value = '⚠️ Пожалуйста, введите текст для обработки';
        return;
    }

    if (!Auth.isAuthenticated()) {
        pendingText = text;
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
    if (!pendingText || !Auth.isAuthenticated()) return;

    if (isWithinWordLimit(pendingText)) {
        const text = pendingText;
        pendingText = null;
        await processText(text);
    } else {
        showWarning(`❌ Максимальное количество слов: ${currentMaxWords}`, true);
        pendingText = null;
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
        if (!val || val.startsWith('⚠️') || val.startsWith('❌') || val.startsWith('🔐') || val === 'Обработка текста...') return '';
        return val;
    });
};

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('pasteBtn')?.addEventListener('click', pasteFromClipboard);
    document.getElementById('copyInputBtn')?.addEventListener('click', window.copyInputText);
    document.getElementById('copyResultBtn')?.addEventListener('click', window.copyResultText);
    document.getElementById('humanizeNewCheckBtn')?.addEventListener('click', () => {
        const elements = window.elements || {};
        localStorage.removeItem('saved_input_text');
        localStorage.removeItem('saved_result_text');
        localStorage.removeItem('saved_result_time');
        if (elements.input) elements.input.value = '';
        if (elements.result) elements.result.value = '';
        updateWordCounter();
        updateResultWordCounter('');
        hideResultColumn();
        setNewCheckButtonVisible(false);
        elements.input?.focus();
    });
    loadTextFromLocalStorage();
    initAutoSave();
    initPdfUpload();
    initWordUpload();
});
})();
