"""
Отметка «купил подарок» + команда /bought.
"""

import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.enums import ChatType

from services import api
from services.keyboards import main_menu, gift_room_choice_kb

logger = logging.getLogger(__name__)
router = Router()


# ─────────────────────────────────────────────
#  Только ЛС
# ─────────────────────────────────────────────
router.message.filter(lambda m: m.chat.type == ChatType.PRIVATE)
router.callback_query.filter(lambda c: c.message.chat.type == ChatType.PRIVATE)


# ─────────────────────────────────────────────
#  /bought — отметить покупку
# ─────────────────────────────────────────────
@router.message(Command("bought"))
async def cmd_bought(message: Message):
    user = await api.get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("Сначала привяжите аккаунт: /link")
        return

    rooms = await api.get_rooms_with_stats(user)
    # Фильтруем — только те, где жеребьёвка проведена
    rooms = [r for r in rooms if r['draw_completed']]

    if not rooms:
        await message.answer(
            "🎄 У вас нет комнат с проведённой жеребьёвкой.\n"
            "Отметить покупку можно после того, как админ проведёт жеребьёвку."
        )
        return

    await message.answer(
        "🎁 <b>В какой комнате отметить подарок?</b>",
        reply_markup=gift_room_choice_kb(rooms),
        parse_mode='HTML',
    )


# ─────────────────────────────────────────────
#  Callback: выбрана комната для отметки
# ─────────────────────────────────────────────
@router.callback_query(F.data.startswith("gift_room:"))
async def gift_room_selected(call: CallbackQuery):
    room_id = int(call.data.split(":")[1])
    user = await api.get_user_by_telegram_id(call.from_user.id)
    room = await api.get_room_by_id(room_id)

    if not room or not user:
        await call.answer("Ошибка", show_alert=True)
        return

    status = await api.get_gift_status(user, room)
    if not status:
        await call.answer("Вы не в этой комнате", show_alert=True)
        return

    if status['bought']:
        # Уже куплено — предложим снять отметку
        await call.message.edit_text(
            f"✅ <b>Уже отмечено!</b>\n\n"
            f"Комната: <b>{room.name}</b>\n"
            f"Отмечено: {status['bought_at'].strftime('%d.%m.%Y %H:%M')}\n\n"
            f"Хотите снять отметку?",
            parse_mode='HTML',
            reply_markup={
                'inline_keyboard': [
                    [{'text': '❌ Снять отметку', 'callback_data': f'gift_unbought:{room.id}'}],
                    [{'text': '🔙 Назад', 'callback_data': 'back_to_bought'}],
                ]
            },
        )
    else:
        # Ещё не куплено — предложим отметить
        await call.message.edit_text(
            f"🎁 <b>{room.name}</b>\n\n"
            f"📅 Дедлайн: {room.gift_deadline.strftime('%d.%m.%Y') if room.gift_deadline else 'не установлен'}\n"
            f"💰 Бюджет: {room.budget or 'не установлен'}\n\n"
            f"Отметить, что подарок уже куплен?",
            parse_mode='HTML',
            reply_markup={
                'inline_keyboard': [
                    [{'text': '✅ Да, купил(а)', 'callback_data': f'gift_bought:{room.id}'}],
                    [{'text': '🔙 Назад', 'callback_data': 'back_to_bought'}],
                ]
            },
        )


# ─────────────────────────────────────────────
#  Отметка «купил»
# ─────────────────────────────────────────────
@router.callback_query(F.data.startswith("gift_bought:"))
async def gift_bought(call: CallbackQuery):
    room_id = int(call.data.split(":")[1])
    user = await api.get_user_by_telegram_id(call.from_user.id)
    room = await api.get_room_by_id(room_id)

    if not room or not user:
        await call.answer("Ошибка", show_alert=True)
        return

    ok = await api.mark_gift_bought(user, room, bought=True)

    if ok:
        await call.message.edit_text(
            f"🎉 <b>Отлично!</b>\n\n"
            f"Отметка о покупке подарка в комнате «{room.name}» сохранена.\n\n"
            f"Ваш Санта и администратор увидят это в группе.",
            parse_mode='HTML',
        )
        await call.answer("✅ Отмечено!")
    else:
        await call.answer("Ошибка", show_alert=True)


# ─────────────────────────────────────────────
#  Снять отметку
# ─────────────────────────────────────────────
@router.callback_query(F.data.startswith("gift_unbought:"))
async def gift_unbought(call: CallbackQuery):
    room_id = int(call.data.split(":")[1])
    user = await api.get_user_by_telegram_id(call.from_user.id)
    room = await api.get_room_by_id(room_id)

    if not room or not user:
        await call.answer("Ошибка", show_alert=True)
        return

    await api.mark_gift_bought(user, room, bought=False)
    await call.message.edit_text(
        f"↩️ Отметка снята.\n\n"
        f"Будем напоминать о подарке в комнате «{room.name}».",
        parse_mode='HTML',
    )


# ─────────────────────────────────────────────
#  Назад к списку комнат
# ─────────────────────────────────────────────
@router.callback_query(F.data == "back_to_bought")
async def back_to_bought(call: CallbackQuery):
    user = await api.get_user_by_telegram_id(call.from_user.id)
    if not user:
        await call.answer("Ошибка", show_alert=True)
        return

    rooms = await api.get_rooms_with_stats(user)
    rooms = [r for r in rooms if r['draw_completed']]

    if not rooms:
        await call.message.edit_text("🎄 У вас нет комнат с жеребьёвкой.")
        return

    await call.message.edit_text(
        "🎁 <b>В какой комнате отметить подарок?</b>",
        reply_markup=gift_room_choice_kb(rooms),
        parse_mode='HTML',
    )


# ─────────────────────────────────────────────
#  Callback «Позже» из push-сообщения
# ─────────────────────────────────────────────
@router.callback_query(F.data == "gift_later")
async def gift_later(call: CallbackQuery):
    await call.answer("Поняли, напомним позже ⏰", show_alert=False)
    try:
        await call.message.delete()
    except:
        pass