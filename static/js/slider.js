/* static/js/slider.js */

// Объявляем функцию глобально через window, чтобы main.js ее видел
window.initHeroSlider = function() {
    const slides = document.querySelectorAll('.hero-slide');

    // Если на странице нет слайдов, выходим и возвращаем null
    if (slides.length === 0) return null;

    let slideIndex = 0;
    let timer;
    let touchStartX = 0;
    const container = document.querySelector('.hero-container');

    // 1. Создание точек
    let dotsContainer = document.querySelector('.hero-dots');
    if (!dotsContainer && container) {
        dotsContainer = document.createElement('div');
        dotsContainer.className = 'hero-dots';
        container.appendChild(dotsContainer);

        slides.forEach((_, i) => {
            const dot = document.createElement('div');
            dot.className = i === 0 ? 'dot active' : 'dot';
            dot.addEventListener('click', () => showSlide(i));
            dotsContainer.appendChild(dot);
        });
    }
    const dots = document.querySelectorAll('.dot');

    // 2. Логика
    function showSlide(n) {
        slideIndex = (n + slides.length) % slides.length;
        slides.forEach(s => s.classList.remove('active'));
        dots.forEach(d => d.classList.remove('active'));
        slides[slideIndex].classList.add('active');
        if (dots[slideIndex]) dots[slideIndex].classList.add('active');
        resetTimer();
    }

    function nextSlide() { showSlide(slideIndex + 1); }

    function resetTimer() {
        clearInterval(timer);
        timer = setInterval(nextSlide, 5000);
    }

    // 3. Тач/Свайпы
    const handleTouchStart = (e) => { touchStartX = e.changedTouches[0].screenX; };
    const handleTouchEnd = (e) => {
        if (touchStartX - e.changedTouches[0].screenX > 50) nextSlide();
        if (e.changedTouches[0].screenX - touchStartX > 50) showSlide(slideIndex - 1);
    };

    if (container) {
        container.addEventListener('touchstart', handleTouchStart, { passive: true });
        container.addEventListener('touchend', handleTouchEnd, { passive: true });
    }

    resetTimer();

    // 4. Возвращаем метод для очистки (чтобы Swup мог убить таймер)
    return {
        destroy: () => {
            clearInterval(timer);
            if (container) {
                container.removeEventListener('touchstart', handleTouchStart);
                container.removeEventListener('touchend', handleTouchEnd);
            }
        }
    };
};
