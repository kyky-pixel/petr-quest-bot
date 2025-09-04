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

# =========================
#     СЛУЖЕБНЫЕ КОМАНДЫ
# =========================
@admin_router.message(Command("ping"))
async def ping(m: Message):
    if not is_admin(m.from_user.id):
        return
    await m.reply("pong")

@admin_router.message(Command("whoami"))
async def whoami(m: Message):
    await m.reply(
        f"uid={m.from_user.id}\n"
        f"admin={m.from_user.id in settings.admin_ids}\n"
        f"whitelisted={((not settings.whitelist_ids) or (m.from_user.id in settings.whitelist_ids))}"
    )

# =========================
#        АДМИН-ПАНЕЛЬ
# =========================
@admin_router.message(Command("panel"))
async def panel_cmd(m: Message):
    if not is_admin(m.from_user.id):
        return
    try:
        await m.reply("Админ-панель:", reply_markup=admin_main_kb())
    except Exception as e:
        logging.error(f"/panel error: {e}")
        await m.reply(f"Админ-панель (без клавиатуры). Ошибка: {e}")

@admin_router.message(F.text == "📝 Ожидают проверки")
async def pending_review(m: Message):
    if not is_admin(m.from_user.id):
        return
    async with get_db() as db:
        cur = await db.execute(
            "SELECT q.id, u.name, q.title, q.base_xp FROM quests q "
            "JOIN users u ON u.id = q.assigned_to "
            "WHERE q.state='submitted' ORDER BY q.id DESC"
        )
        rows = await cur.fetchall()
    if not rows:
        return await m.reply("Нет квестов на проверке.")
    for qid, uname, title, xp in rows:
        await m.answer(f"#{qid} — {title} (от {uname}) +{xp} XP", reply_markup=admin_review_kb(qid))

# =========================
#    ВЫДАТЬ (временно — МНЕ)
# =========================
class GivePetr(StatesGroup):
    wait_title = State()
    wait_xp = State()

@admin_router.message(F.text.in_(["➕ Выдать Пете", "➕ Выдать (временно — мне)"]))
async def give_start(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    await state.set_state(GivePetr.wait_title)
    await m.reply("Введи заголовок квеста:")

@admin_router.message(GivePetr.wait_title)
async def give_title(m: Message, state: FSMContext):
    await state.update_data(title=m.text.strip())
    await state.set_state(GivePetr.wait_xp)
    await m.reply("Сколько XP дать? (число, по умолчанию 10)")

@admin_router.message(GivePetr.wait_xp)
async def give_finish(m: Message, state: FSMContext):
    data = await state.get_data()
    title = data.get("title") or "Задача"
    try:
        xp = int(m.text.strip())
    except Exception:
        xp = 10

    # ЖЁСТКИЙ РЕЖИМ: назначаем квест именно автору команды
    async with get_db() as db:
        # убеждаемся, что автор есть в users
        cur_self = await db.execute("SELECT id, tg_id, name FROM users WHERE tg_id=?", (m.from_user.id,))
        self_row = await cur_self.fetchone()
        if not self_row:
            await db.execute(
                "INSERT INTO users(tg_id, name) VALUES(?,?)",
                (m.from_user.id, f"@{m.from_user.username}" if m.from_user.username else m.from_user.full_name)
            )
            await db.commit()
            cur_self = await db.execute("SELECT id, tg_id, name FROM users WHERE tg_id=?", (m.from_user.id,))
            self_row = await cur_self.fetchone()

        assigned_user_id, assigned_tg_id = self_row[0], self_row[1]

        # создаём квест
        await db.execute(
            "INSERT INTO quests(title, flavor_text, base_xp, tag, deadline_at, state, created_by, assigned_to) "
            "VALUES(?,?,?,?,?,'pending',?,?)",
            (title, None, xp, None, None, m.from_user.id, assigned_user_id)
        )
        cur2 = await db.execute("SELECT last_insert_rowid()")
        qid = (await cur2.fetchone())[0]
        await db.commit()

    await state.clear()
    await m.reply(f"Квест выдан: #{qid} {title} (+{xp} XP)")

    # Уведомление исполнителю (тебе)
    try:
        await m.bot.send_message(
            assigned_tg_id,
            f"🎯 Новый квест!\n\n#{qid} — {title}\nXP: +{xp}",
            reply_markup=quest_actions_kb(qid, "pending")
        )
    except Exception as e:
        logging.error(f"Не удалось уведомить исполнителя {assigned_tg_id}: {e}")

# =========================
#  ИНЛАЙН: APPROVE / REJECT
# =========================
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
