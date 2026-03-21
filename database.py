import sqlite3
import logging
from contextlib import contextmanager
from config import DB_PATH

logger = logging.getLogger(__name__)


def init_db():
    """Инициализация базы данных."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                min_price INTEGER,
                max_price INTEGER,
                keywords TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER DEFAULT 1
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS seen_ads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subscription_id INTEGER NOT NULL,
                ad_id TEXT NOT NULL,
                seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (subscription_id) REFERENCES subscriptions(id),
                UNIQUE(subscription_id, ad_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                notifications_enabled INTEGER DEFAULT 1
            )
        """)
        conn.commit()
    logger.info("База данных инициализирована.")


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


# ─── Пользователи ────────────────────────────────────────────────────────────

def upsert_user(user_id: int, username: str, first_name: str):
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO users (user_id, username, first_name)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name
        """, (user_id, username, first_name))
        conn.commit()


def get_user(user_id: int):
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()


def set_notifications(user_id: int, enabled: bool):
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET notifications_enabled = ? WHERE user_id = ?",
            (int(enabled), user_id)
        )
        conn.commit()


# ─── Подписки ─────────────────────────────────────────────────────────────────

def add_subscription(user_id: int, title: str, url: str,
                     min_price: int = None, max_price: int = None,
                     keywords: str = None) -> int:
    with get_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO subscriptions (user_id, title, url, min_price, max_price, keywords)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, title, url, min_price, max_price, keywords))
        conn.commit()
        return cursor.lastrowid


def get_subscriptions(user_id: int) -> list:
    with get_connection() as conn:
        return conn.execute("""
            SELECT * FROM subscriptions
            WHERE user_id = ? AND is_active = 1
            ORDER BY created_at DESC
        """, (user_id,)).fetchall()


def get_subscription(sub_id: int, user_id: int):
    with get_connection() as conn:
        return conn.execute("""
            SELECT * FROM subscriptions
            WHERE id = ? AND user_id = ? AND is_active = 1
        """, (sub_id, user_id)).fetchone()


def delete_subscription(sub_id: int, user_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.execute("""
            UPDATE subscriptions SET is_active = 0
            WHERE id = ? AND user_id = ?
        """, (sub_id, user_id))
        conn.commit()
        return cursor.rowcount > 0


def get_all_active_subscriptions() -> list:
    with get_connection() as conn:
        return conn.execute("""
            SELECT s.*, u.notifications_enabled
            FROM subscriptions s
            JOIN users u ON s.user_id = u.user_id
            WHERE s.is_active = 1 AND u.notifications_enabled = 1
        """).fetchall()


def count_user_subscriptions(user_id: int) -> int:
    with get_connection() as conn:
        row = conn.execute("""
            SELECT COUNT(*) as cnt FROM subscriptions
            WHERE user_id = ? AND is_active = 1
        """, (user_id,)).fetchone()
        return row["cnt"]


# ─── Просмотренные объявления ─────────────────────────────────────────────────

def is_ad_seen(subscription_id: int, ad_id: str) -> bool:
    with get_connection() as conn:
        row = conn.execute("""
            SELECT 1 FROM seen_ads
            WHERE subscription_id = ? AND ad_id = ?
        """, (subscription_id, ad_id)).fetchone()
        return row is not None


def mark_ad_seen(subscription_id: int, ad_id: str):
    with get_connection() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO seen_ads (subscription_id, ad_id)
            VALUES (?, ?)
        """, (subscription_id, ad_id))
        conn.commit()


def cleanup_old_seen_ads(days: int = 30):
    """Удаляем старые записи просмотренных объявлений."""
    with get_connection() as conn:
        conn.execute("""
            DELETE FROM seen_ads
            WHERE seen_at < datetime('now', ? || ' days')
        """, (f"-{days}",))
        conn.commit()
