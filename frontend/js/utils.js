const DEFAULT_MAX_WORDS = 500;
const DEFAULT_MIN_WORDS = 50;

let currentMaxWords = DEFAULT_MAX_WORDS;
let currentMinWords = DEFAULT_MIN_WORDS;
let textProcessingInProgress = false;

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
    },
    grammar: {
        loading: 'Проверяем грамматику. Это может занять до минуты.',
        success: 'Проверка грамматики завершена'
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
    if (status === 502) return 'Нейросеть временно недоступна. Попробуйте немного позже.';
    if (status === 504) return 'Обработка заняла слишком много времени. Попробуйте ещё раз или сократите текст.';
    if (status === 500) return 'Сервис временно недоступен из-за ошибки базы данных. Попробуйте позже.';
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
        shortMessage = 'Нейросеть временно недоступна';
    } else if (status === 500) {
        shortMessage = 'Сервис временно недоступен';
    }

    if (typeof showNotification === 'function') {
        showNotification(shortMessage, status === 400 || status === 429 ? 'warning' : 'error', 7000);
    }
    if (hasNoWords) showUpgradeModal('words');
    if (studyWorkTrialUsed) showUpgradeModal('study_work_trial');
    return detail;
}

function showToolNetworkError() {
    const message = 'Нет соединения с сервером. Проверьте интернет и попробуйте ещё раз.';
    if (typeof showNotification === 'function') {
        showNotification('Не удалось связаться с сервером', 'error', 7000);
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

    const current = countWords(input.value);
    const span = document.getElementById('wordCount');
    if (!span) return;

    span.textContent = `${current}/${currentMaxWords}`;

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

function updateResultWordCounter(text) {
    const span = document.getElementById('resultWordCount');
    if (!span) return;

    const current = countWords(text);
    span.textContent = `${current}/${currentMaxWords}`;

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

async function copyButtonText(btn, getText) {
    const text = getText();
    if (!text || !text.trim()) {
        showNotification('Нет текста для копирования', 'warning');
        return;
    }
    try {
        await navigator.clipboard.writeText(text);
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

    newWordBtn.addEventListener('click', () => wordFileInput.click());
    wordFileInput.addEventListener('change', async event => {
        const file = event.target.files?.[0];
        if (!file) return;
        if (!file.name.toLowerCase().endsWith('.docx')) {
            showNotification('Выберите файл Word в формате .docx', 'warning');
            wordFileInput.value = '';
            return;
        }
        if (typeof mammoth === 'undefined') {
            showNotification('Не удалось загрузить модуль чтения Word. Обновите страницу и попробуйте снова.', 'error');
            return;
        }

        newWordBtn.disabled = true;
        newWordBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Загрузка...';
        try {
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
window.DEFAULT_MAX_WORDS = DEFAULT_MAX_WORDS;
window.DEFAULT_MIN_WORDS = DEFAULT_MIN_WORDS;
window.currentMaxWords = currentMaxWords;
window.currentMinWords = currentMinWords;
window.countWords = countWords;
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
