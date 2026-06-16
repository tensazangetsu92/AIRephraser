/* ========================================
   МОБИЛЬНОЕ МЕНЮ — добавить в main.js или подключить отдельно
   ======================================== */

(function () {
    // Создаём кнопку-гамбургер
    const menuBtn = document.createElement('button');
    menuBtn.className = 'mobile-menu-btn';
    menuBtn.setAttribute('aria-label', 'Открыть меню');
    menuBtn.innerHTML = '<i class="fas fa-bars"></i>';
    document.body.appendChild(menuBtn);

    // Создаём оверлей
    const overlay = document.createElement('div');
    overlay.className = 'sidebar-overlay';
    document.body.appendChild(overlay);

    const sidebar = document.querySelector('.sidebar');

    function openSidebar() {
        overlay.style.display = 'block';
        // небольшая задержка чтобы transition сработал
        requestAnimationFrame(() => overlay.classList.add('visible'));
        sidebar.classList.add('mobile-open');
        overlay.classList.add('visible');
        menuBtn.innerHTML = '<i class="fas fa-times"></i>';
        document.body.style.overflow = 'hidden'; // блокируем скролл фона
    }

    function closeSidebar() {
        overlay.classList.remove('visible');
        overlay.addEventListener('transitionend', () => {
            overlay.style.display = 'none';
        }, { once: true });
        sidebar.classList.remove('mobile-open');
        overlay.classList.remove('visible');
        menuBtn.innerHTML = '<i class="fas fa-bars"></i>';
        document.body.style.overflow = '';
    }

    menuBtn.addEventListener('click', () => {
        sidebar.classList.contains('mobile-open') ? closeSidebar() : openSidebar();
    });

    overlay.addEventListener('click', closeSidebar);

    // Закрываем при клике на пункт меню (навигация)
    sidebar.querySelectorAll('.sidebar-item').forEach(item => {
        item.addEventListener('click', () => {
            if (window.innerWidth <= 768) closeSidebar();
        });
    });

    // При ресайзе до десктопа — сбрасываем состояние
    window.addEventListener('resize', () => {
        if (window.innerWidth > 768) {
            closeSidebar();
        }
    });
})();