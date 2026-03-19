import aiosqlite
from datetime import datetime

DB_FILE = "seen_ads.db"


async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS seen (
                ad_id TEXT PRIMARY KEY,
                title TEXT,
                price TEXT,
                url TEXT,
                first_seen TEXT
            )
        """)
        await db.commit()


async def is_seen(ad_id: str) -> bool:
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute("SELECT 1 FROM seen WHERE ad_id = ?", (ad_id,))
        return await cursor.fetchone() is not None


async def mark_seen(ad_id: str, title: str, price: str, url: str):
    async with aiosqlite.connect(DB_FILE) as db:
        now = datetime.utcnow().isoformat()
        await db.execute(
            "INSERT OR IGNORE INTO seen (ad_id, title, price, url, first_seen) VALUES (?, ?, ?, ?, ?)",
            (ad_id, title, price, url, now)
        )
        await db.commit()