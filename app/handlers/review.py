import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery

from ..db import get_db
from ..xp import add_xp
from ..keyboards import admin_review_kb, quest_actions_kb  # admin_review_kb пригодится позже
from ..config import settings

review_router = Router()

@review_router.callback_query(F.data.startswith("qa:approve:"))
async def qa_approve(c: CallbackQuery):
    try:
        qid = int(c.data.split(":")[2])
    except Exception:
        return await c.answer("Некорректный идентификатор", show_alert=True)

    async with get_db() as db:
        cur = await db.execute("SELECT assigned_to, base_xp FROM quests WHERE id=?", (qid,))
        row = await cur.fetchone()
        if not row:
            return await c.answer("Квест не найден", show_alert=True)
        user_id, base_xp = row

        curu = await db.execute("SELECT tg_id, level FROM users WHERE id=?", (user_id,))
        urow = await curu.fetchone()
        tg_id = urow[0] if urow else None
        level_before = urow[1] if urow else None

        await db.execute("UPDATE quests SET state='approved' WHERE id=?", (qid,))
        await db.execute("UPDATE submissions SET state='approved' WHERE quest_id=?", (qid,))
        await add_xp(db, user_id, base_xp, reason="quest_approved", meta={"quest_id": qid})

        cura = await db.execute("SELECT level FROM users WHERE id=?", (user_id,))
        arow = await cura.fetchone()
        level_after = arow[0] if arow else None

        await db.commit()

    # ответ админу
    await c.answer("Подтверждено ✅", show_alert=False)
    try:
        await c.message.edit_text(c.message.text + "\n\n✅ Подтверждено")
    except Exception:
        pass
    try:
        await c.message.answer(f"Квест #{qid} подтверждён. Начислено +{base_xp} XP.")
    except Exception:
        pass

    # уведомление игроку
    if tg_id:
        text = f"✅ Квест #{qid} принят! Начислено +{base_xp} XP."
        if (level_before is not None) and (level_after is not None) and (level_after > level_before):
            text += f"\n🎉 Уровень повышен: {level_before} → {level_after}!"
        try:
            await c.bot.send_message(tg_id, text)
        except Exception as e:
            logging.error(f"player notify approve failed: {e}")

@review_router.callback_query(F.data.startswith("qa:reject:"))
async def qa_reject(c: CallbackQuery):
    try:
        qid = int(c.data.split(":")[2])
    except Exception:
        return await c.answer("Некорректный идентификатор", show_alert=True)

    async with get_db() as db:
        cur = await db.execute("SELECT assigned_to FROM quests WHERE id=?", (qid,))
        row = await cur.fetchone()
        if not row:
            return await c.answer("Квест не найден", show_alert=True)
        user_id = row[0]

        curu = await db.execute("SELECT tg_id FROM users WHERE id=?", (user_id,))
        urow = await curu.fetchone()
        tg_id = urow[0] if urow else None

        await db.execute("UPDATE submissions SET state='rejected' WHERE quest_id=?", (qid,))
        await db.execute("UPDATE quests SET state='returned' WHERE id=?", (qid,))
        await db.commit()

    await c.answer("Отклонено ❌", show_alert=False)
    try:
        await c.message.edit_text(c.message.text + "\n\n❌ Отклонено")
    except Exception:
        pass
    try:
        await c.message.answer(f"Квест #{qid} отклонён. Вернул на доработку.")
    except Exception:
        pass

    if tg_id:
        try:
            await c.bot.send_message(
                tg_id,
                f"❌ Квест #{qid} отклонён. Доработай и сдавай снова.",
                reply_markup=quest_actions_kb(qid, "returned")
            )
        except Exception as e:
            logging.error(f"player notify reject failed: {e}")
import logging
from aiogram import F
from aiogram.types import CallbackQuery
from .review import review_router  # сам себя не перетираем, просто получаем router
from ..db import get_db
from ..xp import add_xp
from ..keyboards import quest_actions_kb

@review_router.callback_query(F.data.startswith("qa:approve:"))
async def qa_approve_verbose(c: CallbackQuery):
    logging.info(f"[QA_APPROVE:IN] raw={c.data} from={getattr(c.from_user,'id',None)}")
    try:
        qid = int(c.data.split(":")[2])
    except Exception as e:
        logging.error(f"[QA_APPROVE] bad qid: {e}")
        return await c.answer("Некорректный идентификатор", show_alert=True)

    tg_id = None
    base_xp = 0
    level_before = level_after = None

    try:
        async with get_db() as db:
            cur = await db.execute("SELECT assigned_to, base_xp FROM quests WHERE id=?", (qid,))
            row = await cur.fetchone()
            if not row:
                logging.warning(f"[QA_APPROVE] quest {qid} not found")
                return await c.answer("Квест не найден", show_alert=True)
            user_id, base_xp = row

            curu = await db.execute("SELECT tg_id, level FROM users WHERE id=?", (user_id,))
            urow = await curu.fetchone()
            tg_id = urow[0] if urow else None
            level_before = urow[1] if urow else None

            await db.execute("UPDATE quests SET state='approved' WHERE id=?", (qid,))
            await db.execute("UPDATE submissions SET state='approved' WHERE quest_id=?", (qid,))
            await add_xp(db, user_id, base_xp, reason="quest_approved", meta={"quest_id": qid})

            cura = await db.execute("SELECT level FROM users WHERE id=?", (user_id,))
            arow = await cura.fetchone()
            level_after = arow[0] if arow else None

            await db.commit()
            logging.info(f"[QA_APPROVE] qid={qid} user_id={user_id} xp=+{base_xp} lvl:{level_before}->{level_after}")
    except Exception as e:
        logging.exception(f"[QA_APPROVE] db/logic error: {e}")
        return await c.answer("Ошибка при подтверждении", show_alert=True)

    # фидбек админу — делаем и через edit_text, и отдельным сообщением
    try:
        await c.answer("Подтверждено ✅", show_alert=False)
    except Exception: pass
    try:
        await c.message.edit_text((c.message.text or "") + "\n\n✅ Подтверждено")
    except Exception as e:
        logging.info(f"[QA_APPROVE] edit_text warn: {e}")
    try:
        await c.message.answer(f"Квест #{qid} подтверждён. Начислено +{base_xp} XP.")
    except Exception as e:
        logging.info(f"[QA_APPROVE] admin notify warn: {e}")

    # уведомление игроку
    if tg_id:
        text = f"✅ Квест #{qid} принят! Начислено +{base_xp} XP."
        if (level_before is not None) and (level_after is not None) and (level_after > level_before):
            text += f"\n🎉 Уровень повышен: {level_before} → {level_after}!"
        try:
            await c.bot.send_message(tg_id, text)
        except Exception as e:
            logging.error(f"[QA_APPROVE] player notify error: {e}")
    logging.info(f"[QA_APPROVE:OUT] qid={qid}")

@review_router.callback_query(F.data.startswith("qa:reject:"))
async def qa_reject_verbose(c: CallbackQuery):
    logging.info(f"[QA_REJECT:IN] raw={c.data} from={getattr(c.from_user,'id',None)}")
    try:
        qid = int(c.data.split(":")[2])
    except Exception as e:
        logging.error(f"[QA_REJECT] bad qid: {e}")
        return await c.answer("Некорректный идентификатор", show_alert=True)

    tg_id = None
    try:
        async with get_db() as db:
            cur = await db.execute("SELECT assigned_to FROM quests WHERE id=?", (qid,))
            row = await cur.fetchone()
            if not row:
                logging.warning(f"[QA_REJECT] quest {qid} not found")
                return await c.answer("Квест не найден", show_alert=True)
            user_id = row[0]

            curu = await db.execute("SELECT tg_id FROM users WHERE id=?", (user_id,))
            urow = await curu.fetchone()
            tg_id = urow[0] if urow else None

            await db.execute("UPDATE submissions SET state='rejected' WHERE quest_id=?", (qid,))
            await db.execute("UPDATE quests SET state='returned' WHERE id=?", (qid,))
            await db.commit()
            logging.info(f"[QA_REJECT] qid={qid} user_id={user_id} -> returned")
    except Exception as e:
        logging.exception(f"[QA_REJECT] db/logic error: {e}")
        return await c.answer("Ошибка при отклонении", show_alert=True)

    # фидбек админу
    try:
        await c.answer("Отклонено ❌", show_alert=False)
    except Exception: pass
    try:
        await c.message.edit_text((c.message.text or "") + "\n\n❌ Отклонено")
    except Exception as e:
        logging.info(f"[QA_REJECT] edit_text warn: {e}")
    try:
        await c.message.answer(f"Квест #{qid} отклонён. Вернул на доработку.")
    except Exception as e:
        logging.info(f"[QA_REJECT] admin notify warn: {e}")

    # уведомление игроку
    if tg_id:
        try:
            await c.bot.send_message(
                tg_id,
                f"❌ Квест #{qid} отклонён. Доработай и сдавай снова.",
                reply_markup=quest_actions_kb(qid, "returned")
            )
        except Exception as e:
            logging.error(f"[QA_REJECT] player notify error: {e}")
    logging.info(f"[QA_REJECT:OUT] qid={qid}")
