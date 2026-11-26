import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from app.config import DATA_DIR

DB_PATH = DATA_DIR / "jobs.db"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                url TEXT NOT NULL UNIQUE,
                source_type TEXT NOT NULL DEFAULT 'wp_json',
                enabled INTEGER NOT NULL DEFAULT 1,
                last_fetched_at TEXT
            );

            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_name TEXT NOT NULL,
                source_url TEXT NOT NULL UNIQUE,
                title_en TEXT NOT NULL,
                company TEXT NOT NULL DEFAULT '',
                category TEXT NOT NULL DEFAULT 'General',
                closing_date TEXT NOT NULL DEFAULT '',
                salary TEXT NOT NULL DEFAULT '',
                location TEXT NOT NULL DEFAULT 'Sri Lanka',
                raw_excerpt TEXT NOT NULL DEFAULT '',
                sinhala_post TEXT NOT NULL DEFAULT '',
                card_headline_si TEXT NOT NULL DEFAULT '',
                card_subline_si TEXT NOT NULL DEFAULT '',
                card_image_path TEXT NOT NULL DEFAULT '',
                video_path TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending',
                fb_post_id TEXT NOT NULL DEFAULT '',
                error_message TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                published_at TEXT NOT NULL DEFAULT ''
            );
            """
        )

        # Safe migration for existing databases missing newer columns
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(jobs)").fetchall()]
        if "salary" not in cols:
            conn.execute("ALTER TABLE jobs ADD COLUMN salary TEXT NOT NULL DEFAULT ''")
        if "video_path" not in cols:
            conn.execute("ALTER TABLE jobs ADD COLUMN video_path TEXT NOT NULL DEFAULT ''")

        # Seed default sources requested by the user
        default_sources = [
            ("Gazette.lk", "https://www.gazette.lk", "wp_json", 1),
            ("HelloJobs.lk", "https://hellojobs.lk", "wp_json", 1),
        ]
        for name, url, stype, enabled in default_sources:
            conn.execute(
                """
                INSERT OR IGNORE INTO sources (name, url, source_type, enabled)
                VALUES (?, ?, ?, ?)
                """,
                (name, url, stype, enabled),
            )
