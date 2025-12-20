import json

from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DetailView, ListView

from .models import AnimeTitle, Episode, EpisodeHistory, UserAnimeList

# Create your views here.


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
        context['last_episode_id'] = None
        context['last_timestamp'] = 0

        if self.request.user.is_authenticated:
            try:
                from .models import UserAnimeList
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


class UserLibraryView(ListView):
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
            time = data.get('time')

            if not episode_id or time is None:
                return JsonResponse({'status': 'error', 'message': 'Missing data'}, status=400)

            episode = Episode.objects.get(id=episode_id)
            history, created = EpisodeHistory.objects.update_or_create(
                user=request.user,
                episode=episode,
                defaults={'timestamp': time}
            )

            return JsonResponse({'status': 'ok'})
        except Episode.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Episode not found'}, status=404)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

    return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)
