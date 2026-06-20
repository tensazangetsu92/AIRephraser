let currentPage = 1;
let currentFilter = 'all';
let currentDateFilter = 'all';
let totalPages = 1;
let isLoading = false;
let observer = null;

function escapeHtmlAttr(text) {
    return text
        .replace(/&/g, '&amp;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

function getTypeName(type) {
    const types = {
        humanizer: 'Гуманайзер',
        detector: 'Детектор ИИ',
        paraphraser: 'Перефразер',
        grammar: 'Грамматика'
    };
    return types[type] || 'Обработка';
}

function getResultPreview(toolType, resultText) {
    if (toolType === 'detector') {
        try {
            const data = JSON.parse(resultText);
            return `${data.verdict || ''} (ИИ: ${data.ai_probability}%, Человек: ${data.human_probability}%)`;
        } catch {
            return resultText.substring(0, 250);
        }
    }
    return resultText.substring(0, 250) + (resultText.length > 250 ? '...' : '');
}

function attachHistoryItemHandlers() {
    document.querySelectorAll('.history-item:not([data-bound])').forEach(item => {
        item.dataset.bound = '1';
        item.addEventListener('click', () => {
            const toolType = item.querySelector('.history-item-type')?.textContent.trim();
            const original = item.dataset.original;
            const result = item.dataset.result;

            if (toolType === 'Детектор ИИ') {
                localStorage.setItem('detector_input_text', original);
                try {
                    localStorage.setItem('detector_result_data', JSON.stringify(JSON.parse(result)));
                } catch {
                    localStorage.removeItem('detector_result_data');
                }
                window.location.href = '/detector';
            } else {
                localStorage.setItem('saved_input_text', original);
                localStorage.setItem('saved_result_text', result);
                window.location.href = '/humanizer';
            }
        });
    });
}

function initObserver() {
    if (observer) observer.disconnect();

    const sentinel = document.getElementById('historySentinel');
    if (!sentinel) return;

    observer = new IntersectionObserver((entries) => {
        if (entries[0].isIntersecting && currentPage < totalPages && !isLoading) {
            currentPage++;
            loadHistory(true);
        }
    }, { threshold: 0.1 });

    observer.observe(sentinel);
}

async function loadHistory(append = false) {
    if (isLoading) return;
    isLoading = true;

    const historyList = document.getElementById('historyList');
    if (!historyList) { isLoading = false; return; }

    if (!append) {
        historyList.innerHTML = '<div class="history-empty">Загрузка...</div>';
    } else {
        const loader = document.createElement('div');
        loader.className = 'history-empty history-loader';
        loader.textContent = 'Загрузка...';
        historyList.appendChild(loader);
    }

    try {
        const response = await fetch(`/user/history?page=${currentPage}&limit=5&type=${currentFilter}&date=${currentDateFilter}`, {
            headers: { 'Authorization': `Bearer ${Auth.getToken()}` }
        });
        const data = await response.json();

        historyList.querySelector('.history-loader')?.remove();

        if (data.success && data.history?.length > 0) {
            if (!append) historyList.innerHTML = '';

            totalPages = data.total_pages || 1;

            data.history.forEach(item => {
                const el = document.createElement('div');
                el.className = 'history-item';
                el.dataset.id = item.id;
                el.dataset.original = escapeHtmlAttr(item.original_text);
                el.dataset.result = escapeHtmlAttr(item.result_text);
                el.innerHTML = `
                    <div class="history-item-header">
                        <span class="history-item-type">${getTypeName(item.tool_type)}</span>
                        <span class="history-item-date">${new Date(item.created_at).toLocaleString()}</span>
                    </div>
                    <div class="history-item-original">
                        ${escapeHtml(item.original_text.substring(0, 250))}${item.original_text.length > 250 ? '...' : ''}
                    </div>
                    <div class="history-item-result">
                        ${escapeHtml(getResultPreview(item.tool_type, item.result_text))}
                    </div>
                `;
                historyList.appendChild(el);
            });

            attachHistoryItemHandlers();
        } else if (!append) {
            historyList.innerHTML = '<div class="history-empty">История пуста</div>';
        }
    } catch {
        historyList.querySelector('.history-loader')?.remove();
        if (!append) historyList.innerHTML = '<div class="history-empty">Ошибка загрузки истории</div>';
    }

    isLoading = false;
}

async function clearHistory() {
    if (!confirm('Вы уверены? Вся история будет удалена безвозвратно.')) return;

    try {
        const response = await fetch('/user/history/clear', {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${Auth.getToken()}` }
        });
        const data = await response.json();

        if (response.ok) {
            showNotification('История очищена', 'success');
            currentPage = 1;
            totalPages = 1;
            loadHistory(false);
        } else {
            showNotification(data.detail || 'Ошибка очистки', 'error');
        }
    } catch {
        showNotification('Ошибка соединения', 'error');
    }
}

document.addEventListener('DOMContentLoaded', () => {
    initObserver();
    loadHistory();

    document.querySelectorAll('.history-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.history-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            currentFilter = tab.dataset.type;
            currentPage = 1;
            totalPages = 1;
            loadHistory(false);
        });
    });

    document.getElementById('historyFilterDate')?.addEventListener('change', (e) => {
        currentDateFilter = e.target.value;
        currentPage = 1;
        totalPages = 1;
        loadHistory(false);
    });

    document.getElementById('clearHistoryBtn')?.addEventListener('click', clearHistory);
});