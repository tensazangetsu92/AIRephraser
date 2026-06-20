(function () {
    const menuBtn = document.getElementById('mobileHeaderToggle');
    const authBtn = document.getElementById('mobileHeaderAuth');
    const sidebar = document.querySelector('.sidebar');

    if (!menuBtn || !sidebar) return;

    const overlay = document.createElement('div');
    overlay.className = 'sidebar-overlay';
    document.body.appendChild(overlay);

    function openSidebar() {
        overlay.style.display = 'block';
        requestAnimationFrame(() => overlay.classList.add('visible'));
        sidebar.classList.add('mobile-open');
        menuBtn.innerHTML = '<i class="fas fa-times"></i>';
        document.body.style.overflow = 'hidden';
    }

    function closeSidebar() {
        sidebar.classList.remove('mobile-open');
        overlay.classList.remove('visible');
        overlay.addEventListener('transitionend', () => {
            overlay.style.display = 'none';
        }, { once: true });
        menuBtn.innerHTML = '<i class="fas fa-bars"></i>';
        document.body.style.overflow = '';
    }

    const closeBtn = document.getElementById('sidebarMobileClose');
    if (closeBtn) {
        closeBtn.addEventListener('click', closeSidebar);
    }

    menuBtn.addEventListener('click', () => {
        sidebar.classList.contains('mobile-open') ? closeSidebar() : openSidebar();
    });

    overlay.addEventListener('click', closeSidebar);

    sidebar.querySelectorAll('.sidebar-item').forEach(item => {
        item.addEventListener('click', () => {
            if (window.innerWidth <= 768) closeSidebar();
        });
    });

    window.addEventListener('resize', () => {
        if (window.innerWidth > 768) closeSidebar();
    });

    // Кнопка входа в header — показываем только если юзер НЕ авторизован
    function updateMobileAuthButton() {
        if (!authBtn) return;
        const isAuth = typeof Auth !== 'undefined' && Auth.isAuthenticated();
        authBtn.style.display = isAuth ? 'none' : 'block';
    }

    if (authBtn) {
        authBtn.addEventListener('click', () => {
            if (typeof Auth !== 'undefined') Auth.showAuthModal();
        });
    }

    updateMobileAuthButton();

    // Переподписываемся на обновления состояния авторизации
    const originalUpdateUI = window.updateUI;
    window.updateUI = function (...args) {
        if (typeof originalUpdateUI === 'function') originalUpdateUI.apply(this, args);
        updateMobileAuthButton();
    };
})();