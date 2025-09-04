import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

from ..config import settings
from ..db import get_db
from ..xp import add_xp
from ..keyboards import admin_main_kb, admin_review_kb, quest_actions_kb

admin_router = Router()
logging.info("admin_router loaded")

def is_admin(tg_id: int) -> bool:
    return tg_id in settings.admin_ids

# ----- /panel, выдача Пете, pending list — остаются как есть -----

@admin_router.callback_query(F.data.startswith("qa:approve:"))
async def qa_approve(c: CallbackQuery):
    qid = int(c.data.split(":")[2])
    async with get_db() as db:
        cur = await db.execute("SELECT assigned_to, base_xp FROM quests WHERE id=?", (qid,))
        row = await cur.fetchone()
        if not row:
            return await c.answer("Квест не найден", show_alert=True)
        user_id, base_xp = row
        total = base_xp
        curu = await db.execute("SELECT tg_id FROM users WHERE id=?", (user_id,))
        tg_row = await curu.fetchone()
        tg_id = tg_row[0] if tg_row else None
        await db.execute("UPDATE quests SET state='approved' WHERE id=?", (qid,))
        await db.execute("UPDATE submissions SET state='approved' WHERE quest_id=?", (qid,))
        await add_xp(db, user_id, total, reason="quest_approved", meta={"quest_id": qid})
        await db.commit()
    await c.answer("Подтверждено ✅")
    try:
        await c.message.edit_text(c.message.text + "\n\n✅ Подтверждено")
    except Exception:
        pass
    if tg_id:
        try:
            await c.message.bot.send_message(tg_id, f"✅ Квест #{qid} принят! Начислено {total} XP.")
        except Exception as e:
            logging.error(f"Не смог отправить игроку апрув: {e}")

@admin_router.callback_query(F.data.startswith("qa:reject:"))
async def qa_reject(c: CallbackQuery):
    qid = int(c.data.split(":")[2])
    async with get_db() as db:
        cur = await db.execute("SELECT assigned_to FROM quests WHERE id=?", (qid,))
        row = await cur.fetchone()
        if not row:
            return await c.answer("Квест не найден", show_alert=True)
        user_id = row[0]
        curu = await db.execute("SELECT tg_id FROM users WHERE id=?", (user_id,))
        tg_row = await curu.fetchone()
        tg_id = tg_row[0] if tg_row else None
        # Помечаем сабмишены rejected, а сам квест — accepted, чтобы можно было сразу пересдать
        await db.execute("UPDATE submissions SET state='rejected' WHERE quest_id=?", (qid,))
        await db.execute("UPDATE quests SET state='accepted' WHERE id=?", (qid,))
        await db.commit()
    await c.answer("Отклонено ❌")
    try:
        await c.message.edit_text(c.message.text + "\n\n❌ Отклонено")
    except Exception:
        pass
    if tg_id:
        try:
            await c.message.bot.send_message(
                tg_id,
                f"❌ Квест #{qid} отклонён. Доработай и сдавай снова.",
                reply_markup=quest_actions_kb(qid, "accepted")
            )
        except Exception as e:
            logging.error(f"Не смог отправить игроку реджект: {e}")

# текстовые /approve /reject — оставь как дубль, при reject тоже переводи квест в 'accepted'
@admin_router.message(Command("reject"))
async def reject_cmd(m: Message):
    if not is_admin(m.from_user.id):
        return
    parts = m.text.split()
    if len(parts) < 2:
        return await m.reply("Формат: /reject <quest_id>")
    qid = int(parts[1])
    async with get_db() as db:
        cur = await db.execute("SELECT assigned_to FROM quests WHERE id=?", (qid,))
        row = await cur.fetchone()
        if not row:
            return await m.reply("Квест не найден")
        user_id = row[0]
        curu = await db.execute("SELECT tg_id FROM users WHERE id=?", (user_id,))
        tg_row = await curu.fetchone()
        tg_id = tg_row[0] if tg_row else None
        await db.execute("UPDATE submissions SET state='rejected' WHERE quest_id=?", (qid,))
        await db.execute("UPDATE quests SET state='accepted' WHERE id=?", (qid,))
        await db.commit()
    await m.reply(f"Квест #{qid} отклонён (разрешена пересдача).")
    if tg_id:
        try:
            await m.bot.send_message(
                tg_id,
                f"❌ Квест #{qid} отклонён. Доработай и сдавай снова.",
                reply_markup=quest_actions_kb(qid, "accepted")
            )
        except Exception as e:
            logging.error(f"Не смог отправить игроку реджект: {e}")
@admin_router.message(Command("ping"))
async def ping(m: Message):
    if not is_admin(m.from_user.id):
        return
    await m.reply("pong")
