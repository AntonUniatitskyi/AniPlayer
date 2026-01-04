from django.contrib import admin
from unfold.admin import ModelAdmin
from unfold.contrib.import_export.forms import ExportForm, ImportForm
from import_export.admin import ImportExportModelAdmin

from .models import AnimeTitle, UserAnimeList, Profile, Franchise
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
