import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

import config


@contextmanager
def _connect():
    conn = sqlite3.connect(config.DB_PATH)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS posted_tenders (
                tender_no TEXT PRIMARY KEY,
                title TEXT,
                posted_at TEXT NOT NULL
            )
            """
        )


def is_seeded() -> bool:
    """True if the DB already has at least one record (i.e. not a first run)."""
    with _connect() as conn:
        row = conn.execute("SELECT 1 FROM posted_tenders LIMIT 1").fetchone()
        return row is not None


def is_posted(tender_no: str) -> bool:
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM posted_tenders WHERE tender_no = ?", (tender_no,)
        ).fetchone()
        return row is not None


def mark_posted(tender_no: str, title: str = ""):
    with _connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO posted_tenders (tender_no, title, posted_at) "
            "VALUES (?, ?, ?)",
            (tender_no, title, datetime.now(timezone.utc).isoformat()),
        )


def mark_many_posted(tenders):
    with _connect() as conn:
        conn.executemany(
            "INSERT OR IGNORE INTO posted_tenders (tender_no, title, posted_at) "
            "VALUES (?, ?, ?)",
            [
                (t["tender_no"], t.get("title", ""), datetime.now(timezone.utc).isoformat())
                for t in tenders
            ],
        )
