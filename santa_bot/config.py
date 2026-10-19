import os
import sys
import django
from pathlib import Path

# ─── 1. Добавляем корень Django-проекта в sys.path ───
# config.py лежит в:  public_html/santa_bot/config.py
# parent         = santa_bot
# parent.parent  = public_html   ← вот корень Django (тут manage.py)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ─── 2. Указываем настройки Django ───
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'secret_santa.settings')

# ─── 3. Инициализируем Django ───
django.setup()

BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '8044460949:AAG_kM6ElVfsU0uhbb3OQNdjcBps7P2BzKM')
ADMIN_IDS = [int(x) for x in os.getenv('BOT_ADMIN_IDS', '').split(',') if x]