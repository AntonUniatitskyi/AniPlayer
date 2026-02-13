import json

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from .models import AnimeTitle, Episode, EpisodeHistory, Profile, Subscription


class AnimeProjectTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='test_anton', password='password123')
        self.client = Client()
        self.anime = AnimeTitle.objects.create(
            name_ru="Тестовое аниме",
            code="test-anime",
            shikimori_id=12345
        )

        self.episode = Episode.objects.create(
            anime=self.anime,
            ordinal=1
        )

    def test_profile_auto_creation(self):
        self.assertIsNotNone(self.user.profile)
        self.assertEqual(self.user.profile.user.username, 'test_anton')

    def test_anime_str(self):
        self.assertEqual(str(self.anime), "Тестовое аниме")

    def test_anime_list_view(self):
        # Убедись, что name='anime_list' в urls.py
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Тестовое аниме")

    def test_anime_detail_view(self):
        url = reverse('anime_detail', kwargs={'slug': self.anime.code})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['anime'], self.anime)

    def test_save_progress_api(self):
        self.client.login(username='test_anton', password='password123')
        url = reverse('save_progress')

        data = {
            'episode_id': self.episode.id,
            'time': 120  # Остановился на 120-й секунде
        }

        response = self.client.post(
            url,
            data=json.dumps(data),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        history = EpisodeHistory.objects.get(
            user=self.user, episode=self.episode)
        self.assertEqual(history.timestamp, 120)

    def test_toggle_subscription_no_telegram(self):
        self.client.login(username='test_anton', password='password123')
        url = reverse('toggle_subscription')

        data = {'anime_slug': self.anime.code}
        response = self.client.post(
            url,
            data=json.dumps(data),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('Сначала привяжите Telegram', response.json()['message'])

    def test_toggle_subscription_success(self):
        profile = self.user.profile
        profile.telegram_id = "123456789"
        profile.save()

        self.client.login(username='test_anton', password='password123')
        url = reverse('toggle_subscription')
        data = {'anime_slug': self.anime.code}

        import unittest.mock as mock
        with mock.patch('requests.post') as mocked_post:
            response = self.client.post(
                url,
                data=json.dumps(data),
                content_type='application/json'
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['status'], 'subscribed')
            self.assertTrue(Subscription.objects.filter(
                user=self.user, anime=self.anime).exists())
