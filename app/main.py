import asyncio, logging, sys, traceback
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from .config import settings
from .db import init_db
from .handlers.player import player_router
from .handlers.admin import admin_router
from .middlewares.auth import WhitelistMiddleware

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s", stream=sys.stdout)

async def on_startup():
    logging.info(">>> Бот успешно запущен и готов к работе!")
    logging.info("Инициализация базы данных...")
    await init_db()
    logging.info("База готова.")

async def main():
    if not settings.bot_token:
        logging.error("BOT_TOKEN пуст. Проверь .env")
        sys.exit(1)

    await on_startup()

    bot = Bot(token=settings.bot_token)
    dp = Dispatcher(storage=MemoryStorage())

    # Логи по старту (для диагностики /panel и WL)
    logging.info(f"Admins: {settings.admin_ids}")
    logging.info(f"Whitelist: {settings.whitelist_ids}")

    # Ограничиваем доступ по whitelist (сообщения и коллбэки)
    wl = WhitelistMiddleware()
    dp.message.middleware(wl)
    dp.callback_query.middleware(wl)

    # Подключаем роутеры
    dp.include_router(player_router)
    dp.include_router(admin_router)

    logging.info(">>> Бот начал слушать Telegram API...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info(">>> Бот остановлен пользователем.")
    except Exception as e:
        logging.error(f"Фатальная ошибка: {e}")
        traceback.print_exc()
