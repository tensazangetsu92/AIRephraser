// frontend/js/history.js

let currentPage = 1;
let currentFilter = 'all';
let currentDateFilter = 'all';
let totalPages = 1;

async function loadHistory() {
    const historyList = document.getElementById('historyList');
    if (!historyList) return;

    historyList.innerHTML = '<div class="history-empty">Загрузка...</div>';

    try {
        const response = await fetch(`/user/history?page=${currentPage}&type=${currentFilter}&date=${currentDateFilter}`, {
            headers: { 'Authorization': `Bearer ${Auth.getToken()}` }
        });
        const data = await response.json();

        if (data.success && data.history && data.history.length > 0) {
            historyList.innerHTML = data.history.map(item => `
                <div class="history-item" data-id="${item.id}" data-original="${escapeHtmlAttr(item.original_text)}" data-result="${escapeHtmlAttr(item.result_text)}">
                    <div class="history-item-header">
                        <span class="history-item-type">${getTypeName(item.tool_type)}</span>
                        <span class="history-item-date">${new Date(item.created_at).toLocaleString()}</span>
                    </div>
                    <div class="history-item-original">
                        ${escapeHtml(item.original_text.substring(0, 250))}${item.original_text.length > 200 ? '...' : ''}
                    </div>
                    <div class="history-item-result">
                        ${escapeHtml(item.result_text.substring(0, 250))}${item.result_text.length > 200 ? '...' : ''}
                    </div>
                </div>
            `).join('');

            totalPages = data.total_pages || 1;
            updatePagination();
            attachHistoryItemHandlers();
        } else {
            historyList.innerHTML = '<div class="history-empty">История пуста</div>';
        }
    } catch (err) {
        console.error('Failed to load history:', err);
        historyList.innerHTML = '<div class="history-empty">Ошибка загрузки истории</div>';
    }
}

function attachHistoryItemHandlers() {
    document.querySelectorAll('.history-item').forEach(item => {
        item.addEventListener('click', () => {
            const original = item.dataset.original;
            const result = item.dataset.result;

            localStorage.setItem('saved_input_text', original);
            localStorage.setItem('saved_result_text', result);

            window.location.href = '/humanizer';
        });
    });
}

function getTypeName(type) {
    const types = {
        'humanizer': 'Гуманайзер',
        'detector': 'Детектор ИИ',
        'paraphraser': 'Перефразер',
        'grammar': 'Грамматика'
    };
    return types[type] || 'Обработка';
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function escapeHtmlAttr(text) {
    return text
        .replace(/&/g, '&amp;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

function updatePagination() {
    const pagination = document.getElementById('historyPagination');
    const prevBtn = document.getElementById('prevPageBtn');
    const nextBtn = document.getElementById('nextPageBtn');
    const pageInfo = document.getElementById('pageInfo');

    if (!pagination) return;

    if (totalPages > 1) {
        pagination.style.display = 'flex';
    } else {
        pagination.style.display = 'none';
    }

    if (prevBtn) prevBtn.disabled = currentPage <= 1;
    if (nextBtn) nextBtn.disabled = currentPage >= totalPages;
    if (pageInfo) pageInfo.textContent = `Страница ${currentPage} из ${totalPages}`;
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
    } catch (err) {
        showNotification('Ошибка соединения', 'error');
    }
}

document.addEventListener('DOMContentLoaded', () => {
    loadHistory();

    document.getElementById('prevPageBtn')?.addEventListener('click', () => {
        if (currentPage > 1) {
            currentPage--;
            loadHistory();
        }
    });

    document.getElementById('nextPageBtn')?.addEventListener('click', () => {
        if (currentPage < totalPages) {
            currentPage++;
            loadHistory();
        }
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