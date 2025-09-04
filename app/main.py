import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from .config import settings
from .db import init_db
from .handlers.player import player_router
from .handlers.admin import admin_router
from .handlers.review import review_router
from .middlewares.auth import WhitelistMiddleware
from .middlewares.cblog import CallbackLogMiddleware
from .middlewares.cbtrace import CallbackTraceMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    stream=sys.stdout,
)

async def on_startup():
    logging.info(">>> Бот успешно запущен и готов к работе!")
    await init_db()

async def main():
    if not settings.bot_token:
        logging.error("BOT_TOKEN пуст. Проверь .env")
        sys.exit(1)

    bot = Bot(token=settings.bot_token)
    dp = Dispatcher(storage=MemoryStorage())

    # middlewares: сперва логи коллбэков, затем whitelist
    dp.callback_query.middleware(CallbackLogMiddleware())
    dp.callback_query.middleware(CallbackTraceMiddleware())
    wl = WhitelistMiddleware()
    dp.message.middleware(wl)
    dp.callback_query.middleware(wl)

    # порядок роутеров: review -> admin -> player (review первым, чтобы перехватывать qa:*)
    dp.include_router(review_router)
    dp.include_router(admin_router)
    dp.include_router(player_router)

    await on_startup()
    logging.info(">>> Стартуем long-polling")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
