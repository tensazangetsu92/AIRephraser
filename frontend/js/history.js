let currentPage = 1;
let currentFilter = 'all';
let currentDateFilter = 'all';
let totalPages = 1;

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

function updatePagination() {
    const pagination = document.getElementById('historyPagination');
    const prevBtn = document.getElementById('prevPageBtn');
    const nextBtn = document.getElementById('nextPageBtn');
    const pageInfo = document.getElementById('pageInfo');

    if (!pagination) return;

    pagination.style.display = totalPages > 1 ? 'flex' : 'none';
    if (prevBtn) prevBtn.disabled = currentPage <= 1;
    if (nextBtn) nextBtn.disabled = currentPage >= totalPages;
    if (pageInfo) pageInfo.textContent = `Страница ${currentPage} из ${totalPages}`;
}

function attachHistoryItemHandlers() {
    document.querySelectorAll('.history-item').forEach(item => {
        item.addEventListener('click', () => {
            localStorage.setItem('saved_input_text', item.dataset.original);
            localStorage.setItem('saved_result_text', item.dataset.result);
            window.location.href = '/humanizer';
        });
    });
}

async function loadHistory() {
    const historyList = document.getElementById('historyList');
    if (!historyList) return;

    historyList.innerHTML = '<div class="history-empty">Загрузка...</div>';

    try {
        const response = await fetch(`/user/history?page=${currentPage}&type=${currentFilter}&date=${currentDateFilter}`, {
            headers: { 'Authorization': `Bearer ${Auth.getToken()}` }
        });
        const data = await response.json();

        if (data.success && data.history?.length > 0) {
            historyList.innerHTML = data.history.map(item => `
                <div class="history-item"
                    data-id="${item.id}"
                    data-original="${escapeHtmlAttr(item.original_text)}"
                    data-result="${escapeHtmlAttr(item.result_text)}">
                    <div class="history-item-header">
                        <span class="history-item-type">${getTypeName(item.tool_type)}</span>
                        <span class="history-item-date">${new Date(item.created_at).toLocaleString()}</span>
                    </div>
                    <div class="history-item-original">
                        ${escapeHtml(item.original_text.substring(0, 250))}${item.original_text.length > 250 ? '...' : ''}
                    </div>
                    <div class="history-item-result">
                        ${escapeHtml(item.result_text.substring(0, 250))}${item.result_text.length > 250 ? '...' : ''}
                    </div>
                </div>
            `).join('');

            totalPages = data.total_pages || 1;
            updatePagination();
            attachHistoryItemHandlers();
        } else {
            historyList.innerHTML = '<div class="history-empty">История пуста</div>';
        }
    } catch {
        historyList.innerHTML = '<div class="history-empty">Ошибка загрузки истории</div>';
    }
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
            loadHistory();
        } else {
            showNotification(data.detail || 'Ошибка очистки', 'error');
        }
    } catch {
        showNotification('Ошибка соединения', 'error');
    }
}

document.addEventListener('DOMContentLoaded', () => {
    loadHistory();

    document.getElementById('prevPageBtn')?.addEventListener('click', () => {
        if (currentPage > 1) { currentPage--; loadHistory(); }
    });

    document.getElementById('nextPageBtn')?.addEventListener('click', () => {
        if (currentPage < totalPages) { currentPage++; loadHistory(); }
    });

    document.querySelectorAll('.history-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.history-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            currentFilter = tab.dataset.type;
            currentPage = 1;
            loadHistory();
        });
    });

    document.getElementById('historyFilterDate')?.addEventListener('change', (e) => {
        currentDateFilter = e.target.value;
        currentPage = 1;
        loadHistory();
    });

    document.getElementById('clearHistoryBtn')?.addEventListener('click', clearHistory);
});