"""
Команды для групп.
Бот в группе работает ТОЛЬКО от имени группы (TelegramChat).
Личные данные участников НЕ показываются.
"""

import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, ChatMemberUpdated
from aiogram.enums import ChatType

from services import api
from services.texts import group_status_text, group_deadline_text

logger = logging.getLogger(__name__)
router = Router()


# ─────────────────────────────────────────────
#  Фильтр: только группы
# ─────────────────────────────────────────────
def is_group(message: Message) -> bool:
    return message.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP)


# ─────────────────────────────────────────────
#  Приветствие при добавлении бота в группу
# ─────────────────────────────────────────────
@router.my_chat_member()
async def on_bot_added(event: ChatMemberUpdated):
    """Когда бота добавляют в группу — приветствие с инструкцией."""
    if event.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return

    # Проверим: не привязана ли уже эта группа к комнате
    room = await api.get_room_by_telegram_chat(event.chat.id)

    if room:
        await event.bot.send_message(
            event.chat.id,
            f"👋 <b>С возвращением!</b>\n\n"
            f"Эта группа привязана к комнате «{room.name}».\n\n"
            f"<b>Доступные команды:</b>\n"
            f"/status — статус комнаты\n"
            f"/deadline — дедлайн подарка\n"
            f"/unlink_room — отвязать группу от комнаты",
            parse_mode='HTML',
        )
    else:
        await event.bot.send_message(
            event.chat.id,
            "🎅 <b>Привет! Я бот Тайного Санты.</b>\n\n"
            "Чтобы привязать эту группу к комнате, отправьте:\n"
            "<code>/link_room КОД_КОМНАТЫ</code>\n\n"
            "Код можно найти в дашборде на сайте.\n\n"
            "⚠️ Привязать комнату может только <b>её администратор</b>.",
            parse_mode='HTML',
        )


# ─────────────────────────────────────────────
#  /link_room КОД — привязка группы к комнате
# ─────────────────────────────────────────────
@router.message(Command("link_room"))
async def link_group(message: Message):
    if not is_group(message):
        await message.reply(
            "❌ Эта команда работает только в группах.\n"
            "Для личного использования напишите мне в ЛС: /start"
        )
        return

    args = (message.text or '').split()
    if len(args) < 2:
        await message.reply(
            "📖 <b>Использование</b>\n\n"
            "<code>/link_room КОД_КОМНАТЫ</code>\n\n"
            "Код комнаты можно найти в дашборде на сайте.",
            parse_mode='HTML',
        )
        return

    code = args[1].strip().upper()

    # Проверяем, что вызывающий — админ комнаты
    # Для этого нужен его TelegramUser (привязанный через /link в личке)
    user = await api.get_user_by_telegram_id(message.from_user.id)

    if not user:
        await message.reply(
            "❌ <b>Сначала привяжите аккаунт</b>\n\n"
            "Откройте меня в личных сообщениях: "
            f"<a href='https://t.me/{(await message.bot.get_me()).username}?start=link'>"
            f"нажмите сюда</a> и привяжите аккаунт.\n\n"
            "После этого вернитесь и повторите команду.",
            parse_mode='HTML',
            disable_web_page_preview=True,
        )
        return

    # Проверяем, что группа ещё не привязана
    existing_room = await api.get_room_by_telegram_chat(message.chat.id)
    if existing_room:
        await message.reply(
            f"⚠️ Эта группа уже привязана к комнате «{existing_room.name}».\n\n"
            f"Сначала отвяжите: /unlink_room",
            parse_mode='HTML',
        )
        return

    tg_chat, status = await api.link_group(
        chat_id=message.chat.id,
        chat_title=message.chat.title or '',
        room_code=code,
        admin_user=user,
    )

    if tg_chat:
        await message.reply(
            f"✅ <b>Группа привязана к комнате «{tg_chat.room.name}»!</b>\n\n"
            f"<b>Доступные команды:</b>\n"
            f"/status — статус и количество участников\n"
            f"/deadline — сколько осталось до дедлайна\n"
            f"/unlink_room — отвязать группу\n\n"
            f"ℹ️ Комнатой управляет админ <b>{user.get_display_name()}</b>.",
            parse_mode='HTML',
        )
    else:
        await message.reply(f"❌ {status}")


# ─────────────────────────────────────────────
#  /unlink_room — отвязка группы
# ─────────────────────────────────────────────
@router.message(Command("unlink_room"))
async def unlink_group(message: Message):
    if not is_group(message):
        return

    room = await api.get_room_by_telegram_chat(message.chat.id)
    if not room:
        await message.reply("Эта группа не привязана ни к одной комнате.")
        return

    # Только админ комнаты может отвязать
    user = await api.get_user_by_telegram_id(message.from_user.id)
    if not user or room.admin_id != user.id:
        await message.reply(
            "❌ Только администратор комнаты может отвязать группу."
        )
        return

    await api.unlink_group(message.chat.id)

    await message.reply(
        f"✅ Группа отвязана от комнаты «{room.name}».\n"
        f"Привязать снова: /link_room КОД"
    )


# ─────────────────────────────────────────────
#  /status — статус комнаты
# ─────────────────────────────────────────────
@router.message(Command("status"))
async def group_status(message: Message):
    if not is_group(message):
        await message.reply(
            "❌ Эта команда работает только в группах.\n"
            "Для личного использования: /start в ЛС"
        )
        return

    room = await api.get_room_by_telegram_chat(message.chat.id)
    if not room:
        await message.reply(
            "ℹ️ Эта группа не привязана к комнате.\n"
            "Привязать: /link_room КОД"
        )
        return

    status = await api.get_room_status(room)
    await message.reply(group_status_text(status), parse_mode='HTML')


# ─────────────────────────────────────────────
#  /deadline — дедлайн
# ─────────────────────────────────────────────
@router.message(Command("deadline"))
async def group_deadline(message: Message):
    if not is_group(message):
        return

    room = await api.get_room_by_telegram_chat(message.chat.id)
    if not room:
        await message.reply("Эта группа не привязана. Используйте /link_room КОД")
        return

    await message.reply(group_deadline_text(room.gift_deadline), parse_mode='HTML')


# ─────────────────────────────────────────────
#  /help_group — справка по группам
# ─────────────────────────────────────────────
@router.message(Command("help_group"))
async def group_help(message: Message):
    if not is_group(message):
        return

    await message.reply(
        "🎅 <b>Бот Тайного Санты — справка для групп</b>\n\n"
        "<b>Основные команды:</b>\n"
        "/link_room КОД — привязать группу к комнате\n"
        "/unlink_room — отвязать группу\n"
        "/status — статус комнаты\n"
        "/deadline — сколько осталось до дедлайна\n\n"
        "/reveal — карта пар (после дедлайна)\n"
        "ℹ️ Личные данные (комнаты, чаты, санта) доступны только в "
        "личных сообщениях с ботом.",
        parse_mode='HTML',
    )

@router.message(Command("reset_menu"), F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
async def reset_menu(message: Message):
    """Убирает reply-клавиатуру у пользователей, если она осталась от старого бота."""
    from aiogram.types import ReplyKeyboardRemove
    await message.reply(
        "✅ Меню очищено. Все команды доступны через /help_group",
        reply_markup=ReplyKeyboardRemove()
    )


@router.message(Command("bought"))
async def group_bought_status(message: Message):
    """В группе: кто купил подарок, а кто нет"""
    if not is_group(message):
        return

    room = await api.get_room_by_telegram_chat(message.chat.id)
    if not room:
        await message.reply(
            "Эта группа не привязана к комнате.\n"
            "Привязать: /link_room КОД"
        )
        return

    if not room.draw_completed:
        await message.reply(
            "🎲 Жеребьёвка ещё не проведена. Пока нечего отслеживать."
        )
        return

    stats = await api.get_room_gift_stats(room)

    text = f"🎁 <b>Статус подарков — «{room.name}»</b>\n\n"
    text += f"📊 Готово: <b>{len(stats['bought'])}</b> из <b>{stats['total']}</b>\n\n"

    if stats['bought']:
        text += "✅ <b>Купили:</b>\n"
        for p in stats['bought']:
            crown = "👑 " if p['is_admin'] else ""
            text += f"  • {crown}{p['display_name']}\n"
        text += "\n"

    if stats['not_bought']:
        text += "⏳ <b>Ещё не купили:</b>\n"
        for p in stats['not_bought']:
            crown = "👑 " if p['is_admin'] else ""
            text += f"  • {crown}{p['display_name']}\n"

    if room.gift_deadline:
        from django.utils import timezone
        days = (room.gift_deadline - timezone.now()).days
        if days > 0:
            text += f"\n⏰ До дедлайна: <b>{days}</b> дн."
        elif days == 0:
            text += f"\n🔥 <b>Дедлайн сегодня!</b>"
        else:
            text += f"\n⚠️ Дедлайн прошёл {abs(days)} дн. назад"

    await message.reply(text, parse_mode='HTML')


@router.message(Command("help_group"))
async def group_help(message: Message):
    if not is_group(message):
        return

    await message.reply(
        "🎅 <b>Бот Тайного Санты — справка для групп</b>\n\n"
        "<b>Команды:</b>\n"
        "/link_room КОД — привязать группу к комнате\n"
        "/unlink_room — отвязать группу\n"
        "/status — статус комнаты\n"
        "/deadline — дедлайн подарка\n"
        "/bought — кто купил, а кто нет\n\n"
        "ℹ️ Личные функции (Мои комнаты, чаты) — только в ЛС с ботом.",
        parse_mode='HTML',
    )


@router.message(Command("reveal"))
async def group_reveal(message: Message):
    """В группе: показать карту пар после дедлайна"""
    if not is_group(message):
        return

    room = await api.get_room_by_telegram_chat(message.chat.id)
    if not room:
        await message.reply(
            "Эта группа не привязана к комнате.\n"
            "Привязать: /link_room КОД"
        )
        return

    # Проверяем, что дедлайн прошёл
    if not await api.can_reveal_pairs(room):
        deadline_str = room.gift_deadline.strftime('%d.%m.%Y') if room.gift_deadline else 'не установлен'
        await message.reply(
            f"🔒 <b>Карта пар пока скрыта</b>\n\n"
            f"Она откроется после дедлайна подарка.\n"
            f"📅 Дедлайн: {deadline_str}",
            parse_mode='HTML'
        )
        return

    # Получаем карту пар
    pairs = await api.get_pairs_map(room)

    text = f"🎁 <b>Карта Сант — «{room.name}»</b>\n\n"
    text += f"Кто кому дарил:\n\n"

    for pair in pairs:
        santa_name = pair['santa_name']
        receiver_name = pair['receiver_name']

        # Помечаем админа короной
        santa_crown = "👑 " if pair['santa_is_admin'] else ""
        receiver_crown = "👑 " if pair['receiver_is_admin'] else ""

        text += f"{santa_crown}<b>{santa_name}</b> → {receiver_crown}<b>{receiver_name}</b>\n"

    text += f"\n✨ <i>Праздник удался!</i>"

    await message.reply(text, parse_mode='HTML')