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
        charCounter: document.getElementById('charCounter'),
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
        // Убираем стрелочную функцию, вызываем send напрямую
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
        window.elements.input.addEventListener('input', () => {
            if (typeof window.updateCharCounter === 'function') {
                window.updateCharCounter();
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
    console.log('init called');
    initElements();
    initEventListeners();

    if (window.elements.input && window.elements.charCounter) {
        if (typeof window.updateCharCounter === 'function') {
            window.updateCharCounter();
        }
    }

    if (typeof window.updateUI === 'function') {
        window.updateUI();
    }
}

// Запуск
init();

if (typeof initLanguage === 'function') {
    initLanguage();
}