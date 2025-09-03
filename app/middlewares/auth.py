import logging
from typing import Callable, Awaitable, Any
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from ..config import settings

class WhitelistMiddleware(BaseMiddleware):
    def __init__(self):
        super().__init__()
        self.whitelist = set(settings.whitelist_ids)

    async def __call__(self,
                       handler: Callable[[TelegramObject, dict], Awaitable[Any]],
                       event: TelegramObject,
                       data: dict) -> Any:
        user_id = None
        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery) and event.from_user:
            user_id = event.from_user.id

        # Если это не Message/CallbackQuery (user_id=None) — пропускаем
        if user_id is None:
            logging.info("[WL] pass non-user update")
            return await handler(event, data)

        if user_id not in self.whitelist:
            logging.info(f"[WL] deny user_id={user_id}")
            return

        logging.info(f"[WL] allow user_id={user_id}")
        return await handler(event, data)
