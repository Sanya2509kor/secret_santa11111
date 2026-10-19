"""
Обёртки над Django ORM для вызова из async-кода aiogram.
Защищены от потери соединения с MySQL.
"""

import logging
from functools import wraps

from asgiref.sync import sync_to_async
from django.db import close_old_connections, OperationalError
from django.core.cache import cache
from django.db.models import Q

logger = logging.getLogger(__name__)


def safe_db_call(func):
    """
    Декоратор: закрывает старые соединения и повторяет запрос при потере связи.
    Автоматически оборачивает в sync_to_async.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            close_old_connections()
            return func(*args, **kwargs)
        except OperationalError as e:
            logger.warning("⚠️ DB connection lost, retrying: %s", e)
            close_old_connections()
            try:
                return func(*args, **kwargs)
            except OperationalError as retry_e:
                logger.error("❌ DB retry failed: %s", retry_e)
                raise

    return sync_to_async(wrapper)


# ─────────────────────────────────────────────
#  TelegramUser
# ─────────────────────────────────────────────
@safe_db_call
def get_user_by_telegram_id(tg_id: int):
    from santa_app.models import TelegramUser
    tg = TelegramUser.objects.filter(
        telegram_id=tg_id, is_active=True
    ).select_related('user').first()
    return tg.user if tg else None


import re


def _normalize_phone(raw):
    """Нормализация номера до формата 7XXXXXXXXXX"""
    if not raw:
        return None
    digits = re.sub(r'\D', '', str(raw))

    if len(digits) == 11 and digits.startswith('8'):
        digits = '7' + digits[1:]
    elif len(digits) == 11 and digits.startswith('7'):
        pass
    elif len(digits) == 10:
        digits = '7' + digits
    else:
        return None

    return digits if len(digits) == 11 else None


@safe_db_call
def find_user_by_normalized_phone(normalized_phone):
    """
    Ищет User по нормализованному номеру.
    Сравнивает с учётом всех вариантов записи в БД (7, 8, +7).
    """
    from santa_app.models import User, TelegramUser

    # Достаём всех пользователей и сравниваем в Python
    # (в БД номера могут быть записаны по-разному)
    all_users = User.objects.all()

    matched_user = None
    for u in all_users:
        if _normalize_phone(u.phone) == normalized_phone:
            matched_user = u
            break

    if not matched_user:
        return None

    # Проверим, не привязан ли уже
    already_linked = TelegramUser.objects.filter(
        user=matched_user, is_active=True
    ).exists()

    return {
        'user_id': matched_user.id,
        'display_name': matched_user.get_display_name(),
        'already_linked': already_linked,
    }


@safe_db_call
def attach_telegram_by_contact(telegram_id, user_id, username, first_name):
    """Привязывает Telegram к User по ID."""
    from santa_app.models import User, TelegramUser

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return None, "Пользователь не найден"

    # Проверим, что этот user не привязан к другому TG
    conflict = TelegramUser.objects.filter(
        user=user, is_active=True
    ).exclude(telegram_id=telegram_id).first()
    if conflict:
        return None, "Аккаунт уже привязан к другому Telegram"

    # Проверим, что этот telegram_id не привязан к другому user
    existing_tg = TelegramUser.objects.filter(telegram_id=telegram_id).first()
    if existing_tg and existing_tg.user_id != user.id:
        existing_tg.user = user
        existing_tg.username = username
        existing_tg.first_name = first_name
        existing_tg.is_active = True
        existing_tg.save()
    else:
        TelegramUser.objects.update_or_create(
            telegram_id=telegram_id,
            defaults={
                'user': user,
                'username': username,
                'first_name': first_name,
                'is_active': True,
            }
        )

    return user, "OK"


@safe_db_call
def attach_telegram(telegram_id: int, user_id: int, username: str, first_name: str):
    from santa_app.models import User, TelegramUser
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return None, "Пользователь не найден"

    conflict = TelegramUser.objects.filter(
        user=user, is_active=True
    ).exclude(telegram_id=telegram_id).first()
    if conflict:
        return None, "Аккаунт уже привязан к другому Telegram"

    TelegramUser.objects.update_or_create(
        telegram_id=telegram_id,
        defaults={
            'user': user,
            'username': username,
            'first_name': first_name,
            'is_active': True,
        }
    )
    return user, "OK"


@safe_db_call
def detach_telegram(telegram_id: int) -> bool:
    from santa_app.models import TelegramUser
    updated = TelegramUser.objects.filter(
        telegram_id=telegram_id, is_active=True
    ).update(is_active=False)
    return updated > 0


# ─────────────────────────────────────────────
#  Rate limiting
# ─────────────────────────────────────────────
@sync_to_async
def check_rate_limit(telegram_id: int, action: str,
                     max_attempts: int = 5, window_minutes: int = 60) -> bool:
    key = f"rl:{action}:{telegram_id}"
    count = cache.get(key, 0)
    if count >= max_attempts:
        return False
    cache.set(key, count + 1, timeout=window_minutes * 60)
    return True


# ─────────────────────────────────────────────
#  Rooms / Participants / SantaPair
# ─────────────────────────────────────────────
@safe_db_call
def get_user_rooms(user):
    from santa_app.models import Room
    return list(
        Room.objects.filter(
            participant__user=user,
            is_active=True
        ).distinct()
    )


@safe_db_call
def get_room_by_id(room_id: int):
    from santa_app.models import Room
    return Room.objects.filter(id=room_id, is_active=True).first()


@safe_db_call
def get_room_by_telegram_chat(chat_id: int):
    from santa_app.models import TelegramChat
    link = TelegramChat.objects.filter(
        chat_id=chat_id, is_active=True
    ).select_related('room').first()
    return link.room if link else None


@safe_db_call
def get_room_status(room):
    from santa_app.models import Participant
    total = Participant.objects.filter(room=room).count()
    return {
        'name': room.name,
        'code': room.code,
        'total': total,
        'draw_completed': room.draw_completed,
        'deadline': room.gift_deadline,
        'admin_name': room.admin.get_display_name(),
    }


@safe_db_call
def get_santa_info(user, room):
    from santa_app.models import SantaPair, Participant
    pair = SantaPair.objects.filter(
        room=room, santa=user
    ).select_related('receiver').first()
    if not pair:
        return None

    participant = Participant.objects.filter(
        user=pair.receiver, room=room
    ).first()

    return {
        'receiver': pair.receiver,
        'display_name': participant.get_display_name() if participant else 'Аноним',
        'wishlist': participant.wishlist if participant else '',
    }


@safe_db_call
def get_receiver_info(user, room):
    from santa_app.models import SantaPair
    pair = SantaPair.objects.filter(
        room=room, receiver=user
    ).select_related('santa').first()
    return pair.santa if pair else None


# ─────────────────────────────────────────────
#  Групповые чаты
# ─────────────────────────────────────────────
@safe_db_call
def link_group(chat_id: int, chat_title: str, room_code: str, admin_user):
    from santa_app.models import Room, TelegramChat
    try:
        room = Room.objects.get(code=room_code.upper(), is_active=True)
    except Room.DoesNotExist:
        return None, 'Комната с таким кодом не найдена'

    if room.admin != admin_user:
        return None, 'Вы не админ этой комнаты'

    tg_chat, _ = TelegramChat.objects.update_or_create(
        chat_id=chat_id,
        defaults={
            'room': room,
            'chat_title': chat_title,
            'linked_by': admin_user,
            'is_active': True,
        }
    )
    return tg_chat, 'OK'


@safe_db_call
def get_rooms_with_stats(user):
    """
    Возвращает список комнат пользователя с готовой статистикой.
    Все запросы к БД выполняются здесь — внутри sync-контекста.
    """
    from santa_app.models import Room

    rooms = Room.objects.filter(
        participant__user=user,
        is_active=True
    ).distinct().prefetch_related('participant_set')

    result = []
    for room in rooms:
        result.append({
            'id': room.id,
            'name': room.name,
            'code': room.code,
            'draw_completed': room.draw_completed,
            'total': room.participant_set.count(),
            'deadline': room.gift_deadline,
        })
    return result


@safe_db_call
def get_my_wishlist(user, room):
    """Возвращает пожелания текущего пользователя в комнате"""
    from santa_app.models import Participant
    participant = Participant.objects.filter(
        user=user, room=room
    ).first()
    if not participant:
        return None
    return {
        'display_name': participant.get_display_name(),
        'wishlist': participant.wishlist or '',
    }


# ─────────────────────────────────────────────
#  Чаты и сообщения
# ─────────────────────────────────────────────
@safe_db_call
def get_user_chats_with_stats(user):
    """Возвращает список чатов пользователя со статистикой"""
    from santa_app.models import Chat, Message
    
    chats = Chat.objects.filter(
        user=user
    ).select_related('room', 'participant').order_by('-created_at')

    result = []
    for chat in chats:
        unread = Message.objects.filter(
            chat=chat, is_read=False
        ).exclude(sender=user).count()
        
        last = Message.objects.filter(chat=chat).order_by('-timestamp').first()

        result.append({
            'id': chat.id,
            'title': '🎅 Чат с моим Сантой' if chat.chat_type == 'my_santa' else '🎁 Чат с моим получателем',
            'room_name': chat.room.name,
            'chat_type': chat.chat_type,
            'unread': unread,
            'last_message': (last.content or '📎 Медиа')[:40] if last else None,
            'last_timestamp': last.timestamp.strftime('%H:%M') if last else None,
        })
    return result


@safe_db_call
def get_chat_by_id(chat_id, user):
    """Получает чат, проверяя, что он принадлежит пользователю"""
    from santa_app.models import Chat
    return Chat.objects.filter(
        id=chat_id, user=user
    ).select_related('room', 'participant', 'user').first()


@safe_db_call
def get_chat_info(chat):
    """Инфо о чате для отображения"""
    from santa_app.models import Message, Participant

    other_participant = Participant.objects.filter(
        user=chat.participant, room=chat.room
    ).first()
    other_name = other_participant.get_display_name() if other_participant else 'Аноним'

    last = Message.objects.filter(chat=chat).order_by('-timestamp').first()

    return {
        'title': 'С моим Сантой' if chat.chat_type == 'my_santa' else 'С моим получателем',
        'room_name': chat.room.name,
        'other_name': other_name,
        'last_message': last.content if last else None,
    }


@safe_db_call
def get_chat_messages(chat_id, limit=20):
    """Последние N сообщений в чате"""
    from santa_app.models import Chat, Message
    
    chat = Chat.objects.filter(id=chat_id).first()
    if not chat:
        return []

    msgs = Message.objects.filter(chat=chat).order_by('-timestamp')[:limit]

    result = []
    for m in reversed(msgs):
        result.append({
            'id': m.id,
            'content': m.content,
            'sender': m.sender.get_display_name(),
            'timestamp': m.timestamp.strftime('%d.%m %H:%M'),
            'is_own': m.sender_id == chat.user_id,
        })
    return result


@safe_db_call
def save_message_from_telegram(chat_id, sender_user, content):
    """
    Сохраняет сообщение из Telegram в БД.
    Дублирует в парный чат (как это делает сайт).
    Возвращает True/False.
    """
    from santa_app.models import Chat, Message

    chat = Chat.objects.filter(id=chat_id, user=sender_user).first()
    if not chat:
        return False

    # Сообщение в текущий чат
    Message.objects.create(
        chat=chat,
        sender=sender_user,
        content=content,
        is_read=True,  # своё сообщение сразу прочитано
    )

    # Копия в парный чат
    pair_chat = chat.get_pair_chat()
    if pair_chat:
        Message.objects.create(
            chat=pair_chat,
            sender=sender_user,
            content=content,
            is_read=False,  # получатель ещё не прочитал
        )

    return True


@safe_db_call
def get_unread_notifications_for_user(user):
    """Возвращает непрочитанные сообщения по всем чатам (для уведомлений)"""
    from santa_app.models import Chat, Message

    chats = Chat.objects.filter(user=user).select_related('room', 'participant')
    result = []
    for chat in chats:
        unread = Message.objects.filter(
            chat=chat, is_read=False
        ).exclude(sender=user).count()
        if unread > 0:
            result.append({
                'chat_id': chat.id,
                'room_name': chat.room.name,
                'unread': unread,
                'title': 'С моим Сантой' if chat.chat_type == 'my_santa' else 'С моим получателем',
            })
    return result



@safe_db_call
def mark_chat_read(chat_id, user):
    """Помечает все входящие сообщения чата как прочитанные"""
    from santa_app.models import Chat, Message
    chat = Chat.objects.filter(id=chat_id, user=user).first()
    if not chat:
        return False
    Message.objects.filter(
        chat=chat, is_read=False
    ).exclude(sender=user).update(is_read=True)
    return True


@safe_db_call
def get_my_wishlist_info(user, room):
    """Возвращает текущие пожелания пользователя в комнате"""
    from santa_app.models import Participant
    p = Participant.objects.filter(user=user, room=room).first()
    if not p:
        return None
    return {
        'wishlist': p.wishlist or '',
        'display_name': p.get_display_name(),
    }


@safe_db_call
def update_wishlist(user, room, text):
    """Обновляет wishlist пользователя в комнате"""
    from santa_app.models import Participant
    p = Participant.objects.filter(user=user, room=room).first()
    if not p:
        return False
    p.wishlist = text[:2000]  # ограничим 2000 символов
    p.save(update_fields=['wishlist'])
    return True

@safe_db_call
def unlink_group(chat_id: int) -> bool:
    """Отвязывает TelegramChat от комнаты"""
    from santa_app.models import TelegramChat
    updated = TelegramChat.objects.filter(
        chat_id=chat_id, is_active=True
    ).update(is_active=False)
    return updated > 0


@safe_db_call
def mark_gift_bought(user, room, bought=True):
    """Отмечает/снимает отметку о покупке подарка"""
    from santa_app.models import Participant
    from django.utils import timezone

    p = Participant.objects.filter(user=user, room=room).first()
    if not p:
        return False

    p.gift_bought = bought
    p.gift_bought_at = timezone.now() if bought else None
    p.save(update_fields=['gift_bought', 'gift_bought_at'])
    return True


@safe_db_call
def get_gift_status(user, room):
    """Возвращает статус подарка пользователя в комнате"""
    from santa_app.models import Participant
    p = Participant.objects.filter(user=user, room=room).first()
    if not p:
        return None
    return {
        'bought': p.gift_bought,
        'bought_at': p.gift_bought_at,
        'display_name': p.get_display_name(),
    }


@safe_db_call
def get_room_gift_stats(room):
    """Возвращает список участников с их статусом покупки"""
    from santa_app.models import Participant
    participants = Participant.objects.filter(room=room).order_by('display_name')

    result = {
        'bought': [],
        'not_bought': [],
        'total': 0,
    }

    for p in participants:
        result['total'] += 1
        info = {
            'user_id': p.user_id,
            'display_name': p.get_display_name(),
            'is_admin': p.user_id == room.admin_id,
        }
        if p.gift_bought:
            result['bought'].append(info)
        else:
            result['not_bought'].append(info)

    return result


@safe_db_call
def update_last_asked(user, room):
    """Обновляет время последнего опроса"""
    from santa_app.models import Participant
    from django.utils import timezone
    Participant.objects.filter(user=user, room=room).update(
        last_asked_at=timezone.now()
    )


@safe_db_call
def get_participants_to_ask(room, days_before_deadline=None):
    """
    Возвращает список участников, которых нужно опросить.
    Если days_before_deadline задан — фильтр по дедлайну.
    Если нет — по правилу «каждые 10 дней».
    """
    from santa_app.models import Participant, TelegramUser
    from django.utils import timezone
    from datetime import timedelta

    now = timezone.now()

    if days_before_deadline is not None:
        # За N дней до дедлайна опрашиваем всех, кто не купил
        participants = Participant.objects.filter(
            room=room, gift_bought=False
        )
    else:
        # Каждые 10 дней — только тех, кого не спрашивали или спрашивали давно
        ten_days_ago = now - timedelta(days=10)
        participants = Participant.objects.filter(
            room=room, gift_bought=False
        ).filter(
            Q(last_asked_at__isnull=True) | Q(last_asked_at__lt=ten_days_ago)
        )

    result = []
    for p in participants:
        tg = TelegramUser.objects.filter(
            user=p.user, is_active=True
        ).first()
        if tg:
            result.append({
                'telegram_id': tg.telegram_id,
                'user_id': p.user_id,
                'display_name': p.get_display_name(),
                'room_id': room.id,
            })
    return result



@safe_db_call
def can_reveal_pairs(room):
    """Можно ли раскрыть пары в комнате"""
    from django.utils import timezone
    if not room.gift_deadline:
        return False
    return timezone.now() > room.gift_deadline


@safe_db_call
def get_pairs_map(room):
    """Возвращает карту пар с именами участников"""
    from santa_app.models import SantaPair, Participant

    pairs = SantaPair.objects.filter(room=room).select_related(
        'santa', 'receiver'
    )

    result = []
    for pair in pairs:
        santa_p = Participant.objects.filter(
            user=pair.santa, room=room
        ).first()
        receiver_p = Participant.objects.filter(
            user=pair.receiver, room=room
        ).first()

        result.append({
            'santa_name': santa_p.get_display_name() if santa_p else 'Аноним',
            'receiver_name': receiver_p.get_display_name() if receiver_p else 'Аноним',
            'santa_is_admin': pair.santa_id == room.admin_id,
            'receiver_is_admin': pair.receiver_id == room.admin_id,
        })

    return result