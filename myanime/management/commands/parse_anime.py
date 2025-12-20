from django.core.management.base import BaseCommand

from myanime.services import fetch_anilibria_updates


class Command(BaseCommand):
    help = 'Загружает обновления с Anilibria'

    def add_arguments(self, parser):
        parser.add_argument('--all', action='store_true',
                            help='Скачать всю базу (займет много времени)')

    def handle(self, *args, **options):
        full_load = options['all']

        if full_load:
            self.stdout.write(
                "🌍 ЗАПУСК ПОЛНОЙ ЗАГРУЗКИ БАЗЫ (Это может занять 1-2 часа)...")
        else:
            self.stdout.write("🌍 Быстрая проверка новинок (5 страниц)...")

        try:
            new_count, updated_count = fetch_anilibria_updates(
                full_load=full_load)

            self.stdout.write(self.style.SUCCESS(
                f"✅ Готово! Добавлено аниме: {new_count}, Обновлено аниме: {updated_count}"
            ))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Произошла ошибка: {e}"))
