"""
Привязка Telegram к аккаунту через подтверждение номера телефона.
Пользователь жмёт "Поделиться номером" — Telegram передаёт его боту.
"""

import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message, KeyboardButton, ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from services import api
from services.keyboards import main_menu
from aiogram.enums import ChatType


logger = logging.getLogger(__name__)
router = Router()
router.message.filter(lambda m: m.chat.type == ChatType.PRIVATE)
router.callback_query.filter(lambda c: c.message.chat.type == ChatType.PRIVATE)

# ─────────────────────────────────────────────
#  Нормализация номера
# ─────────────────────────────────────────────
def normalize_phone(raw):
    """
    Приводит номер к виду 7XXXXXXXXXX (11 цифр).
    Возвращает None, если невалиден.

    Примеры:
        +79991234567 → 79991234567
        89991234567  → 79991234567
        9991234567   → 79991234567
        +7 999 123-45-67 → 79991234567
    """
    if not raw:
        return None
    digits = ''.join(filter(str.isdigit, str(raw)))

    if len(digits) == 11 and digits.startswith('8'):
        digits = '7' + digits[1:]
    elif len(digits) == 11 and digits.startswith('7'):
        pass
    elif len(digits) == 10:
        digits = '7' + digits
    else:
        return None

    if len(digits) != 11:
        return None
    return digits


# ─────────────────────────────────────────────
#  Клавиатура с кнопкой "Поделиться номером"
# ─────────────────────────────────────────────
def phone_request_kb():
    """Reply-клавиатура с кнопкой запроса номера."""
    return ReplyKeyboardMarkup(
        keyboard=[[
            KeyboardButton(
                text="📱 Поделиться номером",
                request_contact=True,
            )
        ]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


# ─────────────────────────────────────────────
#  /link
# ─────────────────────────────────────────────
@router.message(Command("link"))
async def cmd_link(message: Message):
    # Уже привязан?
    existing = await api.get_user_by_telegram_id(message.from_user.id)
    if existing:
        await message.answer(
            f"✅ Ваш Telegram уже привязан к аккаунту "
            f"<b>{existing.get_display_name()}</b>.\n\n"
            f"Отвязать: /unlink",
            parse_mode='HTML',
            reply_markup=main_menu(),
        )
        return

    # Rate-limit
    allowed = await api.check_rate_limit(
        telegram_id=message.from_user.id,
        action='link_contact',
        max_attempts=5,
        window_minutes=15,
    )
    if not allowed:
        await message.answer("⛔️ Слишком много попыток. Попробуйте через 15 минут.")
        return

    await message.answer(
        "🔐 <b>Привязка аккаунта</b>\n\n"
        "Нажмите кнопку ниже, чтобы поделиться своим номером телефона.\n"
        "Он должен совпадать с номером, который вы указали на сайте.\n\n"
        "Если что-то не совпадёт — попросим зарегистрироваться или проверить номер.",
        parse_mode='HTML',
        reply_markup=phone_request_kb(),
    )


# ─────────────────────────────────────────────
#  Обработка полученного контакта
# ─────────────────────────────────────────────
@router.message(F.contact)
async def handle_contact(message: Message):
    contact = message.contact

    # Защита: пользователь может поделиться чужим контактом
    # (переслать). Проверяем, что это его собственный номер.
    if contact.user_id != message.from_user.id:
        await message.answer(
            "❌ Пожалуйста, поделитесь <b>своим</b> номером, а не чужим контактом.\n\n"
            "Нажмите кнопку ещё раз и выберите свой контакт.",
            parse_mode='HTML',
            reply_markup=phone_request_kb(),
        )
        return

    # Уже привязан?
    existing = await api.get_user_by_telegram_id(message.from_user.id)
    if existing:
        await message.answer(
            f"✅ Ваш Telegram уже привязан к аккаунту "
            f"<b>{existing.get_display_name()}</b>.",
            parse_mode='HTML',
            reply_markup=main_menu(),
        )
        return

    # Нормализуем номер
    raw_phone = contact.phone_number
    normalized = normalize_phone(raw_phone)

    if not normalized:
        await message.answer(
            "❌ Не удалось распознать номер.\n"
            "Попробуйте ещё раз или обратитесь в поддержку.",
            reply_markup=phone_request_kb(),
        )
        return

    # Ищем пользователя в БД
    result = await api.find_user_by_normalized_phone(normalized)

    if result is None:
        await message.answer(
            f"❌ <b>Аккаунт с номером {raw_phone} не найден на сайте</b>\n\n"
            f"Возможные причины:\n"
            f"• Вы ещё не зарегистрированы\n"
            f"• На сайте указан другой номер\n\n"
            f"Зарегистрируйтесь на "
            f"<a href='https://24santa-secret.ru/register/'>24santa-secret.ru</a> "
            f"и попробуйте снова командой /link",
            parse_mode='HTML',
            disable_web_page_preview=True,
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    if result.get('already_linked'):
        await message.answer(
            "⚠️ Этот аккаунт уже привязан к другому Telegram-аккаунту.\n\n"
            "Если это ваш второй аккаунт — отвяжите старый через сайт "
            "или обратитесь в поддержку.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    # Привязываем
    user, status = await api.attach_telegram_by_contact(
        telegram_id=message.from_user.id,
        user_id=result['user_id'],
        username=message.from_user.username or '',
        first_name=message.from_user.first_name or '',
    )

    if not user:
        await message.answer(f"❌ Ошибка: {status}", reply_markup=ReplyKeyboardRemove())
        return

    await message.answer(
        f"✅ <b>Готово!</b>\n\n"
        f"Ваш Telegram привязан к аккаунту <b>{user.get_display_name()}</b>.\n\n"
        f"Теперь я буду присылать:\n"
        f"• 💬 уведомления о сообщениях\n"
        f"• ⏰ напоминания о дедлайнах\n"
        f"• 🎁 информацию о ваших комнатах\n\n"
        f"Открыть меню: /start",
        parse_mode='HTML',
        reply_markup=main_menu(),
    )
    logger.info("✅ Привязка: user=%s, tg=%s", user.phone, message.from_user.id)


# ─────────────────────────────────────────────
#  /unlink
# ─────────────────────────────────────────────
@router.message(Command("unlink"))
async def cmd_unlink(message: Message):
    user = await api.get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("У вас нет привязанного аккаунта.")
        return

    ok = await api.detach_telegram(message.from_user.id)
    if ok:
        await message.answer(
            f"✅ Аккаунт <b>{user.get_display_name()}</b> отвязан.\n"
            f"Привязать заново: /link",
            parse_mode='HTML',
        )
    else:
        await message.answer("❌ Не удалось отвязать. Попробуйте позже.")


# ─────────────────────────────────────────────
#  /cancel (универсальный)
# ─────────────────────────────────────────────
@router.message(Command("cancel"))
async def cmd_cancel(message: Message):
    await message.answer(
        "✅ Действие отменено.",
        reply_markup=main_menu(),
    )