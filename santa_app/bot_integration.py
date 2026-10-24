"""
Интеграция Django → Telegram.
Отправляет уведомления, когда на сайте приходит новое сообщение.

⚠️ ВНИМАНИЕ: токен и URL заданы прямо в коде.
Позже замените на os.getenv() или settings.
"""

import logging
import asyncio
import threading
import aiohttp
import requests

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
#  🔧 НАСТРОЙКИ (задайте свои значения)
# ─────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = '8044460949:AAG_kM6ElVfsU0uhbb3OQNdjcBps7P2BzKM'
TELEGRAM_WORKER_URL = 'https://autumn-band-ae30.korchemkins0.workers.dev'


# ─────────────────────────────────────────────
#  Отправка сообщения через Bot API
# ─────────────────────────────────────────────
async def _send_telegram_message(chat_id: int, text: str, reply_markup: dict = None):
    """Отправляет сообщение в Telegram через Worker-прокси."""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN не задан — уведомления отключены")
        return False

    url = f"{TELEGRAM_WORKER_URL}/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'HTML',
    }
    if reply_markup:
        payload['reply_markup'] = reply_markup

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=15) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.error("Telegram sendMessage failed: %s %s", resp.status, body)
                    return False
                return True
    except Exception as e:
        logger.exception("HTTP error при отправке в Telegram: %s", e)
        return False


# ─────────────────────────────────────────────
#  Уведомление о новом сообщении
# ─────────────────────────────────────────────
def notify_new_message(chat_obj, message_obj):
    """
    Отправляет уведомление получателю сообщения в Telegram.
    Вызывать из Django-view после создания Message.
    """
    from .models import TelegramUser

    # Собеседник — тот, кому нужно уведомление
    recipient = chat_obj.participant

    tg = TelegramUser.objects.filter(
        user=recipient, is_active=True
    ).first()
    if not tg:
        return  # Получатель не привязал Telegram — тихо выходим

    sender_name = chat_obj.user.get_display_name()
    room_name = chat_obj.room.name
    preview = (message_obj.content or '📎 Медиа')[:100]

    text = (
        f"💬 <b>Новое сообщение</b>\n\n"
        f"<b>От:</b> {sender_name}\n"
        f"<b>Комната:</b> {room_name}\n\n"
        f"{preview}"
    )

    reply_markup = {
        'inline_keyboard': [[
            {'text': '↩️ Ответить', 'callback_data': f'reply_chat:{chat_obj.id}'}
        ]]
    }

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(
            _send_telegram_message(tg.telegram_id, text, reply_markup)
        )
        loop.close()
    except Exception as e:
        logger.exception("Не удалось отправить уведомление: %s", e)


def notify_new_message_async(chat_obj, message_obj):
    """
    Запускает отправку уведомления в фоновом потоке,
    чтобы не блокировать HTTP-запрос Django.
    """
    thread = threading.Thread(
        target=notify_new_message,
        args=(chat_obj, message_obj),
        daemon=True,
    )
    thread.start()


async def _notify_participant_async(room_id, participant_name):
    """Уведомление в TG-группу о новом участнике"""
    from .models import Room, TelegramChat, Participant

    try:
        room = Room.objects.get(id=room_id)
        tg_chat = TelegramChat.objects.filter(
            room=room, is_active=True, notify_new_member=True
        ).first()
        if not tg_chat:
            return

        total = Participant.objects.filter(room=room).count()

        url = f"{TELEGRAM_WORKER_URL}/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': tg_chat.chat_id,
            'text': (
                f"👋 <b>Новый участник!</b>\n\n"
                f"<b>{participant_name}</b> присоединился к комнате «{room.name}»\n"
                f"👥 Всего: <b>{total}</b>"
            ),
            'parse_mode': 'HTML',
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=15) as resp:
                if resp.status != 200:
                    logger.error("Ошибка отправки: %s", await resp.text())
    except Exception as e:
        logger.exception("notify_participant error: %s", e)


def notify_new_participant(room_id, participant_name):
    """
    Синхронная версия. Вызывается из views.py.
    Никаких async/await, никаких потоков — только обычные запросы к БД.
    """
    from .models import Room, TelegramChat, Participant

    logger.info(f"🔔 notify_new_participant: room_id={room_id}, name={participant_name}")

    try:
        # ⚠️ Теперь это работает, потому что функция синхронная!
        room = Room.objects.get(id=room_id)
        tg_chat = TelegramChat.objects.filter(
            room=room, is_active=True, notify_new_member=True
        ).first()

        if not tg_chat:
            logger.warning(f"⚠️ Нет привязанной группы для комнаты «{room.name}»")
            return

        total = Participant.objects.filter(room=room).count()

        url = f"{TELEGRAM_WORKER_URL}/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': tg_chat.chat_id,
            'text': (
                f"👋 <b>Новый участник!</b>\n\n"
                f"<b>{participant_name}</b> присоединился к комнате «{room.name}»\n"
                f"👥 Всего: <b>{total}</b>"
            ),
            'parse_mode': 'HTML',
        }

        # Синхронный POST-запрос
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            logger.info(f"✅ Уведомление отправлено в группу «{tg_chat.chat_title}»")
        else:
            logger.error(f"❌ Telegram вернул ошибку {response.status_code}: {response.text}")

    except Exception as e:
        logger.exception(f"💥 Ошибка при отправке уведомления: {e}")