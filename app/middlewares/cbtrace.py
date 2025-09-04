from aiogram import BaseMiddleware
from aiogram.types import Update
import logging
from typing import Callable, Dict, Any, Awaitable

class CallbackTraceMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any],
    ) -> Any:
        u = getattr(event, "event", None) or event
        d = getattr(u, "data", None)
        uid = getattr(getattr(u, "from_user", None), "id", None)
        hname = getattr(handler, "__name__", str(handler))
        logging.info(f"[CB->] handler={hname} data={d} from={uid}")
        res = await handler(event, data)
        logging.info(f"[CB<-] handler={hname} done")
        return res
