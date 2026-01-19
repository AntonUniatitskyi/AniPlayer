from django.db.models.signals import post_save
from django.dispatch import receiver
import requests
from django.core.cache import cache
from .models import Episode, Subscription, WatchLog
from decouple import config

@receiver(post_save, sender=Episode)
def notify_subscribers(sender, instance, created, **kwargs):

    if created:
        print("--- ЭТО НОВАЯ СЕРИЯ (Created=True) ---")
        anime = instance.anime
        subscribers = Subscription.objects.filter(anime=anime)
        print(f"--- НАЙДЕНО ПОДПИСЧИКОВ: {subscribers.count()} ---")

        if not subscribers.exists():
            print("--- НЕТ ПОДПИСЧИКОВ, ВЫХОДИМ ---")
            return

        try:
            site_url = config('SITE_URL')
        except:
            site_url = "http://127.0.0.1:8000"

        message = (
            f"🔥 <b>Вышла новая серия!</b>\n\n"
            f"📺 <b>{anime.name_ru}</b>\n"
            f"🎬 Эпизод {instance.ordinal}\n\n"
            f"👉 <a href='{site_url}/anime/{anime.code}'>Смотреть прямо сейчас</a>"
        )

        token = config('TG_BOT_TOKEN')
        url = f"https://api.telegram.org/bot{token}/sendMessage"

        for sub in subscribers:
            if not hasattr(sub.user, 'profile'):
                print(f"--- ОШИБКА: У юзера {sub.user.username} нет профиля ---")
                continue

            tg_id = sub.user.profile.telegram_id
            print(f"--- ПОПЫТКА ОТПРАВКИ ЮЗЕРУ {sub.user.username} (ID: {tg_id}) ---")

            if tg_id:
                try:
                    payload = {
                        "chat_id": tg_id,
                        "text": message,
                        "parse_mode": "HTML"
                    }
                    response = requests.post(url, data=payload, timeout=5)
                    print(f"--- ОТВЕТ TELEGRAM: {response.status_code} {response.text} ---")
                except Exception as e:
                    print(f"--- ОШИБКА ОТПРАВКИ: {e} ---")
            else:
                print("--- У ЮЗЕРА НЕТ TELEGRAM ID ---")

@receiver(post_save, sender=WatchLog)
def clear_user_cache(sender, instance, **kwargs):
    cache_key = f'wrapped_stats_{instance.user.id}'
    cache.delete(cache_key)
