from django.contrib.auth.models import User
from django.db import models


# Create your models here.
class AnimeTitle(models.Model):
    anilibria_id = models.IntegerField(
        unique=True, verbose_name="Anilibria ID")

    code = models.CharField(max_length=255, verbose_name="Код (slug)")
    name_ru = models.CharField(
        max_length=255, verbose_name="Название (русское)")
    name_en = models.CharField(
        max_length=255, verbose_name="Название (английское)", blank=True, null=True)
    description = models.TextField(verbose_name="Описание", blank=True)
    poster_path = models.CharField(
        max_length=500, verbose_name="Путь к постеру", blank=True)
    player_url = models.CharField(
        max_length=500, verbose_name="Ссылка на плеер", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name_ru

    class Meta:
        verbose_name = "Аниме тайтл"
        verbose_name_plural = "Аниме тайтлы"


class Episode(models.Model):
    anime = models.ForeignKey(
        AnimeTitle, on_delete=models.CASCADE, related_name='episodes')
    ordinal = models.IntegerField()
    hls_480 = models.URLField(max_length=500, blank=True, null=True)
    hls_720 = models.URLField(max_length=500, blank=True, null=True)
    hls_1080 = models.URLField(max_length=500, blank=True, null=True)
    skip_op_start = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="Начало опенинга")
    skip_op_end = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="Конец опенинга")

    skip_ed_start = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="Начало эндинга")
    skip_ed_end = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="Конец эндинга")

    class Meta:
        ordering = ['ordinal']
        unique_together = ['anime', 'ordinal']

    def __str__(self):
        return f"{self.anime.name_ru} - Эпизод {self.ordinal}"


class UserAnimeList(models.Model):
    STATUS_CHOICES = [
        ('watching', 'Смотрю'),
        ('planned', 'В планах'),
        ('completed', 'Просмотрено'),
        ('dropped', 'Брошено'),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='library')
    anime = models.ForeignKey(
        AnimeTitle, on_delete=models.CASCADE, related_name='in_libraries')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'anime']
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.user.username} - {self.anime.name_ru} ({self.status})"


class EpisodeHistory(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='history')
    episode = models.ForeignKey(Episode, on_delete=models.CASCADE)

    # Сохраняем секунду остановки
    timestamp = models.PositiveIntegerField(
        default=0, verbose_name="Остановился на (сек)")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        unique_together = ['user', 'episode']

    def __str__(self):
        return f"{self.user} -> {self.episode} ({self.timestamp}s)"
