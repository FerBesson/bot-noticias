import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TELEGRAM_NEWS_TOPIC_ID = os.getenv("TELEGRAM_NEWS_TOPIC_ID") # Mantenemos el nombre de la variable de entorno por compatibilidad
TELEGRAM_DAILY_SUMMARY_TOPIC_ID = os.getenv("TELEGRAM_DAILY_SUMMARY_TOPIC_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

HISTORY_FILE = "noticias_enviadas.json"
