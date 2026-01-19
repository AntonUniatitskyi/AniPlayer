import logging
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from django_apscheduler.jobstores import DjangoJobStore
from django_apscheduler import util
from django_apscheduler.models import DjangoJobExecution
import requests
from decouple import config
import sys
import io

# Принудительно переключаем вывод терминала в UTF-8
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

logger = logging.getLogger(__name__)

def send_admin_alert(error_message):
    """Отправляет сообщение об ошибке администратору в Telegram"""
    token = config('TG_BOT_TOKEN')
    # Твой личный ID в Telegram (можно узнать у @userinfobot)
    admin_id = config('ADMIN_TG_ID')

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    text = f"❌ <b>Ошибка планировщика!</b>\n\nКоманда: <code>parse_anime</code>\nОшибка: <code>{error_message}</code>"

    try:
        requests.post(url, data={"chat_id": admin_id, "text": text, "parse_mode": "HTML"}, timeout=5)
    except Exception as e:
        print(f"Не удалось отправить уведомление: {e}")

def run_full_anime_loader():
    """Задача для запуска ПОЛНОЙ загрузки базы"""
    logger.info("--- ЗАПУСК ПОЛНОЙ ЗАГРУЗКИ АНИМЕ (каждые 30 мин) ---")
    try:
        # ВАЖНО: здесь должно быть 'parse_anime', так как ваш файл называется parse_anime.py
        call_command('parse_anime', all=True)
        logger.info("--- Полная загрузка успешно завершена ---")
    except Exception as e:
        logger.error(f"❌ Ошибка при выполнении полной загрузки: {e}")

@util.close_old_connections
def delete_old_job_executions(max_age=604_800):
    DjangoJobExecution.objects.delete_old_job_executions(max_age)

class Command(BaseCommand):
    help = "Запускает APScheduler для полной загрузки аниме."

    def handle(self, *args, **options):
        scheduler = BlockingScheduler(timezone=settings.TIME_ZONE)
        scheduler.add_jobstore(DjangoJobStore(), "default")

        scheduler.add_job(
            run_full_anime_loader,
            trigger=IntervalTrigger(minutes=30),
            id="full_anilibria_loader_job",
            max_instances=1,
            replace_existing=True,
        )

        scheduler.add_job(
            delete_old_job_executions,
            trigger=IntervalTrigger(days=7),
            id="delete_old_job_executions",
            max_instances=1,
            replace_existing=True,
        )

        try:
            logger.info("Планировщик запущен...")
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("Планировщик остановлен.")
            scheduler.shutdown()
