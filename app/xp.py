import json
from datetime import datetime
from .levels import total_xp_for_level

async def add_xp(db, user_id: int, delta: int, reason: str = "system", meta: dict | None = None):
    # читаем текущие XP/уровень
    cur = await db.execute("SELECT total_xp, level FROM users WHERE id=?", (user_id,))
    row = await cur.fetchone()
    if not row:
        return
    total_xp, level = row
    total_xp = max(0, total_xp + int(delta))

    # апгрейд уровня по суммарному опыту
    # (уровень повышаем, пока хватает суммарного XP)
    while total_xp >= total_xp_for_level(level + 1):
        level += 1

    await db.execute("UPDATE users SET total_xp=?, level=? WHERE id=?", (total_xp, level, user_id))
    await db.execute(
        "INSERT INTO xp_events(user_id, delta, type, meta, created_at) VALUES(?,?,?,?,datetime('now'))",
        (user_id, int(delta), reason, json.dumps(meta or {}, ensure_ascii=False))
    )
