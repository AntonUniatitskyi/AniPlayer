from django.contrib.auth.models import User, Group
from django.utils import timezone
from datetime import timedelta

# 🔥 ВАЖНО: Импортируй свои модели.
# Проверь, правильно ли написаны пути (myanime - имя приложения, AnimeTitle - имя класса модели)
try:
    from myanime.models import AnimeTitle
except ImportError:
    AnimeTitle = None  # Заглушка, если модель не найдена или называется иначе

def dashboard_callback(request, context):
    # 1. Получаем текущее время для расчета "новых за неделю"
    now = timezone.now()
    week_ago = now - timedelta(days=7)
    day_ago = now - timedelta(days=1)

    # 2. Считаем ПОЛЬЗОВАТЕЛЕЙ
    total_users = User.objects.count()
    # Считаем, сколько зарегистрировалось за последние 24 часа
    new_users_today = User.objects.filter(date_joined__gte=day_ago).count()

    # 3. Считаем АНИМЕ (с проверкой, чтобы не упало, если модели нет)
    if AnimeTitle:
        total_anime = AnimeTitle.objects.count()
        # Попробуем посчитать обновленные/добавленные за неделю
        # Если у тебя поле называется не 'updated_at', а иначе - поправь тут
        try:
            new_anime_week = AnimeTitle.objects.filter(updated_at__gte=week_ago).count()
        except Exception:
            new_anime_week = 0 # Если поля updated_at нет
    else:
        total_anime = 0
        new_anime_week = 0

    # 4. Формируем карточки
    context.update({
        "kpi": [
            {
                "title": "Всего аниме",
                "value": total_anime,
                "icon": "movie",
                "color": "text-purple-500",
                "trend": f"+{new_anime_week} обновлено", # Реальная цифра
            },
            {
                "title": "Пользователи",
                "value": total_users,
                "icon": "person",
                "color": "text-blue-500",
                "trend": f"+{new_users_today} сегодня", # Реальная цифра
            },
            {
                "title": "Группы прав",
                "value": Group.objects.count(),
                "icon": "shield",
                "color": "text-green-500",
                "trend": "Активны",
            },
        ],
        # Убираем стандартный список (он скрыт в CSS, но тут тоже можно очистить для надежности)
        # НО! Не пиши "available_apps": [], иначе пропадут права доступа!
    })

    return context
