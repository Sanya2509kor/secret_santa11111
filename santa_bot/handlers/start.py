"""
Стартовые команды: /start, /help.
"""

from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from services import api
from services.keyboards import main_menu
from aiogram.enums import ChatType


router = Router()
router.message.filter(lambda m: m.chat.type == ChatType.PRIVATE)
router.callback_query.filter(lambda c: c.message.chat.type == ChatType.PRIVATE)


@router.message(CommandStart())
async def cmd_start(message: Message):
    user = await api.get_user_by_telegram_id(message.from_user.id)

    if user:
        await message.answer(
            f"🎅 <b>С возвращением, {user.get_display_name()}!</b>\n\n"
            f"Что хотите сделать?",
            parse_mode='HTML',
            reply_markup=main_menu(),
        )
    else:
        await message.answer(
            "🎅 <b>Добро пожаловать в Тайного Санту!</b>\n\n"
            "Я помогу вам:\n"
            "• 📋 посмотреть ваши комнаты\n"
            "• 🎁 узнать, кому вы дарите\n"
            "• 📝 заполнить пожелания\n\n"
            "Для начала привяжите аккаунт сайта: /link",
            parse_mode='HTML',
        )


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "🎅 <b>Помощь</b>\n\n"
        "<b>Основные команды:</b>\n"
        "/start — начать заново\n"
        "/link — привязать аккаунт сайта\n"
        "/unlink — отвязать аккаунт\n"
        "/cancel — отменить текущее действие\n\n"
        "<b>В групповых чатах:</b>\n"
        "/link_room КОД — привязать группу к комнате\n"
        "/status — статус комнаты\n"
        "/deadline — сколько осталось до дедлайна\n\n"
        "По вопросам: сайт → «Поддержка»",
        parse_mode='HTML',
    )


@router.message(F.text == "❓ Помощь")
async def btn_help(message: Message):
    await cmd_help(message)


@router.message(F.text == "🔗 Привязать аккаунт")
async def btn_link(message: Message):
    await message.answer("Выполните команду /link")