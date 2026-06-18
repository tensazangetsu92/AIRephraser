let pendingText = null;

function loadTextFromLocalStorage() {
    const elements = window.elements || {};
    const savedInput = localStorage.getItem('saved_input_text');
    const savedResult = localStorage.getItem('saved_result_text');

    if (elements.input) {
        elements.input.value = savedInput || '';
        updateWordCounter();
    }

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
            localStorage.setItem('saved_input_text', elements.input.value);
        });
    }
}

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
            showNotification('Буфер обмена пуст', 'warning');
        }
    } catch {
        showNotification('Не удалось получить доступ к буферу обмена', 'error');
    }
}

async function processText(text) {
    const elements = window.elements || {};

    if (elements.humanizeBtn) {
        elements.humanizeBtn.disabled = true;
        elements.humanizeBtn.innerHTML = '<span class="loading"></span> Обработка...';
    }
    if (elements.result) {
        elements.result.value = 'Обработка текста...';
        showNotification('Обработка текста');
    }

    try {
        const { ok, status, data } = await API.humanize(
            text,
            elements.intensity?.value || 'medium',
            elements.tone?.value || 'neutral',
            elements.style?.value || 'simple',
            elements.length?.value || 'same'
        );

        if (ok) {
            if (elements.result) elements.result.value = data.result;
            localStorage.setItem('saved_result_text', data.result);
            clearWarning();
            showResultColumn();
            API.saveHistory('humanizer', text, data.result);
            if (typeof updateBalanceDisplay === 'function') updateBalanceDisplay();
            if (typeof loadCurrentSubscription === 'function') loadCurrentSubscription();
        } else if (status === 401) {
            if (elements.result) elements.result.value = '❌ Сессия истекла. Пожалуйста, войдите заново.';
            Auth.logout();
            if (typeof window.updateUI === 'function') window.updateUI();
            setTimeout(() => Auth.showAuthModal(), 1500);
        } else if (status === 429) {
            if (elements.result) elements.result.value = '❌ ' + (data.detail || 'Лимит токенов исчерпан');
            if (typeof updateBalanceDisplay === 'function') updateBalanceDisplay();
        } else {
            if (elements.result) elements.result.value = '❌ Ошибка: ' + (data.detail || 'Неизвестная ошибка');
        }
    } catch {
        if (elements.result) elements.result.value = '❌ Ошибка соединения с сервером';
    }

    if (elements.humanizeBtn) {
        elements.humanizeBtn.disabled = false;
        elements.humanizeBtn.innerHTML = 'Очеловечить текст';
    }
}

async function send() {
    const elements = window.elements || {};
    if (!elements.input) return;

    const text = elements.input.value;
    const wordCount = countWords(text);

    clearWarning();

    if (!text.trim()) {
        showWarning('⚠️ Пожалуйста, введите текст для обработки');
        if (elements.result) elements.result.value = '⚠️ Пожалуйста, введите текст для обработки';
        return;
    }

    if (wordCount < currentMinWords) {
        showWarning(`Минимальное количество слов: ${currentMinWords}`, true);
        return;
    }

    if (!isWithinWordLimit(text)) {
        showWarning(`Максимальное количество слов: ${currentMaxWords}`, true);
        return;
    }

    if (!Auth.isAuthenticated()) {
        pendingText = text;
        showWarning('🔐 Для использования сервиса необходимо войти в аккаунт');
        if (elements.result) elements.result.value = '🔐 Для использования сервиса необходимо войти в аккаунт';
        Auth.showAuthModal();
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

function initPdfUpload() {
    if (typeof pdfjsLib === 'undefined') return;

    pdfjsLib.GlobalWorkerOptions.workerSrc =
        'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';

    const pdfBtn = document.getElementById('pdfBtn');
    const pdfFileInput = document.getElementById('pdfFileInput');
    if (!pdfBtn || !pdfFileInput) return;

    const newPdfBtn = pdfBtn.cloneNode(true);
    pdfBtn.parentNode.replaceChild(newPdfBtn, pdfBtn);

    newPdfBtn.addEventListener('click', () => pdfFileInput.click());

    pdfFileInput.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        newPdfBtn.disabled = true;
        newPdfBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Загрузка...';

        try {
            const arrayBuffer = await file.arrayBuffer();
            const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
            let fullText = '';

            for (let i = 1; i <= pdf.numPages; i++) {
                const page = await pdf.getPage(i);
                const textContent = await page.getTextContent();
                let lastY = null;
                let pageText = '';

                for (const item of textContent.items) {
                    if (lastY !== null && Math.abs(item.transform[5] - lastY) > 5) {
                        pageText += '\n';
                    }
                    if (pageText && !pageText.endsWith('\n') && !pageText.endsWith(' ') && item.str && !item.str.startsWith(' ')) {
                        pageText += ' ';
                    }
                    pageText += item.str;
                    lastY = item.transform[5];
                }
                fullText += pageText + '\n\n';
            }

            const text = fullText.trim();
            if (!text) {
                showNotification('PDF не содержит текста — возможно это сканированный документ', 'warning');
                return;
            }

            const input = document.getElementById('input');
            input.value = text;
            input.dispatchEvent(new Event('input', { bubbles: true }));
            showNotification('Текст из PDF успешно загружен', 'success');

        } catch {
            showNotification('Не удалось прочитать PDF файл', 'error');
        } finally {
            newPdfBtn.disabled = false;
            newPdfBtn.innerHTML = '<i class="fas fa-file-pdf"></i> Загрузить PDF';
            pdfFileInput.value = '';
        }
    });
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

    loadTextFromLocalStorage();
    initAutoSave();
    initPdfUpload();
});