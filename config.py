import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# Интервал проверки новых объявлений (в минутах)
CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", "10"))

# Максимальное количество подписок на пользователя
MAX_SUBSCRIPTIONS_PER_USER = int(os.getenv("MAX_SUBSCRIPTIONS_PER_USER", "10"))

# Путь к базе данных
DB_PATH = os.getenv("DB_PATH", "avito_bot.db")

# User-Agent для парсинга
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# Задержка между запросами (секунды)
REQUEST_DELAY = float(os.getenv("REQUEST_DELAY", "2.0"))
