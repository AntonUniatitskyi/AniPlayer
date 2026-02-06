import json

from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.db.models import Q, Count, Sum
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST, require_GET
from django.views.generic import CreateView, DetailView, ListView
from django.contrib import messages
import requests
from django.core.cache import cache
from .forms import ProfileUpdateForm, UserUpdateForm
from decouple import config
from django.db.models import Count
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models.functions import ExtractHour
from anime_parsers_ru import KodikParser

from .models import AnimeTitle, Episode, EpisodeHistory, UserAnimeList, Profile, Subscription, WatchLog

# Create your views here.

@login_required
@require_POST
def toggle_subscription(request):
    data = json.loads(request.body)
    anime_slug = data.get('anime_slug')
    user_profile = getattr(request.user, 'profile', None)

    if not user_profile or not user_profile.telegram_id:
        return JsonResponse({
            'status': 'error',
            'message': 'Сначала привяжите Telegram в настройках!'
        }, status=400)

    try:
        anime = AnimeTitle.objects.get(code=anime_slug)
        sub, created = Subscription.objects.get_or_create(user=request.user, anime=anime)

        if not created:
            sub.delete()
            return JsonResponse({'status': 'unsubscribed'})
        else:
            send_subscription_confirmation(user_profile.telegram_id, anime)

            return JsonResponse({'status': 'subscribed'})

    except AnimeTitle.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Аниме не найдено'}, status=404)

def send_subscription_confirmation(chat_id, anime):
    token = config('TG_BOT_TOKEN')
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    try:
        site_url = config('SITE_URL', default='http://127.0.0.1:8000')
    except:
        site_url = "http://127.0.0.1:8000"

    anime_link = f"{site_url}/anime/{anime.code}"

    message = (
        f"🔔 <b>Подписка оформлена!</b>\n\n"
        f"Вы успешно подписались на обновления:\n"
        f"📺 <b>{anime.name_ru}</b>\n\n"
        f"Бот пришлет уведомление, как только выйдет новая серия."
    )

    keyboard = {
        "inline_keyboard": [
            [
                {"text": "🎬 Открыть на сайте", "url": anime_link}
            ]
        ]
    }

    try:
        requests.post(url, data={
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
            "reply_markup": json.dumps(keyboard)  # <--- МАГИЯ ЗДЕСЬ
        }, timeout=2)
    except Exception as e:
        print(f"Ошибка отправки подтверждения: {e}")

def search_anime_api(request):
    query = request.GET.get('q', '')
    if len(query) < 2:
        return JsonResponse({'results': []})

    results = AnimeTitle.objects.filter(name_ru__icontains=query)[:5]

    data = []
    for anime in results:
        data.append({
            'name': anime.name_ru,
            'poster': anime.poster_path,
            'slug': anime.code
        })

    return JsonResponse({'results': data})


class AnimeTitleListView(ListView):
    model = AnimeTitle
    template_name = "anime_list.html"
    context_object_name = 'anime_list'
    ordering = ['-updated_at']
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset()
        query = self.request.GET.get('q')

        if query:
            queryset = queryset.filter(
                Q(name_ru__icontains=query) |
                Q(name_en__icontains=query)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Если пользователь залогинен - достаем его историю
        context['slider_anime'] = AnimeTitle.objects.filter(
            poster_path__isnull=False
        ).exclude(poster_path='').order_by('-updated_at')[:5]
        if self.request.user.is_authenticated:
            raw_history = EpisodeHistory.objects.filter(
                user=self.request.user
            ).select_related('episode__anime').order_by('-updated_at')[:50]

            unique_history = []
            seen_anime_ids = set()

            for item in raw_history:
                anime = item.episode.anime

                if anime.id not in seen_anime_ids:
                    unique_history.append(item)
                    seen_anime_ids.add(anime.id)

                if len(unique_history) == 5:
                    break
            context['history'] = unique_history
        return context


class AnimeTitleDetailView(DetailView):
    model = AnimeTitle
    template_name = "anime_detail.html"
    context_object_name = 'anime'
    slug_url_kwarg = 'slug'
    slug_field = 'code'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        anime = self.object
        # Берем жанры текущего аниме
        anime_genres = anime.genres.all()
        franchise_releases = []
        if anime.franchise:
            # Берем все тайтлы этой франшизы, сортируем по полю franchise_order или году
            franchise_releases = anime.franchise.releases.all().order_by('franchise_order', 'updated_at')


        # Ищем совпадения
        similar_anime = AnimeTitle.objects.filter(genres__in=anime_genres)\
            .exclude(id=anime.id)\
            .annotate(same_genres=Count('genres'))\
            .order_by('-same_genres', '-updated_at')\
            .distinct()[:6]

        context['franchise_releases'] = franchise_releases
        context['similar_anime'] = similar_anime
        context['last_episode_id'] = None
        context['last_timestamp'] = 0
        context['is_subscribed'] = False
        if self.request.user.is_authenticated:
            context['is_subscribed'] = Subscription.objects.filter(
                user=self.request.user,
                anime=self.object
            ).exists()

        if self.request.user.is_authenticated:
            try:
                user_list = UserAnimeList.objects.get(
                    user=self.request.user,
                    anime=self.object
                )
                context['user_status'] = user_list.status
            except UserAnimeList.DoesNotExist:
                context['user_status'] = None

            try:
                from .models import EpisodeHistory

                last_history = EpisodeHistory.objects.filter(
                    user=self.request.user,
                    episode__anime=self.object
                ).select_related('episode').order_by('-updated_at').first()

                if last_history:
                    context['last_episode_id'] = last_history.episode.id
                    context['last_timestamp'] = last_history.timestamp
            except Exception as e:
                print(f"Error fetching history: {e}")
        return context


class RegisterView(CreateView):
    form_class = UserCreationForm
    template_name = 'registration/register.html'
    success_url = reverse_lazy('login')


@login_required
@require_POST
def update_status(request):
    try:
        data = json.loads(request.body)
        anime_code = data.get('anime_slug')
        status = data.get('status')

        anime = AnimeTitle.objects.get(code=anime_code)

        if not status or status == 'none':
            UserAnimeList.objects.filter(
                user=request.user, anime=anime).delete()
            return JsonResponse({'status': 'removed'})
        UserAnimeList.objects.update_or_create(
            user=request.user,
            anime=anime,
            defaults={'status': status}
        )
        return JsonResponse({'status': 'updated', 'new_status': status})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


class UserLibraryView(LoginRequiredMixin, ListView):
    template_name = 'library.html'
    context_object_name = 'library_items'

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return UserAnimeList.objects.none()
        return UserAnimeList.objects.filter(user=self.request.user).select_related('anime')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        items = self.get_queryset()
        context['watching'] = items.filter(status='watching')
        context['planned'] = items.filter(status='planned')
        context['completed'] = items.filter(status='completed')
        context['dropped'] = items.filter(status='dropped')

        from_anime_code = self.request.GET.get('from_anime')
        if from_anime_code:
            try:
                context['prev_anime'] = AnimeTitle.objects.get(
                    code=from_anime_code)
            except AnimeTitle.DoesNotExist:
                pass

        return context


@login_required
def save_progress(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            episode_id = data.get('episode_id')
            current_time = data.get('time')  # Время с плеера

            if not episode_id or current_time is None:
                return JsonResponse({'status': 'error', 'message': 'Missing data'}, status=400)

            episode = Episode.objects.select_related('anime').get(id=episode_id)

            # 1. Сначала просто ищем запись в истории
            history, created = EpisodeHistory.objects.get_or_create(
                user=request.user,
                episode=episode,
                defaults={'timestamp': current_time}
            )

            if not created:
                # 2. Если запись была, считаем разницу между "сейчас" и "тем что в базе"
                last_time = history.timestamp
                diff = current_time - last_time

                # 3. Логируем просмотр, только если разница положительная и небольшая
                # (чтобы не засчитывать перемотку или если вкладка была долго открыта)
                if 0 < diff < 300:
                    WatchLog.objects.create(
                        user=request.user,
                        anime=episode.anime,
                        episode_number=episode.ordinal,
                        seconds_watched=diff
                    )

                # 4. Обновляем время в истории
                history.timestamp = current_time
                history.save()

            return JsonResponse({'status': 'ok'})
        except Episode.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Episode not found'}, status=404)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

    return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)

@login_required
def settings_view(request):
    profile, created = Profile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        u_form = UserUpdateForm(request.POST, instance=request.user)
        p_form = ProfileUpdateForm(request.POST, request.FILES, instance=profile)

        if u_form.is_valid() and p_form.is_valid():
            u_form.save()
            p_form.save()
            messages.success(request, 'Настройки успешно сохранены!')
            return redirect('settings')
        else:
            messages.error(request, 'Ошибка при сохранении. Проверьте консоль.')
    else:
        u_form = UserUpdateForm(instance=request.user)
        p_form = ProfileUpdateForm(instance=profile)

    context = {
        'u_form': u_form,
        'p_form': p_form,
        'user': request.user
    }
    return render(request, 'settings.html', context)

@login_required
def start_telegram_auth(request):
    token = request.user.profile.generate_token()
    bot_name = "aniplayerbot"
    link = f"https://t.me/{bot_name}?start={token}"

    return redirect(link)

def finish_telegram_auth(request, token, chat_id):
    try:
        profile = Profile.objects.get(tg_auth_token=token)
        profile.telegram_id = chat_id
        profile.tg_auth_token = ""
        profile.save()

        messages.success(request, 'Telegram успешно привязан! ✈️')
    except Profile.DoesNotExist:
        messages.error(request, 'Ошибка привязки: неверный токен.')

    return redirect('settings')

def user_wrapped_view(request):
    return render(request, 'wrapped.html')

# 2. API (Считает тяжелую статистику)
@login_required
def wrapped_data_api(request):
    user = request.user
    cache_key = f'wrapped_stats_{user.id}'

    user_logs = WatchLog.objects.filter(user=user)

    # ПРОВЕРКА В КОНСОЛИ
    print(f"--- DEBUG FOR {user.username} ---")
    print(f"Количество записей в логе: {user_logs.count()}")

    if user_logs.count() == 0:
        return JsonResponse({'error': 'No data found'}, status=404)

    # Пытаемся достать готовый JSON из кэша
    data = cache.get(cache_key)

    if not data:
        print(f"⚡ Пересчет статистики для {user.username}...")

        # --- А. Общее время ---
        total_seconds = WatchLog.objects.filter(user=user)\
            .aggregate(Sum('seconds_watched'))['seconds_watched__sum'] or 0
        total_hours = round(total_seconds / 3600, 1)
        total_days = round(total_hours / 24, 1)

        # --- Б. Активность по часам (Заполняем все 24 часа) ---
        # Получаем данные из БД (только те часы, где есть просмотры)
        hours_qs = WatchLog.objects.filter(user=user)\
            .annotate(hour=ExtractHour('timestamp'))\
            .values('hour')\
            .annotate(count=Count('id'))\
            .order_by('hour')

        # Превращаем в словарь {0: 0, 1: 5, ... 23: 0}
        hours_dict = {h: 0 for h in range(24)}
        for entry in hours_qs:
            hours_dict[entry['hour']] = entry['count']

        chart_hours_labels = [f"{h:02d}:00" for h in range(24)]
        chart_hours_data = list(hours_dict.values())

        # Определяем "Сову" (если активность с 23 до 04 больше, чем днем)
        night_activity = sum([hours_dict[h] for h in [23, 0, 1, 2, 3, 4]])
        day_activity = sum(chart_hours_data) - night_activity
        is_owl = night_activity > (day_activity * 0.3) # Если ночью > 30% активности

        # --- В. Топ Жанров ---
        genres_qs = WatchLog.objects.filter(user=user)\
            .values('anime__genres__name')\
            .annotate(total=Count('id'))\
            .order_by('-total')[:5]

        chart_genres_labels = [item['anime__genres__name'] for item in genres_qs]
        chart_genres_data = [item['total'] for item in genres_qs]

        # --- Г. Любимое аниме (по количеству записей) ---
        top_anime_qs = WatchLog.objects.filter(user=user)\
            .values('anime__name_ru', 'anime__poster_path')\
            .annotate(total=Count('id'))\
            .order_by('-total').first()

        top_anime_title = top_anime_qs['anime__name_ru'] if top_anime_qs else "Пока пусто"
        top_anime_poster = top_anime_qs['anime__poster_path'] if top_anime_qs else ""

        # Формируем итоговый словарь
        data = {
            'total_hours': total_hours,
            'total_days': total_days,
            'is_owl': is_owl,
            'top_anime_title': top_anime_title,
            'top_anime_poster': top_anime_poster,

            # Данные для графиков
            'chart_hours_labels': chart_hours_labels,
            'chart_hours_data': chart_hours_data,
            'chart_genres_labels': chart_genres_labels,
            'chart_genres_data': chart_genres_data,
        }

        # Сохраняем в кэш на 24 часа
        cache.set(cache_key, data, 86400)
    else:
        print("🚀 Отдал данные из кэша (API)")

    return JsonResponse(data)


kodik_parser = KodikParser(validate_token=False)
@require_GET
def kodik_link(request, slug):
    try:
        anime = get_object_or_404(AnimeTitle, code=slug)
        episode_num = request.GET.get('episode', 1)
        translation_id = request.GET.get('translation', '0')
        # Получаем качество из запроса, по умолчанию 720
        requested_quality = int(request.GET.get('quality', 720))

        if not anime.shikimori_id:
            return JsonResponse({'error': 'No Shikimori ID linked'}, status=404)

        # Добавляем качество в ключ кэша
        cache_key = f"kodik_stream_{anime.shikimori_id}_ep_{episode_num}_q_{requested_quality}_tr_{translation_id}"
        cached_url = cache.get(cache_key)

        if cached_url:
            return JsonResponse({'url': cached_url, 'source': 'cache'})

        # Запрашиваем конкретное качество у Кодика
        link = kodik_parser.get_m3u8_playlist_link(
            id=str(anime.shikimori_id),
            id_type="shikimori",
            seria_num=int(episode_num),
            translation_id=translation_id,
            quality=requested_quality  # Передаем нужное качество сюда
        )

        if link:
            if link.startswith('//'):
                link = 'https:' + link
            cache.set(cache_key, link, timeout=7200)
            return JsonResponse({'url': link, 'source': 'api', 'quality': requested_quality})

        return JsonResponse({'error': 'Video not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@require_GET
def kodik_translations(request, slug):
    try:
        anime = get_object_or_404(AnimeTitle, code=slug)
        if not anime.shikimori_id:
            return JsonResponse({'error': 'No ID'}, status=404)

        cache_key = f"kodik_trans_{anime.shikimori_id}"
        cached_data = cache.get(cache_key)
        if cached_data:
            return JsonResponse({'translations': cached_data})

        info = kodik_parser.get_info(id=str(anime.shikimori_id), id_type="shikimori")

        if info and 'translations' in info:
            translations = info['translations']
            # translations — это список словарей: [{'id': '609', 'name': 'AniDUB', 'type': 'voice'}, ...]

            cache.set(cache_key, translations, timeout=43200) # 12 часов
            return JsonResponse({'translations': translations})

        return JsonResponse({'translations': []})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
