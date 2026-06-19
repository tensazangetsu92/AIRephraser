const DEFAULT_MAX_WORDS = 1000;
const DEFAULT_MIN_WORDS = 50;

let currentMaxWords = DEFAULT_MAX_WORDS;
let currentMinWords = DEFAULT_MIN_WORDS;

function countWords(text) {
    if (!text || !text.trim()) return 0;
    return text.trim().split(/\s+/).length;
}

function isWithinWordLimit(text) {
    return countWords(text) <= currentMaxWords;
}

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
    currentMaxWords = subscription?.max_words || DEFAULT_MAX_WORDS;
    window.currentMaxWords = currentMaxWords;
    updateWordCounter();
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
        span.style.fontWeight = 'normal';
    } else {
        span.style.color = '#c4c4c4';
        span.style.fontWeight = current < currentMinWords ? 'bold' : 'normal';
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

window.pasteFromClipboard = pasteFromClipboard;
window.initPdfUpload = initPdfUpload;
window.DEFAULT_MAX_WORDS = DEFAULT_MAX_WORDS;
window.DEFAULT_MIN_WORDS = DEFAULT_MIN_WORDS;
window.currentMaxWords = currentMaxWords;
window.currentMinWords = currentMinWords;
window.countWords = countWords;
window.isWithinWordLimit = isWithinWordLimit;
window.isAboveMinWords = isAboveMinWords;
window.escapeHtml = escapeHtml;
window.showWarning = showWarning;
window.clearWarning = clearWarning;
window.updateMaxWordsFromSubscription = updateMaxWordsFromSubscription;
window.updateWordCounter = updateWordCounter;
window.copyButtonText = copyButtonText;