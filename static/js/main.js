/* static/js/main.js */

document.addEventListener('DOMContentLoaded', () => {

    // 1. Инициализация переменных и глобальных функций
    const themeBtn = document.getElementById('themeBtn');
    const body = document.body;
    let sliderInstance = null; // Храним слайдер здесь

    // --- ФУНКЦИИ ТЕМЫ ---
    function initTheme() {
        const savedTheme = localStorage.getItem('theme');
        if (savedTheme === 'light') {
            body.classList.add('light-theme');
            updatePwaThemeColor(true);
        }
    }

    function updatePwaThemeColor(isLight) {
        const color = isLight ? '#ffffff' : '#1a1a1a';
        document.querySelectorAll('meta[name="theme-color"]').forEach(meta => {
            meta.setAttribute('content', color);
            meta.removeAttribute('media');
        });
    }

    if (themeBtn) {
        themeBtn.addEventListener('click', () => {
            const isLight = body.classList.toggle('light-theme');
            localStorage.setItem('theme', isLight ? 'light' : 'dark');
            updatePwaThemeColor(isLight);
        });
    }

    // --- ФУНКЦИИ ПОИСКА И UI ---
    window.toggleMobileSearch = function() {
        const panel = document.getElementById('mobileSearchPanel');
        const input = panel.querySelector('input');
        const isActive = panel.classList.toggle('active');
        if (isActive) setTimeout(() => input.focus(), 100);
        else input.blur();
    }

    document.addEventListener('click', function(e) {
        const panel = document.getElementById('mobileSearchPanel');
        const btn = document.querySelector('button[onclick="toggleMobileSearch()"]');
        if (panel && panel.classList.contains('active') && !panel.contains(e.target) && !btn.contains(e.target)) {
            panel.classList.remove('active');
        }
    });

    window.showToast = function(message, type = 'normal') {
        const container = document.getElementById('toast-container');
        if(!container) return;
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        let icon = type === 'success' ? '✅' : (type === 'error' ? '❌' : 'ℹ️');
        toast.innerHTML = `<span class="toast-icon">${icon}</span> <span>${message}</span>`;
        toast.onclick = () => toast.remove();
        container.appendChild(toast);
        setTimeout(() => toast.remove(), 3000);
    }

    // --- ФУНКЦИЯ ЗАПУСКА ВСЕГО (InitGlobalScripts) ---
    // Запускается при первой загрузке и после каждого перехода Swup
    function initGlobalScripts() {
        window.scrollTo(0, 0);
        updateActiveMenu();
        initDesktopSearch();

        // ЗАПУСК СЛАЙДЕРА (берем функцию из slider.js)
        if (window.initHeroSlider) {
            // Если старый экземпляр жив - убиваем перед созданием нового
            if (sliderInstance && typeof sliderInstance.destroy === 'function') {
                sliderInstance.destroy();
            }
            sliderInstance = window.initHeroSlider();
        }
    }

    function updateActiveMenu() {
        const currentPath = window.location.pathname;
        const navItems = document.querySelectorAll('.mobile-bottom-nav .nav-item');
        navItems.forEach(item => {
            item.classList.remove('active');
            const link = item.getAttribute('href');
            if (link && (link === currentPath || (link !== '/' && currentPath.startsWith(link)))) {
                item.classList.add('active');
            }
        });
    }

    function initDesktopSearch() {
        const searchInput = document.getElementById('searchInput');
        const searchResults = document.getElementById('searchResults');
        let debounceTimer;

        if (searchInput && searchResults) {
            const newInput = searchInput.cloneNode(true);
            searchInput.parentNode.replaceChild(newInput, searchInput);

            newInput.addEventListener('input', function() {
                const query = this.value.trim();
                clearTimeout(debounceTimer);
                if (query.length < 2) {
                    searchResults.classList.remove('active');
                    searchResults.innerHTML = '';
                    return;
                }
                debounceTimer = setTimeout(() => {
                    fetch(`/api/search/?q=${encodeURIComponent(query)}`)
                        .then(r => r.json())
                        .then(data => {
                            searchResults.innerHTML = '';
                            if (data.results.length > 0) {
                                data.results.forEach(anime => {
                                    const html = `
                                        <a href="/anime/${anime.slug}/" class="search-result-item">
                                            <img src="${anime.poster || ''}" alt="${anime.name}">
                                            <div class="result-info">
                                                <div class="result-title">${anime.name}</div>
                                                <div class="result-hint">Перейти к просмотру</div>
                                            </div>
                                        </a>`;
                                    searchResults.insertAdjacentHTML('beforeend', html);
                                });
                                searchResults.classList.add('active');
                            } else {
                                searchResults.innerHTML = '<div class="no-results">Ничего не найдено 😔</div>';
                                searchResults.classList.add('active');
                            }
                        });
                }, 300);
            });

            document.addEventListener('click', function(e) {
                if (!newInput.contains(e.target) && !searchResults.contains(e.target)) {
                    searchResults.classList.remove('active');
                }
            });
        }
    }

    // --- НАСТРОЙКА SWUP ---
    const swup = new Swup({
        containers: ["#swup"],
        cache: true,
        animationSelector: '[class*="transition-fade"]',
        plugins: [new SwupScriptsPlugin({
            head: true,
            body: true
        })]
    });

    // ХУК: ПЕРЕД уходом со страницы
    swup.hooks.before('content:replace', () => {
        // Убиваем плеер
        if (window.player && typeof window.player.destroy === 'function') {
            window.player.destroy();
            window.player = null;
        }
        // Убиваем слайдер
        if (sliderInstance && typeof sliderInstance.destroy === 'function') {
            sliderInstance.destroy();
            sliderInstance = null;
        }
        // Прячем поиск
        const panel = document.getElementById('mobileSearchPanel');
        if (panel) panel.classList.remove('active');
    });

    // ХУК: ПОСЛЕ загрузки новой страницы
    swup.hooks.on('content:replace', () => {
        initGlobalScripts();
    });

    // --- ПЕРВИЧНЫЙ ЗАПУСК ---
    initTheme();
    initGlobalScripts();

    // PWA Service Worker
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/sw.js').catch(err => console.log('SW failed:', err));
    }

    // Mobile Navbar Hide/Show on Scroll
    let lastScrollY = window.scrollY;
    const bottomNav = document.querySelector('.mobile-bottom-nav');
    window.addEventListener('scroll', () => {
        if (!bottomNav) return;
        const currentScrollY = window.scrollY;
        if (currentScrollY > lastScrollY && currentScrollY > 100) {
            bottomNav.style.transform = 'translateY(100%)';
        } else {
            bottomNav.style.transform = 'translateY(0)';
        }
        lastScrollY = currentScrollY;
    }, { passive: true });

    // Показываем контент (анимация загрузки)
    document.body.classList.add('loaded');
});
