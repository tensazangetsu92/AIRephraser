(function () {
    let originalText = '';
    let sourceWordFile = null;
    let sourceWordText = '';
    let processedWordBlob = null;
    let processedWordFilename = 'humary-учебная-работа.docx';
    let hasStoredProcessedWord = false;
    const MAX_STUDY_WORK_FILE_SIZE_BYTES = window.MAX_UPLOAD_FILE_SIZE_BYTES || 10 * 1024 * 1024;
    const MAX_STUDY_WORK_FILE_SIZE_LABEL = window.MAX_UPLOAD_FILE_SIZE_LABEL || '10 МБ';
    const WORD_DOCUMENT_MIME = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
    const showStudyWorkError = message => showNotification(message, 'error');

    async function hasZipSignature(file) {
        const header = new Uint8Array(await file.slice(0, 4).arrayBuffer());
        return header.length >= 2 && header[0] === 0x50 && header[1] === 0x4b;
    }

    async function hasPdfSignature(file) {
        const header = new Uint8Array(await file.slice(0, 1024).arrayBuffer());
        const signature = [0x25, 0x50, 0x44, 0x46, 0x2d]; // %PDF-
        for (let offset = 0; offset <= header.length - signature.length; offset += 1) {
            if (signature.every((byte, index) => header[offset + index] === byte)) return true;
        }
        return false;
    }

    function setStudyWorkProcessingError(isVisible) {
        const badge = document.getElementById('studyWorkProcessingError');
        if (badge) badge.hidden = !isVisible;
    }

    function setStudyWorkResultVisible(isVisible) {
        const result = document.getElementById('studyWorkResult');
        if (!result) return;
        result.hidden = !isVisible;
        document.querySelector('.study-work-editor')?.classList.toggle('single-col', !isVisible);
    }

    function setStudyWorkNewCheckButtonVisible(isVisible) {
        const button = document.getElementById('studyWorkNewCheckBtn');
        if (button) button.style.display = isVisible ? 'inline-flex' : 'none';
    }

    function getStudyWorkMaxWords() {
        return window.currentStudyWorkMaxWords || 5000;
    }

    function updateStudyWorkResultCounter(text) {
        const counter = document.getElementById('studyWorkResultCounter');
        if (!counter) return;
        counter.textContent = `${countWords(text)}/${getStudyWorkMaxWords()} ${typeof t === 'function' ? t('words') : 'слов'}`;
    }

    function isWithinStudyWorkLimit(text) {
        return countWords(text) <= getStudyWorkMaxWords();
    }

    function getStudyWorkLimitMessage(text) {
        const current = countWords(text);
        const maxWords = getStudyWorkMaxWords();
        return `Превышен лимит слов за один запрос. Максимум: ${maxWords}. Сейчас: ${current}. Сократите текст на ${current - maxWords} слов.`;
    }

    function renderStudyWorkResult(editedText) {
        const output = document.getElementById('studyWorkEdited');
        if (!output) return;
        // The result is text, not HTML. textContent prevents a document name,
        // pasted text or a provider response from creating DOM elements.
        // .study-work-text uses white-space: pre-wrap, so paragraph breaks are
        // still rendered exactly as they arrived from the processed document.
        output.textContent = String(editedText);
        updateStudyWorkResultCounter(editedText);
    }

    async function restoreHistoryWork() {
        const historyRestore = typeof getHistoryRestore === 'function'
            ? await getHistoryRestore('study_work')
            : null;
        if (!historyRestore) return;

        const input = document.getElementById('studyWorkInput');
        const result = document.getElementById('studyWorkResult');
        if (!input || !result) return;

        originalText = historyRestore.original || '';
        hasStoredProcessedWord = Boolean(historyRestore.hasProcessedDocx);
        processedWordFilename = historyRestore.processedDocxFilename || processedWordFilename;
        input.value = originalText;
        renderStudyWorkResult(historyRestore.result || '');
        setStudyWorkResultVisible(true);
        setStudyWorkNewCheckButtonVisible(Boolean(historyRestore.result?.trim()));
        updateCounter();
    }

    async function importWordFile(file) {
        const input = document.getElementById('studyWorkInput');
        const button = document.getElementById('studyWorkWordUpload');
        if (!file || !input || !button) return;
        if (!file.name.toLowerCase().endsWith('.docx')) {
            showStudyWorkError('Выберите файл Word в формате .docx.');
            return;
        }
        if (file.size > MAX_STUDY_WORK_FILE_SIZE_BYTES) {
            showStudyWorkError(`Файл больше ${MAX_STUDY_WORK_FILE_SIZE_LABEL}. Выберите документ меньшего размера.`);
            return;
        }
        if (!await hasZipSignature(file)) {
            showStudyWorkError('Файл не является корректным документом Word .docx.');
            return;
        }
        button.disabled = true;
        button.innerHTML = '<span class="loading"></span> Читаем документ...';
        try {
            const mammoth = await window.loadMammoth();
            const result = await mammoth.extractRawText({ arrayBuffer: await file.arrayBuffer() });
            const text = result.value.trim();
            if (!text) {
                showStudyWorkError('В документе не найден текст.');
                return;
            }
            input.value = text;
            input.readOnly = true;
            sourceWordFile = file;
            sourceWordText = text;
            processedWordBlob = null;
            processedWordFilename = `humary-${file.name}`;
            const wordNote = document.getElementById('studyWorkWordNote');
            if (wordNote) {
                const icon = document.createElement('i');
                icon.className = 'fa-solid fa-file-word';
                wordNote.replaceChildren(icon, document.createTextNode(file.name));
                wordNote.hidden = false;
            }
            input.dispatchEvent(new Event('input', { bubbles: true }));
            showNotification('Текст из Word загружен', 'success');
        } catch {
            showStudyWorkError('Не удалось прочитать файл Word. Проверьте, что это корректный .docx документ.');
        } finally {
            button.disabled = false;
            button.innerHTML = '<i class="fa-solid fa-file-word"></i> Загрузить Word';
            document.getElementById('studyWorkWordFile').value = '';
        }
    }

    async function pasteStudyWorkText() {
        const input = document.getElementById('studyWorkInput');
        if (!input || input.readOnly) {
            showStudyWorkError('Чтобы изменить текст, сначала загрузите новый документ Word или обновите страницу.');
            return;
        }
        if (!navigator.clipboard?.readText) {
            input.focus();
            showNotification('Нажмите на поле и выберите «Вставить» в меню телефона.', 'warning');
            return;
        }
        try {
            const text = await navigator.clipboard.readText();
            if (!text.trim()) throw new Error('Буфер обмена пуст.');
            input.value = text;
            input.dispatchEvent(new Event('input', { bubbles: true }));
        } catch (error) {
            const message = error?.message || 'Не удалось вставить текст из буфера обмена.';
            showNotification(message, 'error');
        }
    }

    async function importPdfFile(file) {
        const input = document.getElementById('studyWorkInput');
        const button = document.getElementById('studyWorkPdfBtn');
        const fileInput = document.getElementById('studyWorkPdfFile');
        if (!file || !input || !button) return;
        if (input.readOnly) {
            showStudyWorkError('Чтобы загрузить PDF, сначала загрузите новый документ Word или обновите страницу.');
            return;
        }
        if (!file.name.toLowerCase().endsWith('.pdf')) {
            showStudyWorkError('Выберите файл в формате PDF.');
            return;
        }
        if (file.size > MAX_STUDY_WORK_FILE_SIZE_BYTES) {
            showStudyWorkError(`Файл больше ${MAX_STUDY_WORK_FILE_SIZE_LABEL}. Выберите PDF меньшего размера.`);
            return;
        }
        if (!await hasPdfSignature(file)) {
            showStudyWorkError('Файл не является корректным PDF-документом.');
            return;
        }

        button.disabled = true;
        button.innerHTML = '<span class="loading"></span> Читаем PDF...';
        try {
            const pdfjs = await window.loadPdfJs();
            const pdf = await pdfjs.getDocument({ data: await file.arrayBuffer() }).promise;
            const pages = [];
            for (let pageNumber = 1; pageNumber <= pdf.numPages; pageNumber += 1) {
                const page = await pdf.getPage(pageNumber);
                const content = await page.getTextContent();
                pages.push(content.items.map(item => item.str).join(' '));
            }
            const text = pages.join('\n\n').trim();
            if (!text) throw new Error('В PDF не найден текст. Возможно, это скан без распознанного текста.');
            input.value = text;
            input.dispatchEvent(new Event('input', { bubbles: true }));
            showNotification('Текст из PDF загружен', 'success');
        } catch (error) {
            const message = error?.message || 'Не удалось прочитать PDF-файл.';
            showNotification(message, 'error');
        } finally {
            button.disabled = false;
            button.innerHTML = '<i class="fas fa-file-pdf"></i><span>Загрузить PDF</span>';
            if (fileInput) fileInput.value = '';
        }
    }

    function updateCounter() {
        const input = document.getElementById('studyWorkInput');
        const counter = document.getElementById('studyWorkCounter');
        if (!input || !counter) return;
        const isAuthenticated = typeof Auth !== 'undefined' && Auth.isAuthenticated();
        counter.hidden = !isAuthenticated;
        if (!isAuthenticated) return;
        const current = countWords(input.value);
        const maxWords = getStudyWorkMaxWords();
        counter.textContent = `${current}/${maxWords} ${typeof t === 'function' ? t('words') : 'слов'}`;
        counter.classList.toggle('is-over-limit', current > maxWords);
        updateStudyWorkResultCounter(document.getElementById('studyWorkEdited')?.innerText || '');
    }

    async function processWordDocument(workType) {
        const formData = new FormData();
        formData.append('file', sourceWordFile);
        formData.append('work_type', workType);
        const response = await Auth.authorizedFetch('/study-work/docx/process', {
            method: 'POST',
            headers: { Authorization: `Bearer ${Auth.getToken()}` },
            body: formData,
        });
        if (!response.ok) {
            let detail = 'Не удалось обработать документ Word.';
            try { detail = (await response.json()).detail || detail; } catch (_) { /* non-JSON response */ }
            const error = new Error(detail);
            error.status = response.status;
            throw error;
        }
        const historyId = Number(response.headers.get('X-History-Id')) || null;
        processedWordBlob = await response.blob();
        const mammoth = await window.loadMammoth();
        const result = await mammoth.extractRawText({ arrayBuffer: await processedWordBlob.arrayBuffer() });
        if (!result.value.trim()) throw new Error('В обработанном документе не найден текст.');
        return { text: result.value.trim(), historyId };
    }

    function getStudyWorkHistoryId() {
        const match = window.location.pathname.match(/^\/study-work\/(\d+)\/?$/);
        return match ? Number(match[1]) : null;
    }

    function isIOSDevice() {
        const platform = navigator.platform || '';
        return /iPad|iPhone|iPod/i.test(navigator.userAgent)
            || (platform === 'MacIntel' && navigator.maxTouchPoints > 1);
    }

    function openIOSDownloadWindow() {
        if (!isIOSDevice()) return null;
        const downloadWindow = window.open('', '_blank');
        if (downloadWindow) {
            try { downloadWindow.opener = null; } catch { /* opener may be protected by the browser */ }
        }
        return downloadWindow;
    }

    async function downloadWordBlob(blob, filename, iosDownloadWindow = null) {
        if (isIOSDevice()) {
            const file = typeof File === 'function'
                ? new File([blob], filename, { type: blob.type || WORD_DOCUMENT_MIME })
                : null;
            let canUseShareSheet = !iosDownloadWindow && Boolean(file) && typeof navigator.share === 'function';
            if (canUseShareSheet && navigator.canShare) {
                try { canUseShareSheet = navigator.canShare({ files: [file] }); } catch { canUseShareSheet = false; }
            }

            if (canUseShareSheet) {
                try {
                    await navigator.share({ files: [file], title: filename });
                    return;
                } catch (error) {
                    if (error?.name === 'AbortError') return;
                    // A share sheet may be unavailable in an embedded browser.
                }
            }

            const objectUrl = URL.createObjectURL(blob);
            const target = iosDownloadWindow || window.open('', '_blank');
            if (target) {
                target.location.href = objectUrl;
            } else {
                window.location.href = objectUrl;
            }
            window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
            return;
        }

        const link = Object.assign(document.createElement('a'), {
            href: URL.createObjectURL(blob),
            download: filename,
        });
        document.body.append(link);
        link.click();
        link.remove();
        window.setTimeout(() => URL.revokeObjectURL(link.href), 1_000);
    }

    async function downloadEditedWordFile() {
        if (processedWordBlob) {
            await downloadWordBlob(processedWordBlob, processedWordFilename);
            return;
        }

        const iosDownloadWindow = openIOSDownloadWindow();
        const historyId = getStudyWorkHistoryId();
        try {
            if (hasStoredProcessedWord && historyId) {
                const response = await Auth.authorizedFetch(`/study-work/history/${historyId}/docx/download`);
                if (!response.ok) {
                    let detail = 'Не удалось скачать исходный Word-файл.';
                    try { detail = (await response.json()).detail || detail; } catch (_) { /* non-JSON response */ }
                    throw new Error(detail);
                }
                await downloadWordBlob(await response.blob(), processedWordFilename, iosDownloadWindow);
                return;
            }

            const text = document.getElementById('studyWorkEdited')?.innerText || '';
            if (!text.trim()) {
                if (iosDownloadWindow && !iosDownloadWindow.closed) iosDownloadWindow.close();
                return;
            }
            const response = await Auth.authorizedFetch('/study-work/docx/download', {
                method: 'POST',
                headers: {
                    Authorization: `Bearer ${Auth.getToken()}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ text }),
            });
            if (!response.ok) {
                let detail = 'Не удалось подготовить Word-файл.';
                try { detail = (await response.json()).detail || detail; } catch (_) { /* non-JSON response */ }
                throw new Error(detail);
            }
            await downloadWordBlob(await response.blob(), processedWordFilename, iosDownloadWindow);
        } catch (error) {
            if (iosDownloadWindow && !iosDownloadWindow.closed) iosDownloadWindow.close();
            throw error;
        }
    }

    async function submit() {
        const input = document.getElementById('studyWorkInput');
        const button = document.getElementById('studyWorkSubmit');
        const submitButtonMarkup = button?.innerHTML;
        const text = input?.value.trim() || '';
        if (!text) { showStudyWorkError('Вставьте текст для подготовки.'); input?.focus(); return; }
        if (!Auth.isAuthenticated()) { Auth.showAuthModal(); return; }
        if (!isWithinStudyWorkLimit(text)) { showStudyWorkError(getStudyWorkLimitMessage(text)); return; }
        if (sourceWordFile && text !== sourceWordText) {
            showStudyWorkError('Текст Word был изменён в поле ввода. Загрузите документ заново, чтобы сохранить его структуру.');
            return;
        }
        if (!startTextProcessing('humanize')) return;
        setStudyWorkProcessingError(false);

        const workType = document.querySelector('input[name="workType"]:checked')?.value || 'other';
        const trialWasAvailable = document.getElementById('studyWorkTrialBadge')?.hidden === false;
        button.disabled = true;
        button.innerHTML = '<span class="loading"></span> Обработка';
        setStudyWorkNewCheckButtonVisible(false);
        try {
            let editedText;
            let wordHistoryId = null;
            if (sourceWordFile) {
                const processedWord = await processWordDocument(workType);
                editedText = processedWord.text;
                wordHistoryId = processedWord.historyId;
            } else {
                const { ok, status, data } = await API.prepareStudyWork(text, workType);
                if (!ok) throw { status, data };
                editedText = data.result || '';
            }
            originalText = text;
            if (trialWasAvailable && typeof window.markStudyWorkTrialUsed === 'function') {
                window.markStudyWorkTrialUsed();
            }
            if (typeof refreshAllSubscriptionData === 'function') await refreshAllSubscriptionData(true);
            if (wordHistoryId) {
                if (typeof window.clearCachedUserData === 'function') window.clearCachedUserData('history:');
                window.location.assign(`/study-work/${encodeURIComponent(wordHistoryId)}`);
                return;
            }
            if (await redirectToSavedHistory('study_work', text, editedText)) return;

            renderStudyWorkResult(editedText);
            setStudyWorkResultVisible(true);
            setStudyWorkNewCheckButtonVisible(true);
            showToolSuccess('humanize');
        } catch (error) {
            setStudyWorkProcessingError(true);
            if (error instanceof Error) {
                if (error.status) showToolError(error.status, { detail: error.message }, 'Не удалось подготовить документ Word.');
                else showNotification(error.message, 'error');
            } else {
                if (error?.status) showToolError(error.status, error.data, 'Не удалось подготовить текст.');
                else showToolNetworkError();
            }
        } finally {
            button.disabled = false;
            button.innerHTML = submitButtonMarkup;
            finishTextProcessing();
        }
    }

    document.addEventListener('DOMContentLoaded', () => {
        const input = document.getElementById('studyWorkInput');
        input?.addEventListener('input', updateCounter);
        restoreHistoryWork();
        updateCounter();
        window.addEventListener('studyWorkLimitUpdated', updateCounter);
        window.addEventListener('authStateChanged', updateCounter);
        document.getElementById('studyWorkWordUpload')?.addEventListener('pointerdown', () => {
            void window.loadMammoth().catch(() => {});
        }, { passive: true });
        document.getElementById('studyWorkWordUpload')?.addEventListener('click', () => document.getElementById('studyWorkWordFile')?.click());
        document.getElementById('studyWorkWordFile')?.addEventListener('change', event => importWordFile(event.target.files?.[0]));
        document.getElementById('studyWorkPasteBtn')?.addEventListener('click', pasteStudyWorkText);
        document.getElementById('studyWorkPdfBtn')?.addEventListener('pointerdown', () => {
            void window.loadPdfJs().catch(() => {});
        }, { passive: true });
        document.getElementById('studyWorkPdfBtn')?.addEventListener('click', () => document.getElementById('studyWorkPdfFile')?.click());
        document.getElementById('studyWorkPdfFile')?.addEventListener('change', event => importPdfFile(event.target.files?.[0]));
        document.getElementById('studyWorkCopyInput')?.addEventListener('click', () => {
            copyButtonText(document.getElementById('studyWorkCopyInput'), () => document.getElementById('studyWorkInput')?.value || '');
        });
        document.getElementById('studyWorkSubmit')?.addEventListener('click', submit);
        document.getElementById('studyWorkNewCheckBtn')?.addEventListener('click', () => {
            originalText = '';
            sourceWordFile = null;
            sourceWordText = '';
            processedWordBlob = null;
            processedWordFilename = 'humary-учебная-работа.docx';
            hasStoredProcessedWord = false;
            setStudyWorkProcessingError(false);
            const input = document.getElementById('studyWorkInput');
            if (input) {
                input.value = '';
                input.readOnly = false;
            }
            const wordNote = document.getElementById('studyWorkWordNote');
            if (wordNote) {
                wordNote.textContent = '';
                wordNote.hidden = true;
            }
            const wordFileInput = document.getElementById('studyWorkWordFile');
            if (wordFileInput) wordFileInput.value = '';
            const result = document.getElementById('studyWorkEdited');
            if (result) result.textContent = '';
            setStudyWorkResultVisible(false);
            setStudyWorkNewCheckButtonVisible(false);
            updateCounter();
            input?.focus();
        });
        document.getElementById('studyWorkCopy')?.addEventListener('click', () => copyButtonText(document.getElementById('studyWorkCopy'), () => document.getElementById('studyWorkEdited').innerText));
        document.getElementById('studyWorkDownload')?.addEventListener('click', () => {
            downloadEditedWordFile().catch(error => showStudyWorkError(error.message || 'Не удалось подготовить Word-файл.'));
        });
        updateCounter();
    });
})();
