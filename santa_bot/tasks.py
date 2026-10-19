"""
Фоновые задачи: напоминания о дедлайнах, уведомления о новых участниках.
Запускается как asyncio-таск в main.py.
"""

import asyncio
import logging
from datetime import timedelta

from aiogram import Bot
from django.utils import timezone
from asgiref.sync import sync_to_async
from django.db.models import Q

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════
#  1. Ежедневная проверка дедлайнов
# ═══════════════════════════════════════════════
async def daily_deadline_reminders(bot: Bot):
    """
    Раз в день в 10:00 UTC (13:00 МСК) проверяет комнаты с близким дедлайном.
    Отправляет уведомления:
    - за 7 дней
    - за 3 дня  
    - в день дедлайна
    - каждый день после дедлайна (пока админ не закроет комнату)
    """
    while True:
        try:
            await _check_deadlines(bot)
        except Exception as e:
            logger.exception("Ошибка в daily_deadline_reminders: %s", e)

        # Спим до следующего 10:00 UTC
        now = timezone.now()
        next_run = now.replace(hour=10, minute=0, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)
        wait_seconds = (next_run - now).total_seconds()
        logger.info("⏰ Следующая проверка дедлайнов через %.0f ч.", wait_seconds / 3600)
        await asyncio.sleep(wait_seconds)


async def _check_deadlines(bot: Bot):
    from santa_app.models import Room, TelegramChat, Participant, TelegramUser
    from santa_app.models import Message, Chat

    now = timezone.now()

    # Находим все активные комнаты с дедлайном
    rooms = await sync_to_async(list)(
        Room.objects.filter(
            is_active=True,
            gift_deadline__isnull=False,
        )
    )

    for room in rooms:
        days_left = (room.gift_deadline - now).days

        # Отправляем только в «нужные» дни
        should_notify = days_left in (7, 3, 1, 0) or (days_left < 0 and abs(days_left) <= 3)
        if not should_notify:
            continue

        # 1. Уведомление в привязанную группу
        tg_chat = await sync_to_async(
            lambda: TelegramChat.objects.filter(
                room=room, is_active=True, notify_deadline=True
            ).first()
        )()

        if tg_chat:
            text = _format_deadline_message(room, days_left)
            try:
                await bot.send_message(tg_chat.chat_id, text, parse_mode='HTML')
                logger.info("✅ Дедлайн-напоминание в группу %s", tg_chat.chat_title)
            except Exception as e:
                logger.warning("❌ Не удалось отправить в группу %s: %s", tg_chat.chat_id, e)

        # 2. Персональные напоминания участникам, которые не заполнили wishlist (только если за 7+ дней)
        if days_left in (7, 3):
            await _remind_participants(bot, room, days_left)


def _format_deadline_message(room, days_left):
    """Формирует текст напоминания о дедлайне"""
    if days_left > 0:
        emoji = "⏰" if days_left > 3 else "🔥"
        text = (
            f"{emoji} <b>Комната «{room.name}»</b>\n\n"
            f"До дедлайна осталось <b>{days_left}</b> дн.!\n"
            f"📅 Дата: {room.gift_deadline.strftime('%d.%m.%Y')}\n\n"
        )
        if days_left <= 3:
            text += "🎁 Не забудьте купить подарок!"
        else:
            text += "💡 Проверьте пожелания получателя."
    elif days_left == 0:
        text = (
            f"🔥 <b>Сегодня дедлайн!</b>\n\n"
            f"Комната «{room.name}»\n"
            f"🎁 Последний день купить и подарить подарок!"
        )
    else:
        text = (
            f"⚠️ <b>Дедлайн прошёл {abs(days_left)} дн. назад</b>\n\n"
            f"Комната «{room.name}»\n"
            f"Если подарки ещё не вручены — самое время!"
        )
    return text


async def _remind_participants(bot: Bot, room, days_left):
    """Персональные напоминания участникам без wishlist"""
    from santa_app.models import Participant, TelegramUser
    from django.db import models

    # Находим всех участников без пожеланий
    participants_without_wishlist = await sync_to_async(list)(
        Participant.objects.filter(
            room=room,
        ).exclude(wishlist__isnull=False).exclude(wishlist='')
    )

    # Или точнее: у кого wishlist пустой или null
    participants_without_wishlist = await sync_to_async(list)(
        Participant.objects.filter(room=room).filter(
            models.Q(wishlist__isnull=True) | models.Q(wishlist='')
        )
    )

    for p in participants_without_wishlist:
        tg = await sync_to_async(
            lambda u=p.user: TelegramUser.objects.filter(
                user=u, is_active=True
            ).first()
        )()
        if not tg:
            continue

        text = (
            f"🎁 <b>Привет, {p.get_display_name()}!</b>\n\n"
            f"В комнате «{room.name}» до дедлайна осталось <b>{days_left}</b> дн., "
            f"а вы ещё не заполнили пожелания к подарку.\n\n"
            f"Это поможет вашему Санте выбрать идеальный подарок."
        )

        try:
            await bot.send_message(
                tg.telegram_id, text,
                parse_mode='HTML',
                reply_markup={
                    'inline_keyboard': [[
                        {'text': '📝 Заполнить пожелания', 'url': f'https://24santa-secret.ru/room/{room.id}/wishlist/'}
                    ]]
                }
            )
            logger.info("✅ Персональное напоминание → %s", tg.telegram_id)
        except Exception as e:
            logger.warning("❌ Ошибка отправки %s: %s", tg.telegram_id, e)


# ═══════════════════════════════════════════════
#  2. Уведомление о новом участнике
# ═══════════════════════════════════════════════
async def notify_new_participant(bot: Bot, room, participant_name):
    """
    Отправляет уведомление в привязанную к комнате группу.
    Вызывается из Django-view, когда участник присоединяется.
    """
    from santa_app.models import TelegramChat, Participant

    tg_chat = await sync_to_async(
        lambda: TelegramChat.objects.filter(
            room=room, is_active=True, notify_new_member=True
        ).first()
    )()

    if not tg_chat:
        return

    total = await sync_to_async(lambda: Participant.objects.filter(room=room).count())()
    admin_name = room.admin.get_display_name()

    text = (
        f"👋 <b>Новый участник!</b>\n\n"
        f"<b>{participant_name}</b> присоединился к комнате «{room.name}»\n"
        f"👥 Всего участников: <b>{total}</b>\n"
        f"👑 Админ: {admin_name}"
    )

    try:
        await bot.send_message(tg_chat.chat_id, text, parse_mode='HTML')
        logger.info("✅ Уведомление о новом участнике в %s", tg_chat.chat_title)
    except Exception as e:
        logger.warning("❌ Не удалось уведомить о новом участнике: %s", e)


# ═══════════════════════════════════════════════
#  ПРОВЕРКА ПОКУПКИ ПОДАРКОВ
# ═══════════════════════════════════════════════
async def gift_check_scheduler(bot: Bot):
    """
    Раз в день проверяет:
    1. Каждые 10 дней спрашивает в ЛС участников, купили ли они подарок
    2. За 7/3/1 день до дедлайна — срочные напоминания
    3. Отправляет в группу статус «кто купил / кто нет» (по той же периодичности)
    """
    while True:
        try:
            await _check_gifts(bot)
        except Exception as e:
            logger.exception("Ошибка в gift_check_scheduler: %s", e)

        # Проверяем каждый день в 11:00 UTC (14:00 МСК)
        now = timezone.now()
        next_run = now.replace(hour=11, minute=0, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)
        wait = (next_run - now).total_seconds()
        logger.info("⏰ Проверка подарков через %.0f ч.", wait / 3600)
        await asyncio.sleep(wait)


async def _check_gifts(bot: Bot):
    """Основная логика проверки подарков"""
    from santa_app.models import Room

    now = timezone.now()

    # Берём все активные комнаты с дедлайном
    rooms = await sync_to_async(list)(
        Room.objects.filter(
            is_active=True,
            draw_completed=True,
            gift_deadline__isnull=False,
        )
    )

    for room in rooms:
        try:
            days_left = (room.gift_deadline - now).days

            # ═══ 1. Опрос участников в ЛС ═══
            should_ask_individual = False
            ask_reason = ""

            # За 7, 3, 1 день
            if days_left in (7, 3, 1):
                should_ask_individual = True
                ask_reason = f"до дедлайна осталось {days_left} дн."
            # В день дедлайна
            elif days_left == 0:
                should_ask_individual = True
                ask_reason = "сегодня дедлайн!"
            # Каждые 10 дней (если дедлайн ещё далеко)
            elif days_left > 7:
                should_ask_individual = True
                ask_reason = "check_10_days"

            if should_ask_individual:
                await _ask_participants(bot, room, days_left, ask_reason)

            # ═══ 2. Отправка статуса в группу ═══
            should_notify_group = False

            if days_left in (7, 3, 1, 0):
                should_notify_group = True
            elif days_left > 7 and days_left % 10 == 0:
                # Каждые 10 дней до дедлайна
                should_notify_group = True

            if should_notify_group:
                await _notify_group_gift_status(bot, room, days_left)

        except Exception as e:
            logger.exception("Ошибка обработки комнаты %s: %s", room.id, e)


async def _ask_participants(bot: Bot, room, days_left, reason):
    """Спрашивает в ЛС у тех, кто не купил подарок"""
    from santa_bot_helpers import _ask_single  # определим ниже

    # Для «каждые 10 дней» — только тех, кого не спрашивали давно
    if reason == "check_10_days":
        participants = await _get_participants_for_10day_check(room)
    else:
        participants = await _get_participants_not_bought(room)

    for p in participants:
        try:
            text = _build_ask_text(room, days_left, p['display_name'])
            await bot.send_message(
                p['telegram_id'],
                text,
                parse_mode='HTML',
                reply_markup={
                    'inline_keyboard': [
                        [
                            {'text': '✅ Уже купил(а)', 'callback_data': f'gift_bought:{room.id}'},
                        ],
                        [
                            {'text': '⏰ Позже', 'callback_data': 'gift_later'},
                        ],
                    ]
                },
            )
            # Обновляем last_asked_at
            await _update_last_asked(p['user_id'], room.id)
            logger.info("✅ Опрос о подарке → %s", p['display_name'])
        except Exception as e:
            logger.warning("❌ Не отправить %s: %s", p['telegram_id'], e)


def _build_ask_text(room, days_left, name):
    """Формирует текст вопроса о подарке"""
    if days_left > 7:
        return (
            f"🎁 <b>Привет, {name}!</b>\n\n"
            f"Напоминаю про подарок для комнаты «{room.name}».\n"
            f"📅 Дедлайн: {room.gift_deadline.strftime('%d.%m.%Y')}\n\n"
            f"Уже купили подарок?"
        )
    elif days_left == 0:
        return (
            f"🔥 <b>Привет, {name}!</b>\n\n"
            f"<b>Сегодня дедлайн</b> в комнате «{room.name}»!\n"
            f"Успели купить подарок?"
        )
    else:
        return (
            f"⏰ <b>Привет, {name}!</b>\n\n"
            f"До дедлайна в комнате «{room.name}» осталось "
            f"<b>{days_left} дн.</b>\n"
            f"📅 {room.gift_deadline.strftime('%d.%m.%Y')}\n\n"
            f"Уже купили подарок?"
        )


async def _get_participants_not_bought(room):
    """Все, кто не купил подарок, + привязан Telegram"""
    from santa_app.models import Participant, TelegramUser
    parts = await sync_to_async(list)(
        Participant.objects.filter(room=room, gift_bought=False)
    )
    result = []
    for p in parts:
        tg = await sync_to_async(
            lambda u=p.user: TelegramUser.objects.filter(user=u, is_active=True).first()
        )()
        if tg:
            result.append({
                'telegram_id': tg.telegram_id,
                'user_id': p.user_id,
                'display_name': p.get_display_name(),
            })
    return result


async def _get_participants_for_10day_check(room):
    """Тех, кого не спрашивали последние 10 дней"""
    from santa_app.models import Participant, TelegramUser
    from django.db.models import Q
    ten_days_ago = timezone.now() - timedelta(days=10)

    parts = await sync_to_async(list)(
        Participant.objects.filter(room=room, gift_bought=False).filter(
            Q(last_asked_at__isnull=True) | Q(last_asked_at__lt=ten_days_ago)
        )
    )
    result = []
    for p in parts:
        tg = await sync_to_async(
            lambda u=p.user: TelegramUser.objects.filter(user=u, is_active=True).first()
        )()
        if tg:
            result.append({
                'telegram_id': tg.telegram_id,
                'user_id': p.user_id,
                'display_name': p.get_display_name(),
            })
    return result


async def _update_last_asked(user_id, room_id):
    from santa_app.models import Participant
    await sync_to_async(
        lambda: Participant.objects.filter(
            user_id=user_id, room_id=room_id
        ).update(last_asked_at=timezone.now())
    )()


async def _notify_group_gift_status(bot: Bot, room, days_left):
    """Отправляет в группу статус «кто купил / кто нет»"""
    from santa_app.models import TelegramChat, Participant

    tg_chat = await sync_to_async(
        lambda: TelegramChat.objects.filter(room=room, is_active=True).first()
    )()
    if not tg_chat:
        return

    # Собираем статус
    participants = await sync_to_async(list)(
        Participant.objects.filter(room=room).order_by('display_name')
    )

    bought = [p for p in participants if p.gift_bought]
    not_bought = [p for p in participants if not p.gift_bought]

    # Формируем текст
    if days_left > 7:
        header = f"🎁 <b>Статус подарков — «{room.name}»</b>\n\n"
    elif days_left == 0:
        header = f"🔥 <b>Дедлайн сегодня! — «{room.name}»</b>\n\n"
    else:
        header = f"⏰ <b>До дедлайна {days_left} дн. — «{room.name}»</b>\n\n"

    text = header
    text += f"📊 Готово: <b>{len(bought)}</b> из <b>{len(participants)}</b>\n\n"

    if bought:
        text += "✅ <b>Купили подарок:</b>\n"
        for p in bought:
            text += f"  • {p.get_display_name()}\n"
        text += "\n"

    if not_bought:
        text += "⏳ <b>Ещё не купили:</b>\n"
        for p in not_bought:
            text += f"  • {p.get_display_name()}\n"

    text += f"\n💡 Отметить покупку можно командой /bought в ЛС с ботом."

    try:
        await bot.send_message(tg_chat.chat_id, text, parse_mode='HTML')
        logger.info("✅ Статус подарков → группа %s", tg_chat.chat_title)
    except Exception as e:
        logger.warning("❌ Не отправить в группу %s: %s", tg_chat.chat_id, e)