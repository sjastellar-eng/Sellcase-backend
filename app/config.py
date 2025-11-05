import os
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/sellcase")
ALLOWED_ORIGINS = [s for s in os.getenv("ALLOWED_ORIGINS", "*").split(",") if s]

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
API_KEY = os.getenv("API_KEY", "")
TZ = os.getenv("TZ", "Europe/Kyiv")
