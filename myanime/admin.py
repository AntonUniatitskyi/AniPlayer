from django.contrib import admin
from unfold.admin import ModelAdmin
from unfold.contrib.import_export.forms import ExportForm, ImportForm
from import_export.admin import ImportExportModelAdmin

from .models import AnimeTitle, UserAnimeList, Profile, Franchise, WatchLog, Episode
# Если создал файл resources.py (как я советовал выше), импортируй его:
from .resources import AnimeTitleResource

@admin.register(AnimeTitle)
class AnimeTitleAdmin(ImportExportModelAdmin, ModelAdmin):
    resource_classes = [AnimeTitleResource] # Раскомментируй, когда создашь ресурс
    import_form_class = ImportForm
    export_form_class = ExportForm

    list_display = ('anilibria_id', 'name_ru', 'updated_at')
    search_fields = ('name_ru', 'code')
    list_filter = ('kind', 'year') # Добавил полезные фильтры для аниме

@admin.register(UserAnimeList)
class UserAnimeListAdmin(ImportExportModelAdmin, ModelAdmin):
    import_form_class = ImportForm
    export_form_class = ExportForm

    list_display = ('user', 'anime', 'status')
    list_filter = ('status',)
    search_fields = ('user__username', 'anime__name_ru')

@admin.register(Profile)
class ProfileAdmin(ModelAdmin): # Для профилей экспорт обычно не нужен, оставим просто Unfold
    list_display = ('user', 'avatar', 'bio')
    search_fields = ('user__username', 'bio')

@admin.register(Franchise)
class FranchiseAdmin(ImportExportModelAdmin, ModelAdmin):
    import_form_class = ImportForm
    export_form_class = ExportForm

    list_display = ('name',)
    search_fields = ('name',)

@admin.register(WatchLog)
class WatchLogAdmin(admin.ModelAdmin):
    pass


@admin.register(Episode)
class EpisodeAdmin(ImportExportModelAdmin):
    # Что отображать в списке всех эпизодов
    list_display = ('anime_name', 'ordinal', 'has_1080', 'op_info')

    # Фильтры справа (очень помогут найти нужный тайтл)
    list_filter = ('anime__name_ru', 'anime__year')

    # Поиск (ищем по названию аниме или номеру серии)
    search_fields = ('anime__name_ru', 'anime__name_en', 'ordinal')

    # Группировка полей при редактировании для красоты
    fieldsets = (
        (None, {
            'fields': ('anime', 'ordinal')
        }),
        ('Видео потоки (HLS)', {
            'fields': ('hls_1080', 'hls_720', 'hls_480'),
            'description': 'Ссылки на m3u8 плейлисты'
        }),
        ('Таймкоды (в секундах)', {
            'classes': ('collapse',), # Скрыть по умолчанию
            'fields': (
                ('skip_op_start', 'skip_op_end'),
                ('skip_ed_start', 'skip_ed_end')
            ),
        }),
    )

    # Кастомные методы для list_display
    def anime_name(self, obj):
        return obj.anime.name_ru
    anime_name.short_description = 'Аниме'

    def has_1080(self, obj):
        return bool(obj.hls_1080)
    has_1080.boolean = True
    has_1080.short_description = '1080p'

    def op_info(self, obj):
        if obj.skip_op_start and obj.skip_op_end:
            return f"{obj.skip_op_start}s - {obj.skip_op_end}s"
        return "-"
    op_info.short_description = 'Опенинг'
