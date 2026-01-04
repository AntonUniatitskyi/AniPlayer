from import_export import resources, fields
from import_export.widgets import ManyToManyWidget
from .models import AnimeTitle, Genre

class AnimeTitleResource(resources.ModelResource):
    # Пример кастомного поля для ManyToMany (Жанры)
    genres = fields.Field(
        column_name='genres',
        attribute='genres',
        widget=ManyToManyWidget(Genre, field='name', separator=', ')
    )

    class Meta:
        model = AnimeTitle
        # Список полей, которые пойдут в файл
        fields = ('id', 'anilibria_id', 'name_ru', 'year', 'kind_ru', 'genres')
        export_order = fields
