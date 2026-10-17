const DEFAULT_MAX_WORDS = 500;
const DEFAULT_MIN_WORDS = 50;
const MAX_UPLOAD_FILE_SIZE_BYTES = 10 * 1024 * 1024;
const MAX_UPLOAD_FILE_SIZE_LABEL = '10 МБ';
const USER_CACHE_PREFIX = 'humary.user-cache.v1.';
const EXTERNAL_SCRIPT_PROMISES = new Map();
const PDF_JS_URL = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js';
const PDF_WORKER_URL = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
const MAMMOTH_URL = 'https://cdn.jsdelivr.net/npm/mammoth@1.12.0/mammoth.browser.min.js';

function loadExternalScript(url, globalName) {
    if (window[globalName]) return Promise.resolve(window[globalName]);
    if (EXTERNAL_SCRIPT_PROMISES.has(url)) return EXTERNAL_SCRIPT_PROMISES.get(url);

    const promise = new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = url;
        script.async = true;
        script.onload = () => window[globalName]
            ? resolve(window[globalName])
            : reject(new Error(`Global ${globalName} was not created by ${url}`));
        script.onerror = () => reject(new Error(`Could not load ${url}`));
        document.head.appendChild(script);
    }).catch(error => {
        EXTERNAL_SCRIPT_PROMISES.delete(url);
        throw error;
    });

    EXTERNAL_SCRIPT_PROMISES.set(url, promise);
    return promise;
}

async function loadPdfJs() {
    const pdfjs = await loadExternalScript(PDF_JS_URL, 'pdfjsLib');
    pdfjs.GlobalWorkerOptions.workerSrc = PDF_WORKER_URL;
    return pdfjs;
}

function loadMammoth() {
    return loadExternalScript(MAMMOTH_URL, 'mammoth');
}

let currentMaxWords = DEFAULT_MAX_WORDS;
let currentMinWords = DEFAULT_MIN_WORDS;
let textProcessingInProgress = false;

function getUserCacheStorageKey(key) {
    const userId = typeof Auth !== 'undefined' ? Auth.getUser?.()?.id : null;
    return userId ? `${USER_CACHE_PREFIX}${userId}.${key}` : null;
}

function getCachedUserData(key) {
    const storageKey = getUserCacheStorageKey(key);
    if (!storageKey) return null;

    try {
        const saved = JSON.parse(sessionStorage.getItem(storageKey) || 'null');
        if (!saved?.data || Number(saved.expiresAt) <= Date.now()) {
            sessionStorage.removeItem(storageKey);
            return null;
        }
        return saved.data;
    } catch {
        return null;
    }
}

function setCachedUserData(key, data, ttlMs) {
    const storageKey = getUserCacheStorageKey(key);
    if (!storageKey || !data) return;

    try {
        sessionStorage.setItem(storageKey, JSON.stringify({ data, expiresAt: Date.now() + ttlMs }));
    } catch {
        // The interface remains functional when sessionStorage is unavailable.
    }
}

function clearCachedUserData(keyPrefix = '') {
    try {
        Object.keys(sessionStorage)
            .filter(key => key.startsWith(USER_CACHE_PREFIX) && key.includes(`.${keyPrefix}`))
            .forEach(key => sessionStorage.removeItem(key));
    } catch {
        // Cache invalidation must not interrupt the interface.
    }
}

const TOOL_STATUS_MESSAGES = {
    humanize: {
        loading: 'Редактируем текст. Это может занять до минуты.',
        success: 'Текст успешно отредактирован'
    },
    paraphrase: {
        loading: 'Перефразируем текст. Это может занять до минуты.',
        success: 'Текст успешно перефразирован'
    },
    detector: {
        loading: 'Анализируем текст. Это может занять до минуты.',
        success: 'Анализ текста готов'
    }
};

function countWords(text) {
    if (!text || !text.trim()) return 0;
    return text.trim().split(/\s+/).length;
}

function isWithinWordLimit(text) {
    return countWords(text) <= currentMaxWords;
}

function getRequestLimitMessage(text) {
    const wordCount = countWords(text);
    const excessWords = Math.max(0, wordCount - currentMaxWords);
    return `Превышен лимит слов за один запрос. Максимум: ${currentMaxWords}. Сейчас: ${wordCount}. Сократите текст на ${excessWords} слов.`;
}

function showRequestLimitError(text) {
    const message = getRequestLimitMessage(text);
    showWarning(message, true);
    if (typeof showNotification === 'function') {
        showNotification('Превышен лимит слов за один запрос', 'warning', 7000);
    }
    return message;
}

function showEmptyTextError(input) {
    const message = 'Вставьте текст для обработки.';
    showWarning(message, true);
    if (typeof showNotification === 'function') {
        showNotification('Сначала добавьте текст', 'warning');
    }
    input?.focus();
    return message;
}

function startTextProcessing(tool = 'humanize') {
    if (textProcessingInProgress) {
        if (typeof showNotification === 'function') {
            showNotification('Текст уже обрабатывается', 'info');
        }
        return false;
    }
    textProcessingInProgress = true;
    const message = TOOL_STATUS_MESSAGES[tool]?.loading || 'Обрабатываем текст. Это может занять до минуты.';
    if (typeof showNotification === 'function') {
        showNotification(message, 'info', 12000);
    }
    return true;
}

function finishTextProcessing() {
    textProcessingInProgress = false;
}

function showToolSuccess(tool) {
    const message = TOOL_STATUS_MESSAGES[tool]?.success || 'Обработка завершена';
    if (typeof showNotification === 'function') {
        showNotification(message, 'success');
    }
}

function showUpgradeModal(reason = 'words') {
    const modal = document.getElementById('upgradeModal');
    const text = document.getElementById('upgradeModalText');
    if (!modal || !text) return;
    const translationKey = reason === 'study_work_trial' ? 'upgrade_trial_message' : 'upgrade_words_message';
    text.textContent = typeof t === 'function' ? t(translationKey) : 'Выберите тариф, чтобы продолжить работу.';
    modal.classList.add('active');
    modal.setAttribute('aria-hidden', 'false');
}

function closeUpgradeModal() {
    const modal = document.getElementById('upgradeModal');
    if (!modal) return;
    modal.classList.remove('active');
    modal.setAttribute('aria-hidden', 'true');
}

function getToolErrorMessage(status, data, fallbackMessage = 'Не удалось обработать текст') {
    const detail = typeof data?.detail === 'string' ? data.detail : '';

    if (status === 400) return detail || 'Проверьте текст и параметры запроса.';
    if (status === 401) return 'Сессия истекла. Войдите в аккаунт снова.';
    if (status === 429) {
        return detail || 'Слишком много запросов. Подождите немного и попробуйте снова.';
    }
    if (status === 502 || status === 504) return 'Ошибка при обработке.';
    if (status === 500) return 'Ошибка при обработке.';
    return detail || fallbackMessage;
}

function showToolError(status, data, fallbackMessage) {
    const detail = getToolErrorMessage(status, data, fallbackMessage);
    let shortMessage = detail;
    const hasNoWords = status === 429 && detail.startsWith('Недостаточно слов');
    const studyWorkTrialUsed = status === 403 && detail.includes('Бесплатное использование «Учебной работы» уже использовано');

    if (hasNoWords) {
        shortMessage = 'Недостаточно слов для этого запроса';
    } else if (status === 429) {
        shortMessage = 'Нужно немного подождать перед следующим запросом';
    } else if (status === 502 || status === 504) {
        shortMessage = 'Ошибка при обработке';
    } else if (status === 500) {
        shortMessage = 'Ошибка при обработке';
    }

    if (typeof showNotification === 'function') {
        showNotification(shortMessage, status === 400 || status === 429 ? 'warning' : 'error', 7000);
    }
    if (hasNoWords) showUpgradeModal('words');
    if (studyWorkTrialUsed) showUpgradeModal('study_work_trial');
    return detail;
}

function showToolNetworkError() {
    const message = 'Ошибка при обработке.';
    if (typeof showNotification === 'function') {
        showNotification('Ошибка при обработке', 'error', 7000);
    }
    return message;
}

document.addEventListener('DOMContentLoaded', () => {
    const modal = document.getElementById('upgradeModal');
    document.querySelectorAll('[data-upgrade-close]').forEach(button => {
        button.addEventListener('click', closeUpgradeModal);
    });
    modal?.addEventListener('click', event => {
        if (event.target === modal) closeUpgradeModal();
    });
});

function isAboveMinWords(text) {
    return countWords(text) >= currentMinWords;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showWarning(message, isError = false) {
    const el = document.getElementById('wordWarning');
    if (el) {
        el.textContent = message;
        el.style.color = isError ? '#ef4444' : '#f59e0b';
    }
}

function clearWarning() {
    const el = document.getElementById('wordWarning');
    if (el) el.textContent = '';
}

function updateMaxWordsFromSubscription(subscription) {
    const maxWords = Number(subscription?.max_words_per_request);
    currentMaxWords = Number.isFinite(maxWords) && maxWords > 0
        ? maxWords
        : DEFAULT_MAX_WORDS;
    window.currentMaxWords = currentMaxWords;
    window.dispatchEvent(new CustomEvent('wordLimitUpdated', {
        detail: { maxWords: currentMaxWords }
    }));
    updateWordCounter();

    const result = document.getElementById('result');
    if (result) {
        const resultText = 'value' in result ? result.value : result.textContent;
        updateResultWordCounter(resultText || '');
    }
}

function updateWordCounter() {
    const input = window.elements?.input;
    if (!input) return;

    const span = document.getElementById('wordCount');
    if (!span) return;

    const warning = document.getElementById('wordWarning');
    const isAuthenticated = typeof Auth !== 'undefined' && Auth.isAuthenticated();
    span.hidden = !isAuthenticated;
    if (warning) warning.hidden = !isAuthenticated;
    if (!isAuthenticated) return;

    const current = countWords(input.value);

    span.textContent = `${current}/${currentMaxWords} слов`;

    if (current > currentMaxWords) {
        span.style.color = '#ef4444';
        span.style.fontWeight = 'bold';
    } else if (current > currentMaxWords * 0.9) {
        span.style.color = '#f59e0b';
        span.style.fontWeight = 'bold';
    } else {
        span.style.color = '#c4c4c4';
        span.style.fontWeight = 'bold';
    }
}

function takeHistoryRestore(toolType) {
    try {
        const raw = sessionStorage.getItem('history_restore');
        if (!raw) return null;

        const payload = JSON.parse(raw);
        if (payload.toolType !== toolType) return null;

        sessionStorage.removeItem('history_restore');
        return payload;
    } catch {
        sessionStorage.removeItem('history_restore');
        return null;
    }
}

function setCustomSelectValue(hiddenInputId, value) {
    const hiddenInput = document.getElementById(hiddenInputId);
    const select = hiddenInput?.previousElementSibling;
    if (!hiddenInput || !select?.classList.contains('custom-select')) return false;

    const option = Array.from(select.querySelectorAll('.custom-select-option'))
        .find(item => item.dataset.value === value);
    if (!option) return false;

    hiddenInput.value = value;
    select.dataset.value = value;
    select.querySelector('.custom-select-label').textContent = option.textContent;
    select.querySelectorAll('.custom-select-option').forEach(item => {
        item.classList.toggle('selected', item === option);
    });
    return true;
}

const historyToolPaths = {
    humanizer: '/humanize',
    detector: '/detector',
    paraphraser: '/paraphraser',
    study_work: '/study-work',
};
const historyRestoreRequests = new Map();

function getHistoryIdFromToolUrl(toolType) {
    const toolPath = historyToolPaths[toolType];
    const pathname = window.location.pathname.replace(/\/+$/, '');
    if (!toolPath || !pathname.startsWith(`${toolPath}/`)) return null;

    const id = pathname.slice(toolPath.length + 1);
    return /^\d+$/.test(id) ? id : null;
}

async function takeHistoryRestoreFromUrl(toolType) {
    const historyId = getHistoryIdFromToolUrl(toolType);
    if (!historyId || typeof Auth === 'undefined') return null;

    const requestKey = `${toolType}:${historyId}`;
    if (!historyRestoreRequests.has(requestKey)) {
        historyRestoreRequests.set(requestKey, (async () => {
            try {
                const response = await Auth.authorizedFetch(`/user/history/${encodeURIComponent(historyId)}`);
                const data = await response.json();
                const item = data?.history;
                if (!response.ok || !data?.success || !item || item.tool_type !== toolType) return null;

                return {
                    toolType,
                    original: String(item.original_text || ''),
                    result: String(item.result_text || ''),
                    processingOptions: item.processing_options && typeof item.processing_options === 'object'
                        ? item.processing_options
                        : {},
                    hasProcessedDocx: Boolean(item.has_processed_docx),
                    processedDocxFilename: String(item.processed_docx_filename || ''),
                };
            } catch {
                return null;
            }
        })());
    }

    return historyRestoreRequests.get(requestKey);
}

async function getHistoryRestore(toolType) {
    return takeHistoryRestore(toolType) || takeHistoryRestoreFromUrl(toolType);
}

async function redirectToSavedHistory(toolType, original, result, processingOptions = {}) {
    const toolPath = historyToolPaths[toolType];
    if (!toolPath || typeof API === 'undefined') return false;
    try {
        const saved = await API.saveHistory(toolType, original, result, processingOptions);
        const historyId = saved?.data?.history_id;
        if (!saved?.ok || !saved?.data?.success || !historyId) {
            throw new Error('history_save_failed');
        }

        clearCachedUserData('history:');
        window.location.assign(`${toolPath}/${encodeURIComponent(historyId)}`);
        return true;
    } catch {
        showNotification('Не удалось сохранить результат в историю.', 'error');
        return false;
    }
}

function updateResultWordCounter(text) {
    const span = document.getElementById('resultWordCount');
    if (!span) return;

    const current = countWords(text);
    span.textContent = `${current}/${currentMaxWords} слов`;

    if (current > currentMaxWords) {
        span.style.color = '#ef4444';
        span.style.fontWeight = 'bold';
    } else if (current > currentMaxWords * 0.9) {
        span.style.color = '#f59e0b';
        span.style.fontWeight = 'bold';
    } else {
        span.style.color = '#c4c4c4';
        span.style.fontWeight = 'bold';
    }
}

async function copyTextToClipboard(text) {
    if (!text) return false;

    try {
        if (navigator.clipboard?.writeText) {
            await navigator.clipboard.writeText(text);
            return true;
        }
    } catch {
        // Clipboard API is unavailable on HTTP connections and on some mobile
        // browsers. Fall back to a copy operation initiated by the click.
    }

    const selection = document.getSelection();
    const activeElement = document.activeElement;
    const fallback = document.createElement('textarea');
    fallback.value = text;
    fallback.setAttribute('readonly', '');
    fallback.setAttribute('aria-hidden', 'true');
    fallback.style.cssText = 'position:fixed;top:0;left:-9999px;width:1px;height:1px;padding:0;border:0;opacity:0;';
    document.body.append(fallback);

    try {
        fallback.focus({ preventScroll: true });
        fallback.select();
        fallback.setSelectionRange(0, fallback.value.length);
        return document.execCommand('copy');
    } catch {
        return false;
    } finally {
        fallback.remove();
        if (selection) selection.removeAllRanges();
        try { activeElement?.focus?.({ preventScroll: true }); } catch { /* no focus restore needed */ }
    }
}

window.copyTextToClipboard = copyTextToClipboard;

async function copyButtonText(btn, getText) {
    const text = getText();
    if (!text || !text.trim()) {
        showNotification('Нет текста для копирования', 'warning');
        return;
    }
    try {
        const copied = await copyTextToClipboard(text);
        if (!copied) throw new Error('clipboard_copy_failed');
        if (btn) {
            if (!btn.hasAttribute('data-original-html')) {
                btn.setAttribute('data-original-html', btn.innerHTML);
            }
            const original = btn.getAttribute('data-original-html');
            btn.innerHTML = '<i class="fas fa-check"></i>';
            setTimeout(() => { btn.innerHTML = original; }, 1500);
        }
        showNotification('Скопировано', 'success');
    } catch {
        showNotification('Не удалось скопировать текст', 'error');
    }
}

async function pasteFromClipboard() {
    const textarea = document.getElementById('input');
    const pasteBtn = document.getElementById('pasteBtn');
    if (!navigator.clipboard?.readText) {
        textarea?.focus();
        showNotification('Нажмите на поле и выберите «Вставить» в меню телефона.', 'warning');
        return;
    }
    try {
        const text = await navigator.clipboard.readText();
        if (text) {
            textarea.value = text;
            textarea.dispatchEvent(new Event('input', { bubbles: true }));
            if (pasteBtn) pasteBtn.style.display = 'none';
        } else {
            showNotification('Буфер обмена пуст', 'warning');
        }
    } catch {
        showNotification('Не удалось получить доступ к буферу обмена', 'error');
    }
}

function initPdfUpload() {
    const pdfBtn = document.getElementById('pdfBtn');
    const pdfFileInput = document.getElementById('pdfFileInput');
    if (!pdfBtn || !pdfFileInput) return;

    const newPdfBtn = pdfBtn.cloneNode(true);
    pdfBtn.parentNode.replaceChild(newPdfBtn, pdfBtn);

    newPdfBtn.addEventListener('pointerdown', () => {
        void loadPdfJs().catch(() => {});
    }, { passive: true });
    newPdfBtn.addEventListener('click', () => pdfFileInput.click());

    pdfFileInput.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        if (file.size > MAX_UPLOAD_FILE_SIZE_BYTES) {
            showNotification(`PDF больше ${MAX_UPLOAD_FILE_SIZE_LABEL}. Выберите файл меньшего размера.`, 'warning');
            pdfFileInput.value = '';
            return;
        }

        newPdfBtn.disabled = true;
        newPdfBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Загрузка...';

        try {
            const pdfjs = await loadPdfJs();
            const arrayBuffer = await file.arrayBuffer();
            const pdf = await pdfjs.getDocument({ data: arrayBuffer }).promise;
            let fullText = '';

            for (let i = 1; i <= pdf.numPages; i++) {
                const page = await pdf.getPage(i);
                const textContent = await page.getTextContent();
                let lastY = null;
                let pageText = '';

                for (const item of textContent.items) {
                    if (lastY !== null && Math.abs(item.transform[5] - lastY) > 5) pageText += '\n';
                    if (pageText && !pageText.endsWith('\n') && !pageText.endsWith(' ') && item.str && !item.str.startsWith(' ')) pageText += ' ';
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

function initWordUpload() {
    const wordBtn = document.getElementById('wordBtn');
    const wordFileInput = document.getElementById('wordFileInput');
    const input = document.getElementById('input');
    if (!wordBtn || !wordFileInput || !input) return;

    const newWordBtn = wordBtn.cloneNode(true);
    wordBtn.parentNode.replaceChild(newWordBtn, wordBtn);
    const uploadLabel = () => (typeof t === 'function' ? t('upload_word') : 'Загрузить Word');

    newWordBtn.addEventListener('pointerdown', () => {
        void loadMammoth().catch(() => {});
    }, { passive: true });
    newWordBtn.addEventListener('click', () => wordFileInput.click());
    wordFileInput.addEventListener('change', async event => {
        const file = event.target.files?.[0];
        if (!file) return;
        if (!file.name.toLowerCase().endsWith('.docx')) {
            showNotification('Выберите файл Word в формате .docx', 'warning');
            wordFileInput.value = '';
            return;
        }
        if (file.size > MAX_UPLOAD_FILE_SIZE_BYTES) {
            showNotification(`Файл Word больше ${MAX_UPLOAD_FILE_SIZE_LABEL}. Выберите файл меньшего размера.`, 'warning');
            wordFileInput.value = '';
            return;
        }
        newWordBtn.disabled = true;
        newWordBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Загрузка...';
        try {
            const mammoth = await loadMammoth();
            const result = await mammoth.extractRawText({ arrayBuffer: await file.arrayBuffer() });
            const text = result.value.trim();
            if (!text) {
                showNotification('В документе Word не найден текст', 'warning');
                return;
            }
            input.value = text;
            input.dispatchEvent(new Event('input', { bubbles: true }));
            showNotification('Текст из Word успешно загружен', 'success');
        } catch {
            showNotification('Не удалось прочитать файл Word', 'error');
        } finally {
            newWordBtn.disabled = false;
            newWordBtn.innerHTML = `<i class="fas fa-file-word"></i> ${uploadLabel()}`;
            wordFileInput.value = '';
        }
    });
}

window.pasteFromClipboard = pasteFromClipboard;
window.initPdfUpload = initPdfUpload;
window.initWordUpload = initWordUpload;
window.loadPdfJs = loadPdfJs;
window.loadMammoth = loadMammoth;
window.DEFAULT_MAX_WORDS = DEFAULT_MAX_WORDS;
window.DEFAULT_MIN_WORDS = DEFAULT_MIN_WORDS;
window.MAX_UPLOAD_FILE_SIZE_BYTES = MAX_UPLOAD_FILE_SIZE_BYTES;
window.MAX_UPLOAD_FILE_SIZE_LABEL = MAX_UPLOAD_FILE_SIZE_LABEL;
window.currentMaxWords = currentMaxWords;
window.currentMinWords = currentMinWords;
window.countWords = countWords;
window.getCachedUserData = getCachedUserData;
window.setCachedUserData = setCachedUserData;
window.clearCachedUserData = clearCachedUserData;
window.takeHistoryRestore = takeHistoryRestore;
window.isWithinWordLimit = isWithinWordLimit;
window.getRequestLimitMessage = getRequestLimitMessage;
window.showRequestLimitError = showRequestLimitError;
window.showEmptyTextError = showEmptyTextError;
window.startTextProcessing = startTextProcessing;
window.finishTextProcessing = finishTextProcessing;
window.showToolSuccess = showToolSuccess;
window.getToolErrorMessage = getToolErrorMessage;
window.showToolError = showToolError;
window.showToolNetworkError = showToolNetworkError;
window.showUpgradeModal = showUpgradeModal;
window.closeUpgradeModal = closeUpgradeModal;
window.isAboveMinWords = isAboveMinWords;
window.escapeHtml = escapeHtml;
window.showWarning = showWarning;
window.clearWarning = clearWarning;
window.updateMaxWordsFromSubscription = updateMaxWordsFromSubscription;
window.updateWordCounter = updateWordCounter;
window.updateResultWordCounter = updateResultWordCounter;
window.copyButtonText = copyButtonText;
