"""
Личные сообщения: комнаты, санта, пожелания.
"""

import logging
from django.utils import timezone

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from services import api
from services.keyboards import (
    main_menu, rooms_list_kb, room_actions_kb
)
from services.texts import (
    welcome_text, rooms_list_text, santa_info_text,
    wishlist_text, no_rooms_text
)
from aiogram.enums import ChatType


logger = logging.getLogger(__name__)
router = Router()


def is_private(message: Message) -> bool:
    return message.chat.type == ChatType.PRIVATE
# ─────────────────────────────────────────────
#  Кнопка «📋 Мои комнаты»
# ─────────────────────────────────────────────
@router.message(is_private, F.text == "📋 Мои комнаты")
async def my_rooms(message: Message):
    user = await api.get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("Сначала привяжите аккаунт: /link")
        return

    rooms = await api.get_rooms_with_stats(user)
    if not rooms:
        await message.answer(no_rooms_text())
        return

    await message.answer(
        rooms_list_text(rooms),
        reply_markup=rooms_list_kb(rooms),
        parse_mode='HTML'
    )


# ─────────────────────────────────────────────
#  Кнопка «🎁 Кому я дарю»
# ─────────────────────────────────────────────
@router.message(is_private, F.text == "🎁 Кому я дарю")
async def btn_my_santa(message: Message):
    user = await api.get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("Сначала привяжите аккаунт: /link")
        return

    rooms = await api.get_rooms_with_stats(user)
    if not rooms:
        await message.answer(no_rooms_text())
        return

    await message.answer(
        "🎁 <b>Выберите комнату, чтобы узнать, кому вы дарите:</b>",
        reply_markup=rooms_list_kb(rooms),
        parse_mode='HTML'
    )

# ─────────────────────────────────────────────
#  Команды-шорткаты
# ─────────────────────────────────────────────
@router.message(is_private, Command("my_rooms"))
async def cmd_my_rooms(message: Message):
    await my_rooms(message)


@router.message(is_private, Command("my_santa"))
async def cmd_my_santa(message: Message):
    await btn_my_santa(message)


@router.message(is_private, Command("status"))
async def cmd_status_private(message: Message):
    """В личке: показать статус всех комнат"""
    user = await api.get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("Сначала привяжите аккаунт: /link")
        return

    rooms = await api.get_rooms_with_stats(user)
    if not rooms:
        await message.answer(no_rooms_text())
        return

    text = "📊 <b>Статус ваших комнат:</b>\n\n"
    for r in rooms:
        draw = "✅" if r['draw_completed'] else "⏳"
        text += f"{draw} <b>{r['name']}</b> — {r['total']} чел.\n"
        if r['deadline']:
            days = (r['deadline'] - timezone.now()).days
            text += f"   ⏰ До дедлайна: {days} дн.\n"
        text += "\n"

    await message.answer(text, parse_mode='HTML')


# ─────────────────────────────────────────────
#  Callback: карточка комнаты
# ─────────────────────────────────────────────
@router.callback_query(F.data.startswith("room:"))
async def room_detail(call: CallbackQuery):
    room_id = int(call.data.split(":")[1])
    user = await api.get_user_by_telegram_id(call.from_user.id)
    room = await api.get_room_by_id(room_id)

    if not room or not user:
        await call.answer("Ошибка")
        return

    status = await api.get_room_status(room)

    text = f"🎄 <b>{status['name']}</b>\n\n"
    text += f"👥 Участников: {status['total']}\n"
    text += f"🎲 Жеребьёвка: {'✅ проведена' if status['draw_completed'] else '⏳ не проведена'}\n"
    if status['deadline']:
        days = (status['deadline'] - timezone.now()).days
        text += f"⏰ До дедлайна: {days} дн.\n"

    await call.message.edit_text(
        text,
        reply_markup=room_actions_kb(room_id),
        parse_mode='HTML'
    )


@router.callback_query(F.data == "back_rooms")
async def back_rooms(call: CallbackQuery):
    user = await api.get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer("Привяжите аккаунт: /link", show_alert=True)
        return

    rooms = await api.get_rooms_with_stats(user)
    if not rooms:
        await call.message.edit_text(no_rooms_text())
        return

    await call.message.edit_text(
        rooms_list_text(rooms),
        reply_markup=rooms_list_kb(rooms),
        parse_mode='HTML'
    )


@router.callback_query(F.data.startswith("santa:"))
async def santa_info(call: CallbackQuery):
    room_id = int(call.data.split(":")[1])
    user = await api.get_user_by_telegram_id(call.from_user.id)
    room = await api.get_room_by_id(room_id)

    info = await api.get_santa_info(user, room)
    if not info:
        await call.answer("Жеребьёвка ещё не проведена", show_alert=True)
        return

    await call.message.answer(santa_info_text(info), parse_mode='HTML')


@router.callback_query(F.data.startswith("wishlist:"))
async def receiver_wishlist(call: CallbackQuery):
    room_id = int(call.data.split(":")[1])
    user = await api.get_user_by_telegram_id(call.from_user.id)
    room = await api.get_room_by_id(room_id)

    info = await api.get_santa_info(user, room)
    if not info:
        await call.answer("Жеребьёвка ещё не проведена", show_alert=True)
        return

    await call.message.answer(wishlist_text(info), parse_mode='HTML')
