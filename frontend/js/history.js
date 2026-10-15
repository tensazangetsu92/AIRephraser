let currentPage = 1;
let currentFilter = 'all';
let currentDateFilter = 'all';
let totalPages = 1;
let isLoading = false;
let observer = null;
const HISTORY_CACHE_TTL_MS = 60_000;

const toolDestinations = {
    study_work: '/study-work',
    humanizer: '/humanize',
    detector: '/detector',
    paraphraser: '/paraphraser',
};

function getTypeName(type) {
    const types = {
        study_work: 'nav_study_work',
        humanizer: 'nav_humanizer',
        detector: 'nav_detector',
        paraphraser: 'nav_paraphraser'
    };
    return typeof window.t === 'function' ? window.t(types[type] || 'nav_tools') : type;
}

function getResultPreview(toolType, resultText, isTruncated) {
    if (toolType === 'detector') {
        try {
            const data = JSON.parse(resultText);
            return `${data.verdict || ''} (ИИ: ${data.ai_probability}%, Человек: ${data.human_probability}%)`;
        } catch {
            return `${resultText}${isTruncated ? '...' : ''}`;
        }
    }
    return `${resultText}${isTruncated ? '...' : ''}`;
}

function attachHistoryItemHandlers() {
    document.querySelectorAll('.history-item:not([data-bound])').forEach(item => {
        item.dataset.bound = '1';
        item.addEventListener('click', () => {
            const destination = toolDestinations[item.dataset.toolType];
            if (destination) {
                window.location.href = `${destination}/${encodeURIComponent(item.dataset.id)}`;
            }
        });
    });
}

function createHistoryMessage(message, extraClass = '') {
    const element = document.createElement('div');
    element.className = `history-empty${extraClass ? ` ${extraClass}` : ''}`;
    element.textContent = message;
    return element;
}

function resetHistoryFilters() {
    currentFilter = 'all';
    currentDateFilter = 'all';
    currentPage = 1;
    totalPages = 1;
    document.querySelectorAll('.history-tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.type === 'all');
    });
    const dateFilter = document.getElementById('historyFilterDate');
    if (dateFilter) dateFilter.value = 'all';
    loadHistory(false);
}

function createHistoryEmptyState(isFiltered) {
    const element = document.createElement('section');
    element.className = 'history-empty history-empty-rich';
    element.setAttribute('aria-live', 'polite');

    const icon = document.createElement('i');
    icon.className = `fa-solid ${isFiltered ? 'fa-filter' : 'fa-clock-rotate-left'} history-empty-icon`;
    icon.setAttribute('aria-hidden', 'true');

    const title = document.createElement('h2');
    title.textContent = typeof window.t === 'function'
        ? window.t(isFiltered ? 'history_empty_filtered_title' : 'history_empty_title')
        : (isFiltered ? 'По этому фильтру пока ничего нет' : 'История пока пуста');

    const description = document.createElement('p');
    description.textContent = typeof window.t === 'function'
        ? window.t(isFiltered ? 'history_empty_filtered_description' : 'history_empty_description')
        : (isFiltered ? 'Выберите другой тип обработки или покажите всю историю.' : 'После первой обработки сохранённый текст и результат появятся здесь.');

    const action = isFiltered ? document.createElement('button') : document.createElement('a');
    action.className = 'history-empty-action';
    if (isFiltered) {
        action.type = 'button';
        action.addEventListener('click', resetHistoryFilters);
    } else {
        action.href = '/humanize';
    }
    action.textContent = typeof window.t === 'function'
        ? window.t(isFiltered ? 'history_empty_filtered_action' : 'history_empty_action')
        : (isFiltered ? 'Показать всю историю' : 'Очеловечить текст');

    element.append(icon, title, description, action);
    return element;
}

function createSkeletonLine(className = '') {
    const line = document.createElement('span');
    line.className = `skeleton skeleton-text${className ? ` ${className}` : ''}`;
    return line;
}

function createHistorySkeletonItem() {
    const element = document.createElement('div');
    element.className = 'history-item history-skeleton-item';
    element.setAttribute('aria-hidden', 'true');

    const header = document.createElement('div');
    header.className = 'history-item-header';
    header.append(createSkeletonLine('skeleton-text--short'), createSkeletonLine('skeleton-text--short'));

    const texts = document.createElement('div');
    texts.className = 'history-item-texts';
    for (let columnIndex = 0; columnIndex < 2; columnIndex += 1) {
        const column = document.createElement('div');
        column.className = 'history-item-column skeleton-line-stack';
        column.append(createSkeletonLine(), createSkeletonLine(), createSkeletonLine());
        texts.appendChild(column);
    }

    element.append(header, texts);
    return element;
}

function createHistorySkeletons(count = 3) {
    return Array.from({ length: count }, createHistorySkeletonItem);
}

function createHistoryItem(item) {
    const element = document.createElement('div');
    element.className = 'history-item';
    element.dataset.id = String(item.id);
    element.dataset.toolType = String(item.tool_type || '');

    const header = document.createElement('div');
    header.className = 'history-item-header';
    const type = document.createElement('span');
    type.className = 'history-item-type';
    type.textContent = getTypeName(item.tool_type);
    const date = document.createElement('span');
    date.className = 'history-item-date';
    date.textContent = new Date(item.created_at).toLocaleString(window.currentLang === 'en' ? 'en-US' : 'ru-RU');
    header.append(type, date);

    const texts = document.createElement('div');
    texts.className = 'history-item-texts';
    const originalColumn = document.createElement('section');
    originalColumn.className = 'history-item-column';
    const original = document.createElement('div');
    original.className = 'history-item-original';
    original.textContent = `${item.original_preview || ''}${item.original_is_truncated ? '...' : ''}`;
    originalColumn.appendChild(original);

    const resultColumn = document.createElement('section');
    resultColumn.className = 'history-item-column';
    const result = document.createElement('div');
    result.className = 'history-item-result';
    result.textContent = getResultPreview(
        item.tool_type,
        item.result_preview || '',
        item.result_is_truncated,
    );
    resultColumn.appendChild(result);

    texts.append(originalColumn, resultColumn);
    element.append(header, texts);
    return element;
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
    historyList.setAttribute('aria-busy', 'true');

    if (!append) {
        historyList.replaceChildren(...createHistorySkeletons());
    } else {
        const loader = createHistorySkeletonItem();
        loader.classList.add('history-loader');
        historyList.appendChild(loader);
    }

    try {
        const cacheKey = `history:${currentPage}:${currentFilter}:${currentDateFilter}`;
        let data = typeof window.getCachedUserData === 'function'
            ? window.getCachedUserData(cacheKey)
            : null;

        if (!data) {
            const response = await Auth.authorizedFetch(`/user/history?page=${currentPage}&limit=5&type=${currentFilter}&date=${currentDateFilter}`, {
                headers: { 'Authorization': `Bearer ${Auth.getToken()}` }
            });
            data = await response.json();
            if (data?.success && typeof window.setCachedUserData === 'function') {
                window.setCachedUserData(cacheKey, data, HISTORY_CACHE_TTL_MS);
            }
        }

        historyList.querySelector('.history-loader')?.remove();

        if (data.success && data.history?.length > 0) {
            if (!append) historyList.replaceChildren();

            totalPages = data.total_pages || 1;
            data.history.forEach(item => historyList.appendChild(createHistoryItem(item)));

            attachHistoryItemHandlers();
        } else if (!append) {
            historyList.replaceChildren(createHistoryEmptyState(
                currentFilter !== 'all' || currentDateFilter !== 'all',
            ));
        }
    } catch {
        historyList.querySelector('.history-loader')?.remove();
        if (!append) historyList.replaceChildren(createHistoryMessage(
            typeof window.t === 'function' ? window.t('history_load_error') : 'Ошибка загрузки истории',
        ));
    }

    historyList.setAttribute('aria-busy', 'false');
    isLoading = false;
}

function setClearHistoryError(message = '') {
    const error = document.getElementById('clearHistoryError');
    if (!error) return;
    error.textContent = message;
    error.hidden = !message;
}

function closeClearHistoryModal() {
    const modal = document.getElementById('clearHistoryModal');
    if (!modal) return;
    modal.classList.remove('active');
    modal.setAttribute('aria-hidden', 'true');
    document.getElementById('clearHistoryConfirmation').value = '';
    document.getElementById('clearHistoryConfirm').disabled = true;
    setClearHistoryError();
}

function openClearHistoryModal() {
    const modal = document.getElementById('clearHistoryModal');
    if (!modal) return;
    modal.classList.add('active');
    modal.setAttribute('aria-hidden', 'false');
    document.getElementById('clearHistoryConfirmation').value = '';
    document.getElementById('clearHistoryConfirm').disabled = true;
    setClearHistoryError();
    window.setTimeout(() => document.getElementById('clearHistoryConfirmation')?.focus(), 100);
}

async function clearHistory() {
    const confirmation = document.getElementById('clearHistoryConfirmation')?.value.trim();
    const confirmButton = document.getElementById('clearHistoryConfirm');
    if (confirmation !== 'DELETE' || !confirmButton) return;

    const initialText = confirmButton.textContent;
    confirmButton.disabled = true;
    confirmButton.textContent = typeof window.t === 'function' ? window.t('history_clearing') : 'Очищаем…';
    setClearHistoryError();

    try {
        const response = await Auth.authorizedFetch('/user/history/clear', {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${Auth.getToken()}`,
            },
            body: JSON.stringify({ confirmation }),
        });
        const data = await response.json().catch(() => ({}));

        if (response.ok) {
            showNotification(typeof window.t === 'function' ? window.t('history_cleared') : 'История очищена', 'success');
            closeClearHistoryModal();
            if (typeof window.clearCachedUserData === 'function') window.clearCachedUserData('history:');
            currentPage = 1;
            totalPages = 1;
            loadHistory(false);
        } else {
            setClearHistoryError(data.detail || (typeof window.t === 'function' ? window.t('history_clear_error') : 'Ошибка очистки истории'));
        }
    } catch {
        setClearHistoryError(typeof window.t === 'function' ? window.t('profile_network_error') : 'Ошибка соединения. Проверьте интернет и повторите попытку.');
    } finally {
        if (!document.getElementById('clearHistoryModal')?.classList.contains('active')) return;
        confirmButton.disabled = confirmation !== 'DELETE';
        confirmButton.textContent = initialText;
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

    document.getElementById('clearHistoryBtn')?.addEventListener('click', openClearHistoryModal);
    document.getElementById('clearHistoryClose')?.addEventListener('click', closeClearHistoryModal);
    document.getElementById('clearHistoryCancel')?.addEventListener('click', closeClearHistoryModal);
    document.getElementById('clearHistoryConfirm')?.addEventListener('click', clearHistory);
    document.getElementById('clearHistoryConfirmation')?.addEventListener('input', (event) => {
        document.getElementById('clearHistoryConfirm').disabled = event.target.value.trim() !== 'DELETE';
        setClearHistoryError();
    });
    document.getElementById('clearHistoryModal')?.addEventListener('click', (event) => {
        if (event.target.id === 'clearHistoryModal') closeClearHistoryModal();
    });
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') closeClearHistoryModal();
    });
});
