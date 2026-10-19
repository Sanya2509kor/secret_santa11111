"""
Редактирование wishlist прямо в Telegram.
"""

import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from services import api
from services.keyboards import (
    main_menu, wishlist_room_choice_kb, cancel_kb,
)
from aiogram.enums import ChatType


logger = logging.getLogger(__name__)
router = Router()
router.message.filter(lambda m: m.chat.type == ChatType.PRIVATE)
router.callback_query.filter(lambda c: c.message.chat.type == ChatType.PRIVATE)


class WishlistStates(StatesGroup):
    waiting_text = State()


# ─────────────────────────────────────────────
#  Кнопка «📝 Мои пожелания»
# ─────────────────────────────────────────────
@router.message(F.text == "📝 Мои пожелания")
async def btn_wishlist(message: Message):
    user = await api.get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("Сначала привяжите аккаунт: /link")
        return

    rooms = await api.get_rooms_with_stats(user)
    if not rooms:
        await message.answer(
            "🎄 У вас пока нет комнат.\n"
            "Создайте или присоединитесь на сайте."
        )
        return

    await message.answer(
        "📝 <b>Выберите комнату для редактирования пожеланий:</b>",
        reply_markup=wishlist_room_choice_kb(rooms),
        parse_mode='HTML'
    )


@router.message(Command("wishlist"))
async def cmd_wishlist(message: Message):
    await btn_wishlist(message)


# ─────────────────────────────────────────────
#  Выбор комнаты → показать текущий wishlist
# ─────────────────────────────────────────────
@router.callback_query(F.data.startswith("wishlist_edit:"))
async def wishlist_edit(call: CallbackQuery, state: FSMContext):
    room_id = int(call.data.split(":")[1])
    user = await api.get_user_by_telegram_id(call.from_user.id)
    room = await api.get_room_by_id(room_id)

    if not room or not user:
        await call.answer("Ошибка", show_alert=True)
        return

    info = await api.get_my_wishlist_info(user, room)
    if not info:
        await call.answer("Вы не участник этой комнаты", show_alert=True)
        return

    current = info['wishlist'] or '(пока пусто)'
    await state.update_data(room_id=room_id, room_name=room.name)
    await state.set_state(WishlistStates.waiting_text)

    await call.message.answer(
        f"📝 <b>Комната «{room.name}»</b>\n\n"
        f"<b>Текущие пожелания:</b>\n"
        f"<i>{current}</i>\n\n"
        f"Отправьте новый текст пожеланий. Он <b>заменит</b> старый.\n"
        f"Можно указать: любимые книги, размер одежды, хобби, вкусы.\n\n"
        f"Отмена — /cancel",
        parse_mode='HTML',
        reply_markup=cancel_kb(),
    )
    await call.answer()


# ─────────────────────────────────────────────
#  Сохранение текста
# ─────────────────────────────────────────────
@router.message(WishlistStates.waiting_text, F.text)
async def wishlist_save(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text or text.lower() in ('/cancel', 'отмена'):
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=main_menu())
        return

    data = await state.get_data()
    room_id = data.get('room_id')
    room_name = data.get('room_name', 'комната')

    user = await api.get_user_by_telegram_id(message.from_user.id)
    if not user:
        await state.clear()
        await message.answer("Сначала привяжите аккаунт: /link", reply_markup=main_menu())
        return

    room = await api.get_room_by_id(room_id)
    if not room:
        await state.clear()
        await message.answer("Комната не найдена", reply_markup=main_menu())
        return

    ok = await api.update_wishlist(user, room, text)

    if not ok:
        await message.answer("❌ Не удалось сохранить")
        await state.clear()
        return

    await state.clear()
    await message.answer(
        f"✅ <b>Пожелания сохранены!</b>\n\n"
        f"Комната: «{room_name}»\n"
        f"Ваш Санта их уже видит.",
        parse_mode='HTML',
        reply_markup=main_menu()
    )