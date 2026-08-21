async function checkGrammar() {
    const input = document.getElementById('input');
    const result = document.getElementById('result');
    const button = document.getElementById('checkGrammarBtn');
    const text = input?.value?.trim();

    if (!text) {
        showEmptyTextError(input);
        return;
    }

    if (!text) {
        showWarning('Введите текст для проверки грамматики');
        return;
    }
    if (!Auth.isAuthenticated()) {
        Auth.showAuthModal();
        return;
    }
    if (!isWithinWordLimit(text)) {
        showRequestLimitError(text);
        return;
    }
    if (!startTextProcessing('grammar')) return;

    button.disabled = true;
    button.textContent = 'Проверка...';
    updateResultWordCounter('');
    try {
        const {ok, status, data} = await API.checkGrammar(text);
        if (ok) {
            const resultColumn = document.getElementById('grammarResultCol');
            if (resultColumn) resultColumn.style.display = 'flex';
            document.getElementById('editorContainer')?.classList.remove('single-col');
            renderGrammarResult(text, data.result || '');
            await API.saveHistory('grammar', text, data.result || '');
            if (typeof refreshAllSubscriptionData === 'function') refreshAllSubscriptionData();
            showToolSuccess('grammar');
        } else if (status === 401) {
            const errorMessage = showToolError(status, data);
            showGrammarErrorResult(errorMessage);
            Auth.logout();
            Auth.showAuthModal();
        } else if (status === 429) {
            const errorMessage = showToolError(status, data);
            showGrammarErrorResult(errorMessage);
            if (typeof refreshAllSubscriptionData === 'function') refreshAllSubscriptionData();
        } else {
            const errorMessage = showToolError(status, data, 'Не удалось проверить текст');
            showGrammarErrorResult(errorMessage);
        }
    } catch {
        showGrammarErrorResult(showToolNetworkError());
    } finally {
        button.disabled = false;
        button.textContent = 'Исправить грамматику';
        finishTextProcessing();
    }
}

function showGrammarErrorResult(message) {
    const resultColumn = document.getElementById('grammarResultCol');
    const result = document.getElementById('result');
    document.getElementById('grammarResult')?.remove();
    if (resultColumn) resultColumn.style.display = 'flex';
    document.getElementById('editorContainer')?.classList.remove('single-col');
    if (result) {
        result.style.display = '';
        result.value = message;
    }
    updateResultWordCounter('');
}

function getGrammarResultElement() {
    const textarea = document.getElementById('result');
    if (!textarea) return null;
    let result = document.getElementById('grammarResult');
    if (!result) {
        result = document.createElement('div');
        result.id = 'grammarResult';
        result.className = 'output';
        result.style.whiteSpace = 'pre-wrap';
        result.style.overflowY = 'auto';
        result.style.lineHeight = '1.6';
        textarea.parentNode.insertBefore(result, textarea);
        textarea.style.display = 'none';
    }
    return result;
}

function renderGrammarResult(original, corrected) {
    const result = getGrammarResultElement();
    if (!result) return;
    const textarea = document.getElementById('result');
    if (textarea) textarea.value = corrected;
    updateResultWordCounter(corrected);
    const originalTokens = original.split(/(\s+)/);
    const correctedTokens = corrected.split(/(\s+)/);
    result.innerHTML = correctedTokens.map((token, index) => {
        if (/^\s+$/.test(token)) return token;
        const source = originalTokens[index];
        if (source === undefined || source !== token) {
            const color = source === undefined ? 'rgba(59, 130, 246, .3)' : 'rgba(245, 158, 11, .3)';
            return `<span style="background:${color};border-radius:4px;padding:1px 2px">${escapeHtml(token)}</span>`;
        }
        return escapeHtml(token);
    }).join('');
}

function restoreGrammarHistoryResult() {
    const historyRestore = typeof takeHistoryRestore === 'function' ? takeHistoryRestore('grammar') : null;
    const original = historyRestore?.original ?? localStorage.getItem('grammar_history_input_text');
    const corrected = historyRestore?.result ?? localStorage.getItem('grammar_history_result_text');

    if (!original) return;

    localStorage.removeItem('grammar_history_input_text');
    localStorage.removeItem('grammar_history_result_text');

    const input = document.getElementById('input');
    if (input) {
        input.value = original;
        if (typeof updateWordCounter === 'function') updateWordCounter();
    }

    if (corrected !== null) {
        const resultColumn = document.getElementById('grammarResultCol');
        if (resultColumn) resultColumn.style.display = 'flex';
        document.getElementById('editorContainer')?.classList.remove('single-col');
        renderGrammarResult(original, corrected);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('checkGrammarBtn')?.addEventListener('click', checkGrammar);
    document.getElementById('pasteBtn')?.addEventListener('click', window.pasteFromClipboard);
    document.getElementById('copyInputBtn')?.addEventListener('click', window.copyInputText);
    document.getElementById('copyResultBtn')?.addEventListener('click', window.copyResultText);
    initPdfUpload();
    initWordUpload();
    restoreGrammarHistoryResult();
});
