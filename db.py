import aiosqlite
from typing import Optional, Dict, Any, List

DB_PATH = "data.sqlite3"

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS users(
  user_id INTEGER PRIMARY KEY,
  city TEXT NOT NULL DEFAULT 'Tashkent',
  remind_before INTEGER NOT NULL DEFAULT 10,
  remind_enabled INTEGER NOT NULL DEFAULT 1,
  last_imsak_date TEXT,
  last_maghrib_date TEXT
);
"""

class DB:
    def __init__(self, path: str = DB_PATH):
        self.path = path

    async def init(self) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(CREATE_SQL)
            await db.commit()

    async def ensure(self, user_id: int) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute("INSERT OR IGNORE INTO users(user_id) VALUES(?)", (user_id,))
            await db.commit()

    async def get(self, user_id: int) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
            row = await cur.fetchone()
            return dict(row) if row else None

    async def set_city(self, user_id: int, city: str) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute("UPDATE users SET city=? WHERE user_id=?", (city, user_id))
            await db.commit()

    async def set_remind_before(self, user_id: int, minutes: int) -> None:
        minutes = max(1, min(120, int(minutes)))
        async with aiosqlite.connect(self.path) as db:
            await db.execute("UPDATE users SET remind_before=? WHERE user_id=?", (minutes, user_id))
            await db.commit()

    async def mark_sent(self, user_id: int, kind: str, date_str: str) -> None:
        col = "last_imsak_date" if kind == "imsak" else "last_maghrib_date"
        async with aiosqlite.connect(self.path) as db:
            await db.execute(f"UPDATE users SET {col}=? WHERE user_id=?", (date_str, user_id))
            await db.commit()

    async def list_enabled(self) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM users WHERE remind_enabled=1")
            rows = await cur.fetchall()
            return [dict(r) for r in rows]
