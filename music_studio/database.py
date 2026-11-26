import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from app.config import DATA_DIR

MUSIC_DB_PATH = DATA_DIR / "music_studio.db"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def get_music_conn():
    conn = sqlite3.connect(MUSIC_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_music_db():
    with get_music_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS stories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                artist TEXT NOT NULL,
                song_title TEXT NOT NULL,
                hook TEXT NOT NULL,
                scenes_json TEXT NOT NULL,
                caption TEXT NOT NULL,
                voice TEXT NOT NULL DEFAULT 'us_male',
                video_format TEXT NOT NULL DEFAULT 'reel',
                video_path TEXT NOT NULL DEFAULT '',
                thumbnail_path TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending',
                fb_post_id TEXT NOT NULL DEFAULT '',
                error_message TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                published_at TEXT NOT NULL DEFAULT ''
            );
            """
        )
