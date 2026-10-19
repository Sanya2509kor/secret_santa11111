# handlers/reveal.py

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.enums import ChatType

from services import api
from services.keyboards import main_menu

router = Router()

router.message.filter(lambda m: m.chat.type == ChatType.PRIVATE)
router.callback_query.filter(lambda c: c.message.chat.type == ChatType.PRIVATE)


@router.message(Command("reveal"))
async def cmd_reveal(message: Message):
    """В ЛС: показать карту пар по комнате"""
    user = await api.get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("Сначала привяжите аккаунт: /link")
        return

    rooms = await api.get_rooms_with_stats(user)
    # Фильтруем: только те, где дедлайн прошёл
    revealed_rooms = []
    for r in rooms:
        room_obj = await api.get_room_by_id(r['id'])
        if room_obj and await api.can_reveal_pairs(room_obj):
            revealed_rooms.append(r)

    if not revealed_rooms:
        await message.answer(
            "🔒 <b>Пока нечего раскрывать</b>\n\n"
            "Карта пар откроется после дедлайна в комнатах, где вы участвуете.",
            parse_mode='HTML'
        )
        return

    if len(revealed_rooms) == 1:
        # Одна комната — сразу показываем
        room = await api.get_room_by_id(revealed_rooms[0]['id'])
        await _send_pairs(message, room)
        return

    # Несколько — предлагаем выбрать
    from services.keyboards import rooms_list_kb
    await message.answer(
        "🎁 <b>Выберите комнату:</b>",
        reply_markup=rooms_list_for_reveal_kb(revealed_rooms),
        parse_mode='HTML'
    )


@router.callback_query(F.data.startswith("reveal_room:"))
async def reveal_room_selected(call: CallbackQuery):
    room_id = int(call.data.split(":")[1])
    room = await api.get_room_by_id(room_id)

    if not room or not await api.can_reveal_pairs(room):
        await call.answer("Ещё не время 🙈", show_alert=True)
        return

    await call.answer()
    await _send_pairs(call.message, room)


async def _send_pairs(message, room):
    """Отправляет карту пар"""
    pairs = await api.get_pairs_map(room)

    text = f"🎁 <b>Карта Сант — «{room.name}»</b>\n\n"
    for pair in pairs:
        santa_crown = "👑 " if pair['santa_is_admin'] else ""
        receiver_crown = "👑 " if pair['receiver_is_admin'] else ""
        text += f"{santa_crown}<b>{pair['santa_name']}</b> → {receiver_crown}<b>{pair['receiver_name']}</b>\n"

    text += f"\n✨ <i>Праздник удался!</i>"

    await message.answer(text, parse_mode='HTML', reply_markup=main_menu())