"""
Чаты Санта ↔ Получатель прямо в Telegram.
Сообщения синхронизируются с чатами на сайте (общая БД).
"""

import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from services import api
from services.keyboards import (
    main_menu, chats_list_kb, chat_actions_kb,
    cancel_kb,
)
from aiogram.enums import ChatType


logger = logging.getLogger(__name__)
router = Router()
router.message.filter(lambda m: m.chat.type == ChatType.PRIVATE)
router.callback_query.filter(lambda c: c.message.chat.type == ChatType.PRIVATE)

class ChatStates(StatesGroup):
    waiting_message = State()


# ─────────────────────────────────────────────
#  Кнопка «💬 Чаты» в главном меню
# ─────────────────────────────────────────────
@router.message(F.text == "💬 Чаты")
async def btn_chats(message: Message):
    user = await api.get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("Сначала привяжите аккаунт: /link")
        return

    chats = await api.get_user_chats_with_stats(user)
    if not chats:
        await message.answer(
            "💬 <b>У вас пока нет активных чатов.</b>\n\n"
            "Чаты появятся после жеребьёвки в комнатах.",
            parse_mode='HTML'
        )
        return

    await message.answer(
        "💬 <b>Ваши чаты:</b>\n\n"
        "Выберите, с кем хотите поговорить.",
        reply_markup=chats_list_kb(chats),
        parse_mode='HTML'
    )


@router.message(Command("chats"))
async def cmd_chats(message: Message):
    await btn_chats(message)


# ─────────────────────────────────────────────
#  Выбор чата → показать инфо + действия
# ─────────────────────────────────────────────
@router.callback_query(F.data.startswith("chat:"))
async def chat_detail(call: CallbackQuery):
    chat_id = int(call.data.split(":")[1])
    user = await api.get_user_by_telegram_id(call.from_user.id)
    chat = await api.get_chat_by_id(chat_id, user)

    if not chat:
        await call.answer("Чат не найден", show_alert=True)
        return

    info = await api.get_chat_info(chat)

    text = (
        f"💬 <b>Чат: {info['title']}</b>\n\n"
        f"<b>Комната:</b> {info['room_name']}\n"
        f"<b>Собеседник:</b> {info['other_name']}\n"
    )
    if info['last_message']:
        text += f"\n<b>Последнее сообщение:</b>\n<i>{info['last_message'][:200]}</i>\n"

    # Пометить сообщения прочитанными
    await api.mark_chat_read(chat_id, user)

    await call.message.edit_text(
        text,
        reply_markup=chat_actions_kb(chat_id),
        parse_mode='HTML'
    )


# ─────────────────────────────────────────────
#  История сообщений
# ─────────────────────────────────────────────
@router.callback_query(F.data.startswith("chat_history:"))
async def chat_history(call: CallbackQuery):
    chat_id = int(call.data.split(":")[1])
    user = await api.get_user_by_telegram_id(call.from_user.id)
    chat = await api.get_chat_by_id(chat_id, user)

    if not chat:
        await call.answer("Чат не найден", show_alert=True)
        return

    messages = await api.get_chat_messages(chat_id, limit=20)
    if not messages:
        await call.message.answer("📭 Сообщений пока нет")
        return

    text = "📜 <b>Последние 20 сообщений:</b>\n\n"
    for msg in messages:
        sender = "👤 Вы" if msg['is_own'] else f"👤 {msg['sender']}"
        time = msg['timestamp']
        content = (msg['content'] or '📎 Медиа')[:150]
        text += f"<b>{sender}</b> [{time}]:\n{content}\n\n"

    await call.message.answer(text, parse_mode='HTML')


# ─────────────────────────────────────────────
#  Начать писать сообщение
# ─────────────────────────────────────────────
@router.callback_query(F.data.startswith("chat_write:"))
async def chat_write_start(call: CallbackQuery, state: FSMContext):
    chat_id = int(call.data.split(":")[1])
    user = await api.get_user_by_telegram_id(call.from_user.id)
    chat = await api.get_chat_by_id(chat_id, user)

    if not chat:
        await call.answer("Чат не найден", show_alert=True)
        return

    await state.update_data(chat_id=chat_id)
    await state.set_state(ChatStates.waiting_message)

    await call.message.answer(
        "✍️ <b>Введите сообщение:</b>\n\n"
        "Отправьте текст, и он уйдёт собеседнику.\n"
        "Для отмены: /cancel",
        parse_mode='HTML',
        reply_markup=cancel_kb(),
    )
    await call.answer()


# ─────────────────────────────────────────────
#  Сохранить сообщение из бота
# ─────────────────────────────────────────────
@router.message(ChatStates.waiting_message, F.text)
async def chat_send(message: Message, state: FSMContext):
    data = await state.get_data()
    chat_id = data.get('chat_id')

    if not chat_id:
        await state.clear()
        await message.answer("❌ Сессия истекла. Откройте чат заново.", reply_markup=main_menu())
        return

    text = message.text.strip()
    if not text:
        await message.answer("❌ Сообщение не может быть пустым")
        return

    user = await api.get_user_by_telegram_id(message.from_user.id)
    chat = await api.get_chat_by_id(chat_id, user)

    if not chat:
        await state.clear()
        await message.answer("❌ Чат не найден", reply_markup=main_menu())
        return

    # Сохраняем в БД (и в парный чат тоже)
    ok = await api.save_message_from_telegram(chat_id, user, text)

    if not ok:
        await message.answer("❌ Не удалось отправить сообщение")
        await state.clear()
        return

    await state.clear()
    await message.answer(
        "✅ <b>Сообщение отправлено!</b>",
        parse_mode='HTML',
        reply_markup=main_menu()
    )


# ─────────────────────────────────────────────
#  Ответ на уведомление (кнопка «↩️ Ответить»)
# ─────────────────────────────────────────────
@router.callback_query(F.data.startswith("reply_chat:"))
async def reply_chat(call: CallbackQuery, state: FSMContext):
    chat_id = int(call.data.split(":")[1])
    user = await api.get_user_by_telegram_id(call.from_user.id)
    chat = await api.get_chat_by_id(chat_id, user)

    if not chat:
        await call.answer("Чат не найден", show_alert=True)
        return

    await state.update_data(chat_id=chat_id)
    await state.set_state(ChatStates.waiting_message)

    await call.message.answer(
        "✍️ <b>Введите ответ:</b>",
        parse_mode='HTML',
        reply_markup=cancel_kb(),
    )
    await call.answer()


@router.callback_query(F.data == "back_chats")
async def back_chats(call: CallbackQuery):
    user = await api.get_user_by_telegram_id(call.from_user.id)
    chats = await api.get_user_chats_with_stats(user)
    if not chats:
        await call.message.edit_text("💬 У вас пока нет чатов")
        return
    await call.message.edit_text(
        "💬 <b>Ваши чаты:</b>",
        reply_markup=chats_list_kb(chats),
        parse_mode='HTML'
    )


@router.callback_query(F.data == "cancel_action")
async def cancel_action(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("❌ Действие отменено")
    await call.answer()