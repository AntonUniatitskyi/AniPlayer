const CACHE_NAME = 'anime-app-v1';
const ASSETS_TO_CACHE = [
    '/',
    '/static/css/style.css',  // Укажи путь к своим стилям
    '/static/js/main.js',     // Укажи путь к своим скриптам
    '/static/images/icons/icon-192.png'
];

// 1. Установка: Кэшируем статику (оболочку сайта)
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME)
        .then((cache) => cache.addAll(ASSETS_TO_CACHE))
    );
});

// 2. Активация: Удаляем старые кэши при обновлении версии
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keyList) => {
            return Promise.all(keyList.map((key) => {
                if (key !== CACHE_NAME) {
                    return caches.delete(key);
                }
            }));
        })
    );
});

// 3. Перехват запросов (Стратегия: Network First)
// Сначала пробуем интернет, если нет — берем из кэша.
// Для видео это важно, чтобы не забить память телефона кэшем mp4 файлов.
self.addEventListener('fetch', (event) => {
    // Игнорируем запросы к админке и видео-потокам
    if (event.request.url.includes('/admin') || event.request.url.includes('/stream')) {
        return;
    }

    event.respondWith(
        fetch(event.request)
        .catch(() => {
            return caches.match(event.request);
        })
    );
});
