from contextlib import asynccontextmanager
import aiosqlite
from pathlib import Path

DB_PATH = Path("data/db.sqlite3")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id INTEGER UNIQUE NOT NULL,
    name TEXT,
    total_xp INTEGER NOT NULL DEFAULT 0,
    level INTEGER NOT NULL DEFAULT 1,
    current_streak INTEGER NOT NULL DEFAULT 0,
    longest_streak INTEGER NOT NULL DEFAULT 0,
    last_done_date TEXT
);

CREATE TABLE IF NOT EXISTS quests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    flavor_text TEXT,
    base_xp INTEGER NOT NULL DEFAULT 10,
    tag TEXT,
    deadline_at TEXT,
    state TEXT NOT NULL DEFAULT 'pending',
    created_by INTEGER,
    assigned_to INTEGER NOT NULL,
    FOREIGN KEY(assigned_to) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quest_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    text TEXT,
    submitted_at TEXT NOT NULL DEFAULT (datetime('now')),
    state TEXT NOT NULL DEFAULT 'submitted',
    -- новые поля под медиавложения:
    media_file_id TEXT,
    media_type TEXT,
    FOREIGN KEY(quest_id) REFERENCES quests(id) ON DELETE CASCADE,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS xp_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    delta INTEGER NOT NULL,
    type TEXT NOT NULL,
    meta TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
"""

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA_SQL)
        # на случай старой базы — догоним новые колонки
        async def ensure_col(table: str, col: str, ddl: str):
            cur = await db.execute(f"PRAGMA table_info({table})")
            cols = [r[1] for r in await cur.fetchall()]
            if col not in cols:
                await db.execute(ddl)

        await ensure_col("submissions", "media_file_id", "ALTER TABLE submissions ADD COLUMN media_file_id TEXT")
        await ensure_col("submissions", "media_type",    "ALTER TABLE submissions ADD COLUMN media_type TEXT")

        await db.commit()

@asynccontextmanager
async def get_db():
    db = await aiosqlite.connect(DB_PATH)
    try:
        yield db
    finally:
        await db.close()
