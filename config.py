import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

ADMIN_IDS = {
    int(admin.strip())
    for admin in os.getenv("ADMIN_IDS", "").split(",")
    if admin.strip()
}

if not BOT_TOKEN:
    raise ValueError("Не указан BOT_TOKEN")

if not ADMIN_IDS:
    raise ValueError("Не указаны ADMIN_IDS")