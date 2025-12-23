import requests
from django import forms
from django.contrib.auth.forms import PasswordResetForm
from django.conf import settings
from django.urls import reverse
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

class TelegramPasswordResetForm(PasswordResetForm):
    def save(self, domain_override=None, subject_template_name=None,
             email_template_name=None, use_https=False, token_generator=default_token_generator,
             from_email=None, request=None, html_email_template_name=None,
             extra_email_context=None):

        email = self.cleaned_data["email"]

        for user in self.get_users(email):
            if not hasattr(user, 'profile') or not user.profile.telegram_id:
                continue # Пропускаем, если нет привязки к ТГ

            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = token_generator.make_token(user)

            protocol = 'https' if use_https else 'http'
            domain = domain_override if domain_override else request.get_host()
            link = f"{protocol}://{domain}{reverse('password_reset_confirm', kwargs={'uidb64': uid, 'token': token})}"

            message = (
                f"🔐 <b>Запрос на сброс пароля</b>\n\n"
                f"Для пользователя: {user.username}\n"
                f"Нажмите на ссылку, чтобы задать новый пароль:\n\n"
                f"{link}\n\n"
                f"⚠️ Ссылка действительна 24 часа."
            )

            self.send_telegram_message(user.profile.telegram_id, message)

    def send_telegram_message(self, chat_id, text):
        token = settings.TG_BOT_TOKEN
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        try:
            requests.post(url, data=data, timeout=5)
        except Exception as e:
            print(f"Ошибка отправки в Telegram: {e}")
