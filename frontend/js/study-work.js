(function () {
    const escapeHtml = text => String(text).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    let originalText = '';
    let sourceWordFile = null;
    let sourceWordText = '';
    let processedWordBlob = null;
    const showStudyWorkError = message => showNotification(message, 'error');

    function getStudyWorkMaxWords() {
        return window.currentStudyWorkMaxWords || 5000;
    }

    function isWithinStudyWorkLimit(text) {
        return countWords(text) <= getStudyWorkMaxWords();
    }

    function getStudyWorkLimitMessage(text) {
        const current = countWords(text);
        const maxWords = getStudyWorkMaxWords();
        return `Превышен лимит слов за один запрос. Максимум: ${maxWords}. Сейчас: ${current}. Сократите текст на ${current - maxWords} слов.`;
    }

    function selectedValues(selector) {
        return [...document.querySelectorAll(selector)].filter(input => input.checked).map(input => input.value);
    }

    function splitSentences(text) {
        return String(text).match(/[^.!?…]+(?:[.!?…]+|$)/g) || [String(text)];
    }

    function renderChangedSentences(original, editedText) {
        const originalSentences = new Set(splitSentences(original)
            .map(sentence => sentence.trim().replace(/\s+/g, ' ').toLowerCase())
            .filter(Boolean));
        const output = document.getElementById('studyWorkEdited');
        if (!output) return;
        output.innerHTML = splitSentences(editedText).map(sentence => {
            const normalized = sentence.trim().replace(/\s+/g, ' ').toLowerCase();
            const changed = normalized && !originalSentences.has(normalized);
            const content = escapeHtml(sentence);
            return changed ? `<span class="study-changed-sentence">${content}</span>` : content;
        }).join('');
    }

    async function importWordFile(file) {
        const input = document.getElementById('studyWorkInput');
        const button = document.getElementById('studyWorkWordUpload');
        if (!file || !input || !button) return;
        if (!file.name.toLowerCase().endsWith('.docx')) {
            showStudyWorkError('Выберите файл Word в формате .docx.');
            return;
        }
        if (file.size > 10 * 1024 * 1024) {
            showStudyWorkError('Файл больше 10 МБ. Выберите документ меньшего размера.');
            return;
        }
        if (typeof mammoth === 'undefined') {
            showStudyWorkError('Не удалось загрузить модуль чтения Word. Обновите страницу и попробуйте снова.');
            return;
        }
        button.disabled = true;
        button.innerHTML = '<span class="loading"></span> Читаем документ...';
        try {
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
            const wordNote = document.getElementById('studyWorkWordNote');
            if (wordNote) {
                wordNote.innerHTML = `<i class="fa-solid fa-file-word"></i> ${escapeHtml(file.name)}`;
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
        if (typeof pdfjsLib === 'undefined') {
            showStudyWorkError('Не удалось загрузить модуль чтения PDF. Обновите страницу и попробуйте снова.');
            return;
        }
        if (file.size > 10 * 1024 * 1024) {
            showStudyWorkError('Файл больше 10 МБ. Выберите PDF меньшего размера.');
            return;
        }

        button.disabled = true;
        button.innerHTML = '<span class="loading"></span> Читаем PDF...';
        try {
            pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
            const pdf = await pdfjsLib.getDocument({ data: await file.arrayBuffer() }).promise;
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
        const current = countWords(input.value);
        const maxWords = getStudyWorkMaxWords();
        counter.textContent = `${current}/${maxWords}`;
        counter.classList.toggle('is-over-limit', current > maxWords);
    }

    function downloadTextFile() {
        const blob = new Blob([document.getElementById('studyWorkEdited').innerText], { type: 'text/plain;charset=utf-8' });
        const link = Object.assign(document.createElement('a'), { href: URL.createObjectURL(blob), download: 'study-work.txt' });
        link.click();
        URL.revokeObjectURL(link.href);
    }

    async function processWordDocument(workType, preserveOptions) {
        const formData = new FormData();
        formData.append('file', sourceWordFile);
        formData.append('work_type', workType);
        formData.append('preserve_options', JSON.stringify(preserveOptions));
        const response = await fetch('/study-work/docx/process', {
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
        processedWordBlob = await response.blob();
        if (typeof mammoth === 'undefined') throw new Error('Не удалось прочитать обработанный документ Word.');
        const result = await mammoth.extractRawText({ arrayBuffer: await processedWordBlob.arrayBuffer() });
        if (!result.value.trim()) throw new Error('В обработанном документе не найден текст.');
        return result.value.trim();
    }

    async function downloadEditedWordFile() {
        if (processedWordBlob) {
            const link = Object.assign(document.createElement('a'), {
                href: URL.createObjectURL(processedWordBlob),
                download: sourceWordFile.name.replace(/\.docx$/i, '-готово.docx'),
            });
            link.click();
            URL.revokeObjectURL(link.href);
            return;
        }
        if (sourceWordFile) {
            showNotification('Сначала обработайте загруженный документ Word.', 'error');
            return;
        }
        if (!sourceWordFile) {
            downloadTextFile();
            return;
        }

        const button = document.getElementById('studyWorkDownload');
        const editedText = document.getElementById('studyWorkEdited').innerText.trim();
        const formData = new FormData();
        formData.append('file', sourceWordFile);
        formData.append('edited_text', editedText);
        button.disabled = true;
        button.innerHTML = '<span class="loading"></span> Готовим .docx...';
        try {
            const response = await fetch('/study-work/docx/export', {
                method: 'POST',
                headers: { Authorization: `Bearer ${Auth.getToken()}` },
                body: formData,
            });
            if (!response.ok) {
                let detail = 'Не удалось подготовить документ Word.';
                try {
                    detail = (await response.json()).detail || detail;
                } catch (_) {
                    detail = `Не удалось подготовить документ Word (код ${response.status}). Перезапустите сервер и попробуйте снова.`;
                }
                throw new Error(detail);
            }
            const blob = await response.blob();
            const downloadName = sourceWordFile.name.replace(/\.docx$/i, '-готово.docx');
            const link = Object.assign(document.createElement('a'), { href: URL.createObjectURL(blob), download: downloadName });
            link.click();
            URL.revokeObjectURL(link.href);
            showNotification('Документ Word с сохранёнными отступами готов.', 'success');
        } catch (error) {
            showNotification(error.message, 'error');
        } finally {
            button.disabled = false;
            button.innerHTML = sourceWordFile
                ? '<i class="fa-solid fa-download"></i> Скачать .docx'
                : '<i class="fa-solid fa-download"></i> Скачать .txt';
        }
    }

    function renderChecklist(options) {
        const names = { numbers: 'Числа и даты', terms: 'Термины', sources: 'Ссылки и цитаты', formulas: 'Формулы и обозначения' };
        const list = document.getElementById('studyWorkChecklist');
        if (!list) return;
        list.innerHTML = options.map(option => `<li class="is-done"><i class="fa-solid fa-check"></i> ${names[option]} отмечены для сохранения</li>`).join('') +
            '<li><i class="fa-solid fa-circle-info"></i> При необходимости отдельно запустите проверку грамматики.</li>';
    }

    async function submit() {
        const input = document.getElementById('studyWorkInput');
        const button = document.getElementById('studyWorkSubmit');
        const text = input?.value.trim() || '';
        if (!text) { showStudyWorkError('Вставьте текст для подготовки.'); input?.focus(); return; }
        if (!Auth.isAuthenticated()) { Auth.showAuthModal(); return; }
        if (!isWithinStudyWorkLimit(text)) { showStudyWorkError(getStudyWorkLimitMessage(text)); return; }
        if (sourceWordFile && text !== sourceWordText) {
            showStudyWorkError('Текст Word был изменён в поле ввода. Загрузите документ заново, чтобы сохранить его структуру.');
            return;
        }
        if (!startTextProcessing('humanize')) return;

        const workType = document.querySelector('input[name="workType"]:checked')?.value || 'other';
        const preserveOptions = selectedValues('.study-work-preserve input');
        button.disabled = true;
        button.innerHTML = '<span class="loading"></span> Подготавливаем текст...';
        try {
            let editedText;
            if (sourceWordFile) {
                editedText = await processWordDocument(workType, preserveOptions);
            } else {
                const { ok, status, data } = await API.prepareStudyWork(text, workType, preserveOptions);
                if (!ok) throw { status, data };
                editedText = data.result || '';
            }
            originalText = text;
            renderChangedSentences(text, editedText);
            const downloadButton = document.getElementById('studyWorkDownload');
            if (downloadButton) downloadButton.innerHTML = sourceWordFile
                ? '<i class="fa-solid fa-download"></i> Скачать .docx'
                : '<i class="fa-solid fa-download"></i> Скачать .txt';
            document.getElementById('studyWorkResult').hidden = false;
            document.getElementById('studyWorkResult').scrollIntoView({ behavior: 'smooth', block: 'start' });
            renderChecklist(preserveOptions);
            API.saveHistory('study_work', text, editedText);
            if (typeof refreshAllSubscriptionData === 'function') refreshAllSubscriptionData();
            showToolSuccess('humanize');
        } catch (error) {
            if (error instanceof Error) {
                if (error.status) showToolError(error.status, { detail: error.message }, 'Не удалось подготовить документ Word.');
                else showNotification(error.message, 'error');
            } else {
                if (error?.status) showToolError(error.status, error.data, 'Не удалось подготовить текст.');
                else showToolNetworkError();
            }
        } finally {
            button.disabled = false;
            button.innerHTML = '<i class="fas fa-graduation-cap"></i><span>Попробовать<br>бесплатно</span>';
            finishTextProcessing();
        }
    }

    document.addEventListener('DOMContentLoaded', () => {
        const input = document.getElementById('studyWorkInput');
        input?.addEventListener('input', updateCounter);
        updateCounter();
        window.addEventListener('studyWorkLimitUpdated', updateCounter);
        document.getElementById('studyWorkWordUpload')?.addEventListener('click', () => document.getElementById('studyWorkWordFile')?.click());
        document.getElementById('studyWorkWordFile')?.addEventListener('change', event => importWordFile(event.target.files?.[0]));
        document.getElementById('studyWorkPasteBtn')?.addEventListener('click', pasteStudyWorkText);
        document.getElementById('studyWorkPdfBtn')?.addEventListener('click', () => document.getElementById('studyWorkPdfFile')?.click());
        document.getElementById('studyWorkPdfFile')?.addEventListener('change', event => importPdfFile(event.target.files?.[0]));
        document.getElementById('studyWorkSubmit')?.addEventListener('click', submit);
        document.getElementById('studyWorkRedo')?.addEventListener('click', () => document.getElementById('studyWorkForm')?.scrollIntoView({ behavior: 'smooth' }));
        document.getElementById('studyWorkRestore')?.addEventListener('click', () => {
            document.getElementById('studyWorkInput').value = originalText;
            updateCounter(); document.getElementById('studyWorkResult').hidden = true;
        });
        document.getElementById('studyWorkCopy')?.addEventListener('click', () => copyButtonText(document.getElementById('studyWorkCopy'), () => document.getElementById('studyWorkEdited').innerText));
        document.getElementById('studyWorkDownload')?.addEventListener('click', () => {
            return downloadEditedWordFile();
            const blob = new Blob([document.getElementById('studyWorkEdited').innerText], { type: 'text/plain;charset=utf-8' });
            const link = Object.assign(document.createElement('a'), { href: URL.createObjectURL(blob), download: 'учебная-работа.txt' });
            link.click(); URL.revokeObjectURL(link.href);
        });
        updateCounter();
    });
})();
