"""
Шаблоны текстов бота.
Никаких запросов к БД здесь быть НЕ ДОЛЖНО — только форматирование.
"""

from django.utils import timezone


def welcome_text(user):
    return (
        f"🎅 <b>Привет, {user.get_display_name()}!</b>\n\n"
        f"Я бот Тайного Санты. Вот что я умею:\n\n"
        f"📋 <b>Мои комнаты</b> — список ваших комнат\n"
        f"🎁 <b>Кому я дарю</b> — информация о получателе\n"
        f"📝 <b>Мои пожелания</b> — посмотреть wishlist\n"
        f"🔗 <b>Привязать аккаунт</b> — если ещё не привязали"
    )


def rooms_list_text(rooms):
    """rooms — список словарей из api.get_rooms_with_stats()"""
    text = f"📋 <b>Ваши комнаты ({len(rooms)}):</b>\n\n"
    for r in rooms:
        status = "✅" if r['draw_completed'] else "⏳"
        text += f"{status} <b>{r['name']}</b>\n"
        text += f"   Код: <code>{r['code']}</code> • Участников: {r['total']}\n\n"
    return text


def no_rooms_text():
    return (
        "У вас пока нет комнат 🎄\n\n"
        "Создайте комнату на сайте или присоединитесь по коду."
    )


def santa_info_text(info):
    text = f"🎁 <b>Вы — Тайный Санта для:</b>\n\n"
    text += f"👤 <b>{info['display_name']}</b>\n\n"
    if info['wishlist']:
        text += f"📝 <b>Пожелания:</b>\n{info['wishlist']}"
    else:
        text += "📝 Пожелания ещё не заполнены 😔"
    return text


def wishlist_text(info):
    if info['wishlist']:
        return (
            f"📝 <b>Пожелания получателя ({info['display_name']}):</b>\n\n"
            f"{info['wishlist']}"
        )
    return f"😔 {info['display_name']} ещё не заполнил пожелания"


def group_status_text(status):
    text = f"🎄 <b>Комната: {status['name']}</b>\n\n"
    text += f"👥 Участников: <b>{status['total']}</b>\n"

    if status['draw_completed']:
        text += f"🎲 Жеребьёвка: ✅ проведена\n"
    else:
        text += f"🎲 Жеребьёвка: ⏳ ожидается\n"

    if status['deadline']:
        days = (status['deadline'] - timezone.now()).days
        if days > 0:
            text += f"⏰ До дедлайна: <b>{days}</b> дн.\n"
        elif days == 0:
            text += f"⏰ <b>Дедлайн сегодня!</b>\n"
        else:
            text += f"⚠️ Дедлайн прошёл ({abs(days)} дн. назад)\n"

    return text


def group_deadline_text(deadline):
    if not deadline:
        return "⏰ Дедлайн не установлен"

    days = (deadline - timezone.now()).days
    date_str = deadline.strftime('%d.%m.%Y')

    if days > 0:
        return f"⏰ До дедлайна осталось <b>{days}</b> дн.\n📅 Дата: {date_str}"
    elif days == 0:
        return f"🔥 <b>Дедлайн сегодня!</b>\n📅 {date_str}"
    return f"⚠️ Дедлайн прошёл {abs(days)} дн. назад"