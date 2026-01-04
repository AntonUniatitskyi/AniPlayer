import telebot
from decouple import config
import django
import logging
import os

BOT_TOKEN = config('TG_BOT_TOKEN')
bot = telebot.TeleBot(BOT_TOKEN)

SITE_URL = config('SITE_URL')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings') # Проверь имя папки core
django.setup()

bot_logger = logging.getLogger('tg_bot')
bot_logger.setLevel(logging.INFO)

# Файл логов бота
bot_handler = logging.FileHandler(os.path.join('logs', 'bot.log'), encoding='utf-8')
bot_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s'))
bot_logger.addHandler(bot_handler)
bot_logger.addHandler(logging.StreamHandler())

@bot.message_handler(commands=['start'])
def send_welcome(message):
    args = message.text.split()

    if len(args) > 1:
        token = args[1]
        chat_id = message.chat.id
        back_link = f"{SITE_URL}/connect-telegram/done/{token}/{chat_id}/"

        text = (
            f"👋 Привет, {message.from_user.first_name}!\n\n"
            f"Для завершения привязки нажмите на кнопку ниже:"
        )

        markup = telebot.types.InlineKeyboardMarkup()
        btn = telebot.types.InlineKeyboardButton(text="✅ Подтвердить привязку", url=back_link)
        markup.add(btn)

        bot.send_message(chat_id, text, reply_markup=markup)
    else:
        bot.send_message(message.chat.id, "Просто так меня запускать не надо. Зайди в настройки на сайте!")

bot_logger.info("Бот запущен...")
bot.polling(non_stop=True, timeout=90, long_polling_timeout=90)
