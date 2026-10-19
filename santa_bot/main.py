"""
Точка входа Telegram-бота «Тайный Санта».
Работает через Cloudflare Worker-прокси.
"""

import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.enums import ParseMode

from config import BOT_TOKEN
from handlers import start, link, chat, private, group, wishlist, gifts, reveal
from tasks import daily_deadline_reminders, gift_check_scheduler


# ─────────────────────────────────────────────
#  Логирование
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger(__name__)





# ─────────────────────────────────────────────
#  Cloudflare Worker прокси
# ─────────────────────────────────────────────
WORKER_URL = os.getenv(
    'TELEGRAM_WORKER_URL',
    'https://autumn-band-ae30.korchemkins0.workers.dev'
)

POLLING_TIMEOUT = 15  # < 30 сек из-за лимита Cloudflare


# ─────────────────────────────────────────────
#  Основная функция
# ─────────────────────────────────────────────
async def main():
    if not BOT_TOKEN or BOT_TOKEN == 'YOUR_TOKEN_HERE':
        logger.error("❌ BOT_TOKEN не задан!")
        return

    logger.info("🔌 Подключаюсь через прокси: %s", WORKER_URL)

    session = AiohttpSession(
        api=TelegramAPIServer.from_base(WORKER_URL)
    )

    bot = Bot(
        token=BOT_TOKEN,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # Проверим связь с Telegram
    try:
        me = await bot.get_me()
        logger.info("✅ Бот авторизован: @%s (id=%s)", me.username, me.id)
    except Exception as e:
        logger.exception("❌ Не удалось получить данные бота: %s", e)
        await session.close()
        return

    # Роутеры
    dp = Dispatcher()
    dp.include_router(start.router)
    dp.include_router(link.router)
    dp.include_router(chat.router)
    dp.include_router(wishlist.router)
    dp.include_router(gifts.router)
    dp.include_router(reveal.router)
    dp.include_router(private.router)
    dp.include_router(group.router)

    # ═══ Запуск фоновых задач ═══
    asyncio.create_task(daily_deadline_reminders(bot))
    asyncio.create_task(gift_check_scheduler(bot))  # ⭐ НОВОЕ
    logger.info("⏰ Задачи напоминаний запущены")

    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except Exception as e:
        logger.warning("⚠️ Не удалось удалить webhook: %s", e)

    logger.info("🚀 Бот запущен. Ожидаю сообщения...")

    try:
        await dp.start_polling(bot, polling_timeout=POLLING_TIMEOUT)
    finally:
        await session.close()
        logger.info("🛑 Бот остановлен")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен пользователем (Ctrl+C)")
    except Exception as e:
        logger.exception("💥 Критическая ошибка: %s", e)