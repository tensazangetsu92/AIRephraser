// frontend/js/main.js - точка входа

// DOM элементы (делаем глобальными)
window.elements = {};

// Инициализация DOM элементов
function initElements() {
    window.elements = {
        input: document.getElementById('input'),
        result: document.getElementById('result'),
        humanizeBtn: document.getElementById('humanizeBtn'),
        copyBtn: document.getElementById('copyBtn'),
        intensity: document.getElementById('intensity'),
        tone: document.getElementById('tone'),
        style: document.getElementById('style'),
        length: document.getElementById('length'),
        authBtn: document.getElementById('authBtn'),
        userName: document.getElementById('userName'),
        wordCounter: document.getElementById('wordCounter'),
    };

    console.log('Elements loaded:', {
        humanizeBtn: !!window.elements.humanizeBtn,
        input: !!window.elements.input,
        result: !!window.elements.result
    });
}

// Event listeners
function initEventListeners() {
    console.log('initEventListeners called');

    if (window.elements.humanizeBtn) {
        window.elements.humanizeBtn.addEventListener('click', () => {
            console.log('Humanize button clicked');
            if (typeof window.send === 'function') {
                window.send();
            } else {
                console.error('window.send is not defined!');
            }
        });
        console.log('humanizeBtn handler attached');
    }

    if (window.elements.copyBtn) {
        window.elements.copyBtn.addEventListener('click', () => {
            if (typeof window.copyText === 'function') {
                window.copyText();
            }
        });
        console.log('copyBtn handler attached');
    }

    if (window.elements.input) {
        // 👇 ИСПРАВЛЕНО: updateCharCounter → updateWordCounter
        window.elements.input.addEventListener('input', () => {
            console.log('input event fired');  // Отладка
            if (typeof window.updateWordCounter === 'function') {
                window.updateWordCounter();
            } else {
                console.error('window.updateWordCounter is not defined!');
            }
        });

        window.elements.input.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.key === 'Enter') {
                if (typeof window.send === 'function') {
                    window.send();
                }
            }
        });
        console.log('input handler attached');
    }
}

// Инициализация
function init() {
    initElements();
    initEventListeners();
    initCustomSelects();
    if (typeof initUserMenu === 'function') {
        initUserMenu();
    }
    if (typeof updateUserMenu === 'function') {
        updateUserMenu();
    }
    if (typeof loadTextFromLocalStorage === 'function') {
        loadTextFromLocalStorage();
    }
    if (typeof initAutoSave === 'function') {
        initAutoSave();
    }

    if (window.elements.input && window.elements.wordCounter) {
        if (typeof window.updateWordCounter === 'function') {
            window.updateWordCounter();
        }
    }

    if (typeof window.updateUI === 'function') {
        window.updateUI();
    }

    // 👇 ЗАМЕНИТЬ charCounter НА wordCounter
    if (window.elements.input && window.elements.wordCounter) {
        if (typeof window.updateWordCounter === 'function') {
            console.log("asd");
            window.updateWordCounter();
        }
    }

    if (typeof window.updateUI === 'function') {
        window.updateUI();
    }
}



if (typeof initLanguage === 'function') {
    initLanguage();
}

function initCustomSelects() {
    console.log('initCustomSelects called, found:', document.querySelectorAll('.custom-select').length);
    document.querySelectorAll('.custom-select').forEach(select => {
        const trigger = select.querySelector('.custom-select-trigger');
        const label = select.querySelector('.custom-select-label');
        const options = select.querySelectorAll('.custom-select-option');
        const hiddenInput = select.nextElementSibling; // input[type=hidden]

        trigger.addEventListener('click', (e) => {
            e.stopPropagation();
            // Закрываем остальные открытые селекты
            document.querySelectorAll('.custom-select.open').forEach(s => {
                if (s !== select) s.classList.remove('open');
            });
            select.classList.toggle('open');
        });

        options.forEach(option => {
            option.addEventListener('click', () => {
                const value = option.dataset.value;
                const text = option.textContent;

                label.textContent = text;
                hiddenInput.value = value;
                select.dataset.value = value;

                options.forEach(o => o.classList.remove('selected'));
                option.classList.add('selected');

                select.classList.remove('open');
            });
        });
    });

    // Закрытие при клике вне
    document.addEventListener('click', () => {
        document.querySelectorAll('.custom-select.open').forEach(s => s.classList.remove('open'));
    });
}

// Запуск
init();