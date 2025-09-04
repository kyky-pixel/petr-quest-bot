from aiogram import BaseMiddleware
from aiogram.types import Update
import logging
from typing import Callable, Dict, Any, Awaitable

class CallbackLogMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any],
    ) -> Any:
        # Пишем в логи все callback_query (и пропускаем дальше)
        u = getattr(event, "event", None) or event
        try:
            d = getattr(u, "data", None)
            uid = getattr(getattr(u, "from_user", None), "id", None)
            if d:
                logging.info(f"[CB] data={d} from={uid}")
        except Exception:
            pass
        return await handler(event, data)
