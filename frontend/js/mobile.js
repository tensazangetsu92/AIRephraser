(function () {
    const menuBtn = document.getElementById('mobileHeaderToggle');
    const authBtn = document.getElementById('mobileHeaderAuth');
    const registerBtn = document.getElementById('mobileHeaderRegister');
    const sidebar = document.querySelector('.sidebar');

    if (!menuBtn || !sidebar) return;

    const overlay = document.createElement('div');
    overlay.className = 'sidebar-overlay';
    document.body.appendChild(overlay);

    // Первые 30% ширины экрана: зона остаётся одинаковой на телефонах разной ширины.
    // Самый край экрана часто перехватывает системный жест «Назад» браузера.
    const SWIPE_OPEN_ZONE_RATIO = 0.3;
    const SWIPE_DISTANCE = 48;
    let swipeStart = null;

    function setPageScrollLocked(locked) {
        document.documentElement.classList.toggle('sidebar-scroll-locked', locked);
        document.body.classList.toggle('sidebar-scroll-locked', locked);
    }

    function openSidebar() {
        overlay.style.display = 'block';
        requestAnimationFrame(() => overlay.classList.add('visible'));
        sidebar.classList.add('mobile-open');
        menuBtn.innerHTML = '<i class="fas fa-times"></i>';
        setPageScrollLocked(true);
    }

    function closeSidebar() {
        sidebar.classList.remove('mobile-open');
        overlay.classList.remove('visible');
        overlay.addEventListener('transitionend', () => {
            overlay.style.display = 'none';
        }, { once: true });
        menuBtn.innerHTML = '<i class="fas fa-bars"></i>';
        setPageScrollLocked(false);
    }

    const closeBtn = document.getElementById('sidebarMobileClose');
    if (closeBtn) {
        closeBtn.addEventListener('click', closeSidebar);
    }

    menuBtn.addEventListener('click', () => {
        sidebar.classList.contains('mobile-open') ? closeSidebar() : openSidebar();
    });

    overlay.addEventListener('click', closeSidebar);

    function rememberSwipeStart(x, y) {
        swipeStart = {
            x,
            y,
            sidebarWasOpen: sidebar.classList.contains('mobile-open'),
        };
    }

    function handleSwipeEnd(x, y) {
        if (!swipeStart || window.innerWidth > 768) {
            swipeStart = null;
            return;
        }

        const horizontalDistance = x - swipeStart.x;
        const verticalDistance = y - swipeStart.y;
        const isHorizontalSwipe = Math.abs(horizontalDistance) > Math.abs(verticalDistance);
        const startedInOpenZone = swipeStart.x <= window.innerWidth * SWIPE_OPEN_ZONE_RATIO;

        if (isHorizontalSwipe && !swipeStart.sidebarWasOpen
            && startedInOpenZone && horizontalDistance >= SWIPE_DISTANCE) {
            openSidebar();
        } else if (isHorizontalSwipe && swipeStart.sidebarWasOpen
            && horizontalDistance <= -SWIPE_DISTANCE) {
            closeSidebar();
        }

        swipeStart = null;
    }

    // Capture нужен, чтобы обработчики редактора и кнопок не могли остановить жест.
    document.addEventListener('touchstart', (event) => {
        if (window.innerWidth > 768 || event.touches.length !== 1) return;

        const touch = event.touches[0];
        rememberSwipeStart(touch.clientX, touch.clientY);
    }, { capture: true, passive: true });

    document.addEventListener('touchend', (event) => {
        if (event.changedTouches.length !== 1) {
            swipeStart = null;
            return;
        }

        const touch = event.changedTouches[0];
        handleSwipeEnd(touch.clientX, touch.clientY);
    }, { capture: true, passive: true });

    // В современных браузерах Pointer Events надёжнее Touch Events.
    document.addEventListener('pointerdown', (event) => {
        if (event.pointerType !== 'touch' || window.innerWidth > 768) return;
        rememberSwipeStart(event.clientX, event.clientY);
    }, { capture: true, passive: true });

    document.addEventListener('pointerup', (event) => {
        if (event.pointerType !== 'touch') return;
        handleSwipeEnd(event.clientX, event.clientY);
    }, { capture: true, passive: true });

    document.addEventListener('touchcancel', () => {
        swipeStart = null;
    }, { capture: true, passive: true });

    sidebar.querySelectorAll('.sidebar-item').forEach(item => {
        item.addEventListener('click', () => {
            if (window.innerWidth <= 768) closeSidebar();
        });
    });

    window.addEventListener('resize', () => {
        if (window.innerWidth > 768) closeSidebar();
    });

    // Кнопка входа в header — показываем только если юзер НЕ авторизован
    function updateMobileAuthActions() {
        const isAuth = typeof Auth !== 'undefined' && Auth.isAuthenticated();
        [authBtn, registerBtn].forEach((button) => {
            if (button) button.style.display = isAuth ? 'none' : 'inline-flex';
        });
    }

    if (authBtn) {
        authBtn.addEventListener('click', () => {
            if (typeof Auth !== 'undefined') Auth.showAuthModal();
        });
    }

    if (registerBtn) {
        registerBtn.addEventListener('click', () => {
            if (typeof Auth !== 'undefined') Auth.showAuthModal('register');
        });
    }

    updateMobileAuthActions();

    // Переподписываемся на обновления состояния авторизации
    const originalUpdateUI = window.updateUI;
    window.updateUI = function (...args) {
        if (typeof originalUpdateUI === 'function') originalUpdateUI.apply(this, args);
        updateMobileAuthActions();
    };
})();
