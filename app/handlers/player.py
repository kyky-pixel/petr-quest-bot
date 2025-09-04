import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

from ..db import get_db
from ..levels import progress_at
from ..keyboards import main_menu_kb, quest_actions_kb, admin_review_kb
from ..config import settings

player_router = Router()

class SubmitQuest(StatesGroup):
    waiting_note = State()

@player_router.message(Command("start"))
async def start_cmd(m: Message):
    async with get_db() as db:
        cur = await db.execute("SELECT id FROM users WHERE tg_id=?", (m.from_user.id,))
        row = await cur.fetchone()
        if not row:
            await db.execute(
                "INSERT INTO users(tg_id, name) VALUES(?,?)",
                (m.from_user.id, f"@{m.from_user.username}" if m.from_user.username else m.from_user.full_name)
            )
            await db.commit()
    await m.reply("Привет! Я квест-бот. Жми кнопки ниже 👇", reply_markup=main_menu_kb())

@player_router.message(F.text.in_(["📊 Профиль", "Профиль"]))
@player_router.message(Command("profile"))
async def profile_cmd(m: Message):
    async with get_db() as db:
        cur = await db.execute(
            "SELECT id, level, total_xp, current_streak, longest_streak FROM users WHERE tg_id=?",
            (m.from_user.id,)
        )
        row = await cur.fetchone()
        if not row:
            return await m.reply("Сначала сделай /start", reply_markup=main_menu_kb())
        uid, level, total_xp, cs, ls = row

    base, need, have, pct = progress_at(total_xp, level)
    filled = int(round(pct / 10))
    bar = "█" * filled + "░" * (10 - filled)
    to_next = max(0, need - have)

    msg = (
        "Профиль\n"
        f"Уровень: {level}\n"
        f"Опыт: {total_xp} (до след. уровня: {to_next})\n"
        f"Прогресс: [{bar}] {pct:.0f}%\n"
        f"Серия: {cs} (рекорд {ls})"
    )
    await m.reply(msg, reply_markup=main_menu_kb())

@player_router.message(F.text.in_(["🗺 Квесты", "Квесты"]))
@player_router.message(Command("quests"))
async def quests_cmd(m: Message):
    async with get_db() as db:
        cur_uid = await db.execute("SELECT id FROM users WHERE tg_id=?", (m.from_user.id,))
        uid_row = await cur_uid.fetchone()
        if not uid_row:
            return await m.reply("Сначала /start", reply_markup=main_menu_kb())
        uid = uid_row[0]
        cur = await db.execute(
            "SELECT id, title, base_xp, state FROM quests "
            "WHERE assigned_to=? AND state IN ('pending','accepted','submitted','rejected') "
            "ORDER BY id DESC",
            (uid,)
        )
        rows = await cur.fetchall()
    if not rows:
        return await m.reply("Пока нет активных квестов", reply_markup=main_menu_kb())

    for (qid, title, xp, state) in rows:
        text = f"#{qid} — {title}\nXP: +{xp}\nСтатус: {state}"
        await m.answer(text, reply_markup=quest_actions_kb(qid, state))

@player_router.message(Command("done"))
async def done_cmd(m: Message):
    parts = m.text.split(maxsplit=2)
    if len(parts) < 2:
        return await m.reply("Формат: /done <id> краткий_отчёт")
    qid = int(parts[1])
    note = parts[2] if len(parts) > 2 else ""
    await _submit_quest(m.from_user.id, qid, note, m, None, None)

@player_router.callback_query(F.data.startswith("q:accept:"))
async def cb_accept(c: CallbackQuery):
    qid = int(c.data.split(":")[2])
    async with get_db() as db:
        cur = await db.execute("SELECT assigned_to, state FROM quests WHERE id=?", (qid,))
        row = await cur.fetchone()
        if not row:
            return await c.answer("Квест не найден", show_alert=True)
        assigned_to, state = row
        cur = await db.execute("SELECT id FROM users WHERE tg_id=?", (c.from_user.id,))
        uid_row = await cur.fetchone()
        if not uid_row or uid_row[0] != assigned_to:
            return await c.answer("Квест не ваш", show_alert=True)
        if state not in ("pending",):
            return await c.answer("Нельзя принять в текущем состоянии", show_alert=True)
        await db.execute("UPDATE quests SET state='accepted' WHERE id=?", (qid,))
        await db.commit()
    await c.answer("Квест принят ✅")
    await c.message.edit_reply_markup(reply_markup=quest_actions_kb(qid, "accepted"))

@player_router.callback_query(F.data.startswith("q:decline:"))
async def cb_decline(c: CallbackQuery):
    qid = int(c.data.split(":")[2])
    async with get_db() as db:
        cur = await db.execute("SELECT assigned_to, state FROM quests WHERE id=?", (qid,))
        row = await cur.fetchone()
        if not row:
            return await c.answer("Квест не найден", show_alert=True)
        assigned_to, state = row
        cur = await db.execute("SELECT id FROM users WHERE tg_id=?", (c.from_user.id,))
        uid_row = await cur.fetchone()
        if not uid_row or uid_row[0] != assigned_to:
            return await c.answer("Квест не ваш", show_alert=True)
        if state not in ("pending","accepted"):
            return await c.answer("Нельзя отказаться сейчас", show_alert=True)
        await db.execute("UPDATE quests SET state='declined' WHERE id=?", (qid,))
        await db.commit()
    await c.answer("Квест отменён ❌")
    await c.message.edit_reply_markup(reply_markup=None)

@player_router.callback_query(F.data.startswith("q:submit:"))
async def cb_submit(c: CallbackQuery, state: FSMContext):
    qid = int(c.data.split(":")[2])
    await state.set_state(SubmitQuest.waiting_note)
    await state.update_data(qid=qid)
    await c.answer()
    await c.message.reply(f"Напиши короткий отчёт по квесту #{qid} в следующем сообщении. Можно приложить фото/файл — приму как отчёт.")

# ---- Сбор отчёта: фото / файл / текст ----
@player_router.message(SubmitQuest.waiting_note, F.photo)
async def collect_photo(m: Message, state: FSMContext):
    data = await state.get_data()
    qid = data.get("qid")
    file_id = m.photo[-1].file_id
    note = m.caption or ""
    await _submit_quest(m.from_user.id, qid, note, m, file_id, "photo")
    await state.clear()

@player_router.message(SubmitQuest.waiting_note, F.document)
async def collect_doc(m: Message, state: FSMContext):
    data = await state.get_data()
    qid = data.get("qid")
    file_id = m.document.file_id
    note = m.caption or ""
    await _submit_quest(m.from_user.id, qid, note, m, file_id, "document")
    await state.clear()

@player_router.message(SubmitQuest.waiting_note)
async def collect_text(m: Message, state: FSMContext):
    data = await state.get_data()
    qid = data.get("qid")
    note = m.text or ""
    await _submit_quest(m.from_user.id, qid, note, m, None, None)
    await state.clear()

async def _submit_quest(tg_user_id: int, qid: int, note: str, m: Message, media_file_id: str | None, media_type: str | None):
    async with get_db() as db:
        cur = await db.execute("SELECT id, name FROM users WHERE tg_id=?", (tg_user_id,))
        uid_row = await cur.fetchone()
        if not uid_row:
            return await m.reply("Сначала /start", reply_markup=main_menu_kb())
        uid, uname = uid_row

        cur = await db.execute("SELECT id, state, assigned_to FROM quests WHERE id=?", (qid,))
        row = await cur.fetchone()
        if not row:
            return await m.reply("Квест не найден")
        _, state, assigned_to = row
        if assigned_to != uid:
            return await m.reply("Этот квест не назначен вам")
        # РАЗРЕШАЕМ из rejected тоже
        if state not in ("pending", "accepted", "rejected"):
            return await m.reply("Квест нельзя сдать в текущем состоянии")

        await db.execute("UPDATE quests SET state='submitted' WHERE id=?", (qid,))
        await db.execute(
            "INSERT INTO submissions(quest_id, user_id, text, media_file_id, media_type) VALUES(?,?,?,?,?)",
            (qid, uid, note, media_file_id, media_type)
        )
        await db.commit()

    # Нотификация админам со встроенными кнопками + медиа, если есть
    for admin_id in settings.admin_ids:
        try:
            if media_file_id and media_type == "photo":
                await m.bot.send_photo(
                    admin_id, media_file_id,
                    caption=f"📝 Сдан квест #{qid} от {uname}.\nОтчёт: {note or '—'}",
                    reply_markup=admin_review_kb(qid)
                )
            elif media_file_id and media_type == "document":
                await m.bot.send_document(
                    admin_id, media_file_id,
                    caption=f"📝 Сдан квест #{qid} от {uname}.\nОтчёт: {note or '—'}",
                    reply_markup=admin_review_kb(qid)
                )
            else:
                await m.bot.send_message(
                    admin_id,
                    f"📝 Сдан квест #{qid} от {uname}.\nОтчёт: {note or '—'}",
                    reply_markup=admin_review_kb(qid)
                )
        except Exception as e:
            logging.error(f"Не удалось уведомить админа {admin_id}: {e}")

    await m.reply("Отправлено на проверку. Ждём подтверждения.", reply_markup=main_menu_kb())
from aiogram.filters import Command
from aiogram.types import Message
from ..db import get_db
from ..keyboards import quest_actions_kb

async def _send_my_quests(m: Message):
    async with get_db() as db:
        cur = await db.execute(
            """
            SELECT q.id, q.title, q.state, q.base_xp
            FROM quests q
            JOIN users u ON u.id = q.assigned_to
            WHERE u.tg_id = ? AND q.state IN ('pending','accepted','submitted','returned')
            ORDER BY q.id DESC
            """,
            (m.from_user.id,)
        )
        rows = await cur.fetchall()

    if not rows:
        return await m.reply("Пока нет активных/ожидающих квестов.")

    # отправляем карточки с правильными кнопками для текущего состояния
    for qid, title, state, xp in rows:
        await m.reply(
            f"#{qid} — {title}\nСтатус: {state}\nXP: +{xp}",
            reply_markup=quest_actions_kb(qid, state)
        )

@player_router.message(Command("inbox"))
async def inbox_cmd(m: Message):
    await _send_my_quests(m)

@player_router.message(Command("quests"))
async def quests_cmd_all(m: Message):
    await _send_my_quests(m)

# нажатие кнопки "Квесты" в меню
@player_router.message(F.text == "🗺️ Квесты")
@player_router.message(F.text == "Квесты")
async def quests_text_btn(m: Message):
    await _send_my_quests(m)
from aiogram.filters import Command
from aiogram.types import Message
from ..db import get_db
from ..keyboards import quest_actions_kb

async def _send_my_quests(m: Message):
    async with get_db() as db:
        cur = await db.execute(
            """
            SELECT q.id, q.title, q.state, q.base_xp
            FROM quests q
            JOIN users u ON u.id = q.assigned_to
            WHERE u.tg_id = ? AND q.state IN ('pending','accepted','submitted','returned')
            ORDER BY q.id DESC
            """,
            (m.from_user.id,)
        )
        rows = await cur.fetchall()

    if not rows:
        return await m.reply("Пока нет активных/ожидающих квестов.")

    # отправляем карточки с правильными кнопками для текущего состояния
    for qid, title, state, xp in rows:
        await m.reply(
            f"#{qid} — {title}\nСтатус: {state}\nXP: +{xp}",
            reply_markup=quest_actions_kb(qid, state)
        )

@player_router.message(Command("inbox"))
async def inbox_cmd(m: Message):
    await _send_my_quests(m)

@player_router.message(Command("quests"))
async def quests_cmd_all(m: Message):
    await _send_my_quests(m)

# нажатие кнопки "Квесты" в меню
@player_router.message(F.text == "🗺️ Квесты")
@player_router.message(F.text == "Квесты")
async def quests_text_btn(m: Message):
    await _send_my_quests(m)
from aiogram import F
from aiogram.types import CallbackQuery
from ..config import settings
from ..db import get_db

# Игрок нажал "Сдать" (callback "q:submit:<id>")
@player_router.callback_query(F.data.startswith("q:submit:"))
async def q_submit(c: CallbackQuery):
    qid = int(c.data.split(":")[2])
    async with get_db() as db:
        # запишем сдачу (если не записана) и переключим состояние
        await db.execute(
            "INSERT INTO submissions(quest_id, user_id, state) "
            "SELECT q.id, q.assigned_to, 'pending' FROM quests q WHERE q.id=? "
            "ON CONFLICT(quest_id) DO NOTHING",
            (qid,)
        )
        await db.execute("UPDATE quests SET state='submitted' WHERE id=?", (qid,))
        # Получим инфо для уведомления
        cur = await db.execute(
            "SELECT q.id, u.name, q.title, q.base_xp FROM quests q "
            "JOIN users u ON u.id=q.assigned_to WHERE q.id=?",
            (qid,)
        )
        row = await cur.fetchone()
        await db.commit()

    await c.answer("Отправлено на проверку ✅", show_alert=False)
    try:
        await c.message.edit_text(c.message.text + "\n\n📬 Отправлено на проверку")
    except Exception:
        pass

    # нотификация всем админам
    if row:
        qid, uname, title, xp = row
        for aid in settings.admin_ids:
            try:
                await c.message.bot.send_message(
                    aid,
                    f"🧾 Сдан квест #{qid} — {title} (от {uname}) +{xp} XP",
                    reply_markup=admin_review_kb(qid)
                )
            except Exception as e:
                logging.error(f"Не смог отправить админу {aid} уведомление о сдаче: {e}")
# --- notify admins on submit & show "submitted" to player ---
from aiogram import F
from aiogram.types import CallbackQuery
from ..config import settings
from ..keyboards import admin_review_kb

@player_router.callback_query(F.data.startswith("q:submit:"))
async def q_submit(c: CallbackQuery):
    qid = int(c.data.split(":")[2])
    async with get_db() as db:
        # фиксируем сдачу и переводим в submitted
        await db.execute(
            "INSERT INTO submissions(quest_id, user_id, state) "
            "SELECT q.id, q.assigned_to, 'pending' FROM quests q WHERE q.id=? "
            "ON CONFLICT(quest_id) DO NOTHING",
            (qid,)
        )
        await db.execute("UPDATE quests SET state='submitted' WHERE id=?", (qid,))
        # достанем данные для уведомления
        cur = await db.execute(
            "SELECT q.id, u.name, q.title, q.base_xp "
            "FROM quests q JOIN users u ON u.id=q.assigned_to "
            "WHERE q.id=?",
            (qid,)
        )
        row = await cur.fetchone()
        await db.commit()

    await c.answer("Отправлено на проверку ✅")
    try:
        await c.message.edit_text(c.message.text + "\n\n📬 Отправлено на проверку")
    except Exception:
        pass

    if row:
        qid, uname, title, xp = row
        for aid in settings.admin_ids:
            try:
                await c.bot.send_message(
                    aid,
                    f"🧾 Сдан квест #{qid} — {title} (от {uname}) +{xp} XP",
                    reply_markup=admin_review_kb(qid)
                )
            except Exception as e:
                logging.error(f"Не смог уведомить админа {aid}: {e}")
# --- notify admins on submit & show "submitted" to player ---
from aiogram import F
from aiogram.types import CallbackQuery
from ..config import settings
from ..keyboards import admin_review_kb

@player_router.callback_query(F.data.startswith("q:submit:"))
async def q_submit(c: CallbackQuery):
    qid = int(c.data.split(":")[2])
    async with get_db() as db:
        # фиксируем сдачу и переводим в submitted
        await db.execute(
            "INSERT INTO submissions(quest_id, user_id, state) "
            "SELECT q.id, q.assigned_to, 'pending' FROM quests q WHERE q.id=? "
            "ON CONFLICT(quest_id) DO NOTHING",
            (qid,)
        )
        await db.execute("UPDATE quests SET state='submitted' WHERE id=?", (qid,))
        # достанем данные для уведомления
        cur = await db.execute(
            "SELECT q.id, u.name, q.title, q.base_xp "
            "FROM quests q JOIN users u ON u.id=q.assigned_to "
            "WHERE q.id=?",
            (qid,)
        )
        row = await cur.fetchone()
        await db.commit()

    await c.answer("Отправлено на проверку ✅")
    try:
        await c.message.edit_text(c.message.text + "\n\n📬 Отправлено на проверку")
    except Exception:
        pass

    if row:
        qid, uname, title, xp = row
        for aid in settings.admin_ids:
            try:
                await c.bot.send_message(
                    aid,
                    f"🧾 Сдан квест #{qid} — {title} (от {uname}) +{xp} XP",
                    reply_markup=admin_review_kb(qid)
                )
            except Exception as e:
                logging.error(f"Не смог уведомить админа {aid}: {e}")
# --- status labels + последний статус сабмита ---
def _status_label(q_state: str, s_state: str|None) -> str:
    # если последний сабмит rejected — показываем "на доработке"
    if s_state == "rejected":
        return "на доработке"
    return {
        "pending":   "ожидает принятия",
        "accepted":  "в работе",
        "submitted": "на проверке",
        "returned":  "на доработке",
        "approved":  "принят",
    }.get(q_state, q_state)

async def _send_my_quests(m: Message):
    async with get_db() as db:
        # берём последний сабмит (если есть) и его state
        cur = await db.execute(
            """
            SELECT q.id, q.title, q.state, q.base_xp,
                   (SELECT s.state FROM submissions s
                    WHERE s.quest_id = q.id
                    ORDER BY s.id DESC LIMIT 1) AS last_sub_state
            FROM quests q
            JOIN users u ON u.id = q.assigned_to
            WHERE u.tg_id = ? AND q.state IN ('pending','accepted','submitted','returned')
            ORDER BY q.id DESC
            """,
            (m.from_user.id,)
        )
        rows = await cur.fetchall()

    if not rows:
        return await m.reply("Пока нет активных/ожидающих квестов.")

    for qid, title, q_state, xp, sub_state in rows:
        label = _status_label(q_state, sub_state)
        await m.reply(
            f"#{qid} — {title}\nСтатус: {label}\nXP: +{xp}",
            reply_markup=quest_actions_kb(qid, q_state if q_state != "approved" else "approved")
        )

