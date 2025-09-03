import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

debug_router = Router()

@debug_router.message(Command("ping"))
async def ping_cmd(m: Message):
    logging.info(f"/ping from {m.from_user.id}")
    await m.reply("pong")

@debug_router.message(F.text)
async def any_text(m: Message):
    logging.info(f"[TEXT] from {m.from_user.id}: {m.text}")
