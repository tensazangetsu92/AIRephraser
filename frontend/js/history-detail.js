(function () {
    const toolDestinations = {
        study_work: '/study-work',
        humanizer: '/humanize',
        detector: '/detector',
        paraphraser: '/paraphraser',
    };

    const toolTranslationKeys = {
        study_work: 'nav_study_work',
        humanizer: 'nav_humanizer',
        detector: 'nav_detector',
        paraphraser: 'nav_paraphraser',
    };

    const getToolName = toolType => {
        const key = toolTranslationKeys[toolType] || 'nav_tools';
        return typeof window.t === 'function' ? window.t(key) : toolType;
    };

    const formatDetectorResult = text => {
        try {
            return JSON.stringify(JSON.parse(text), null, 2);
        } catch {
            return text;
        }
    };

    const copyText = async text => {
        try {
            const copied = await window.copyTextToClipboard?.(text);
            if (!copied) throw new Error('clipboard_copy_failed');
            if (typeof showNotification === 'function') showNotification('Текст скопирован', 'success');
        } catch {
            if (typeof showNotification === 'function') showNotification('Не удалось скопировать текст', 'error');
        }
    };

    async function loadHistoryDetail() {
        const root = document.getElementById('historyDetail');
        const state = document.getElementById('historyDetailState');
        const content = document.getElementById('historyDetailContent');
        if (!root || !state || !content) return;

        if (!Auth.isAuthenticated()) {
            state.textContent = typeof window.t === 'function' ? window.t('history_detail_auth_required') : 'Войдите в аккаунт, чтобы открыть работу.';
            Auth.showAuthModal();
            return;
        }

        try {
            const response = await Auth.authorizedFetch(`/user/history/${encodeURIComponent(root.dataset.historyId)}`, {
                headers: { Authorization: `Bearer ${Auth.getToken()}` },
            });
            const data = await response.json();
            if (!response.ok || !data.success || !data.history) {
                throw new Error(response.status === 404 ? 'not_found' : 'load_error');
            }

            const item = data.history;
            const original = String(item.original_text || '');
            const result = String(item.result_text || '');
            const displayedResult = item.tool_type === 'detector' ? formatDetectorResult(result) : result;

            document.getElementById('historyDetailTool').textContent = getToolName(item.tool_type);
            document.getElementById('historyDetailTitle').textContent = getToolName(item.tool_type);
            document.getElementById('historyDetailDate').textContent = new Date(item.created_at).toLocaleString(window.currentLang === 'en' ? 'en-US' : 'ru-RU');
            document.getElementById('historyDetailOriginal').textContent = original;
            document.getElementById('historyDetailResult').textContent = displayedResult;

            document.getElementById('historyDetailCopyOriginal').addEventListener('click', () => copyText(original));
            document.getElementById('historyDetailCopyResult').addEventListener('click', () => copyText(result));
            const openButton = document.getElementById('historyDetailOpen');
            openButton.disabled = !toolDestinations[item.tool_type];
            openButton.addEventListener('click', () => {
                const destination = toolDestinations[item.tool_type];
                if (!destination) return;
                window.location.href = `${destination}/${encodeURIComponent(item.id)}`;
            });

            state.hidden = true;
            content.hidden = false;
        } catch (error) {
            const key = error.message === 'not_found' ? 'history_detail_not_found' : 'history_detail_load_error';
            state.className = 'history-empty';
            state.removeAttribute('aria-busy');
            state.textContent = typeof window.t === 'function' ? window.t(key) : 'Не удалось открыть работу.';
        }
    }

    document.addEventListener('DOMContentLoaded', loadHistoryDetail);
})();
