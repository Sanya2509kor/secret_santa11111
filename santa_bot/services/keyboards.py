"""
Клавиатуры для бота.
"""

from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
)


def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Мои комнаты")],
            [KeyboardButton(text="💬 Чаты")],
            [KeyboardButton(text="🎁 Кому я дарю"), KeyboardButton(text="📝 Мои пожелания")],
            [KeyboardButton(text="🔗 Привязать аккаунт"), KeyboardButton(text="❓ Помощь")],
        ],
        resize_keyboard=True
    )


def confirm_link_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, это я", callback_data="link:confirm"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="link:cancel"),
        ]
    ])


def rooms_list_kb(rooms):
    """rooms — список словарей из api.get_rooms_with_stats()"""
    buttons = []
    for room in rooms:
        buttons.append([InlineKeyboardButton(
            text=f"🎄 {room['name']}",
            callback_data=f"room:{room['id']}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)





def room_actions_kb(room_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Кому я дарю", callback_data=f"santa:{room_id}")],
        [InlineKeyboardButton(text="📝 Пожелания получателя", callback_data=f"wishlist:{room_id}")],
        [InlineKeyboardButton(text="🔙 К комнатам", callback_data="back_rooms")],
    ])


def chats_list_kb(chats):
    """Клавиатура со списком чатов"""
    buttons = []
    for chat in chats:
        unread = f" 🔴 {chat['unread']}" if chat['unread'] > 0 else ""
        buttons.append([InlineKeyboardButton(
            text=f"{chat['title']} — {chat['room_name']}{unread}",
            callback_data=f"chat:{chat['id']}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def chat_actions_kb(chat_id):
    """Действия с конкретным чатом"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Написать", callback_data=f"chat_write:{chat_id}")],
        [InlineKeyboardButton(text="📜 История", callback_data=f"chat_history:{chat_id}")],
        [InlineKeyboardButton(text="🔙 К чатам", callback_data="back_chats")],
    ])


def cancel_kb():
    """Клавиатура с одной кнопкой «Отмена»"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_action")]
    ])


def wishlist_room_choice_kb(rooms):
    """Клавиатура выбора комнаты для редактирования wishlist"""
    buttons = []
    for room in rooms:
        buttons.append([InlineKeyboardButton(
            text=f"📝 {room['name']}",
            callback_data=f"wishlist_edit:{room['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_action")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def gift_room_choice_kb(rooms):
    """Список комнат для отметки покупки"""
    buttons = []
    for room in rooms:
        buttons.append([InlineKeyboardButton(
            text=f"🎁 {room['name']}",
            callback_data=f"gift_room:{room['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_action")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def rooms_list_for_reveal_kb(rooms):
    """Список комнат для раскрытия пар"""
    buttons = []
    for room in rooms:
        buttons.append([InlineKeyboardButton(
            text=f"🎁 {room['name']}",
            callback_data=f"reveal_room:{room['id']}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)