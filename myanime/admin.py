from django.contrib import admin
from .models import AnimeTitle, UserAnimeList, Profile

# Register your models here.
@admin.register(AnimeTitle)
class AnimeTitleAdmin(admin.ModelAdmin):
    list_display = ('anilibria_id', 'name_ru', 'updated_at')
    search_fields = ('name_ru', 'code')

@admin.register(UserAnimeList)
class UserAnimeListAdmin(admin.ModelAdmin):
    list_display = ('user', 'anime', 'status')
    list_filter = ('status',)
    search_fields = ('user__username', 'anime__name_ru')

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'avatar', 'bio')
    search_fields = ('user__username', 'bio')
