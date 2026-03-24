import sqlite3
import json
import shutil
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "sendmail.db"


def get_db():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS upload_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            uploaded_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            row_count INTEGER NOT NULL,
            data TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS send_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            row_index INTEGER NOT NULL,
            send_type TEXT NOT NULL,
            to_email TEXT NOT NULL,
            cc_email TEXT,
            subject TEXT,
            status TEXT NOT NULL,
            error TEXT,
            sent_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (session_id) REFERENCES upload_sessions(id)
        )
    """)
    conn.commit()
    conn.close()


ATTACHMENTS_BASE_DIR = Path(__file__).parent.parent / "attachments"


def delete_session(conn, session_id: int) -> None:
    """Delete a session and its send logs. Does NOT close the connection."""
    conn.execute("DELETE FROM send_logs WHERE session_id = ?", (session_id,))
    conn.execute("DELETE FROM upload_sessions WHERE id = ?", (session_id,))
    session_dir = ATTACHMENTS_BASE_DIR / str(session_id)
    if session_dir.exists():
        shutil.rmtree(session_dir)


def cleanup_old_sessions(days: int = 7) -> list[int]:
    """Delete sessions older than `days` days. Returns list of deleted session IDs."""
    conn = get_db()
    rows = conn.execute(
        "SELECT id FROM upload_sessions WHERE uploaded_at < datetime('now', 'localtime', ?)",
        (f"-{days} days",),
    ).fetchall()
    deleted = [r["id"] for r in rows]
    for sid in deleted:
        delete_session(conn, sid)
    conn.commit()
    conn.close()
    return deleted
