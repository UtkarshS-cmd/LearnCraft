"""Remove test accounts (and their dependent rows) from a LearnCraft database.

Test helper scripts register throwaway accounts; this tool removes them again
so the shipped ``data/learncraft.db`` stays clean.

Usage::

    python scripts/cleanup_test_users.py            # default test accounts
    python scripts/cleanup_test_users.py a@x.com b@x.com
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "data" / "learncraft.db"

DEFAULT_EMAILS = [
    "smoke.student@example.com",
    "func.student@example.com",
    "func.teacher@example.com",
    "live-test@example.com",
    "audit.student@example.com",
]

# Columns in any table that may directly reference users.id.
OWNER_COLUMNS = ("user_id", "student_id", "teacher_id", "owner_id", "member_id")


def user_columns(connection: sqlite3.Connection, table: str) -> list[str]:
    rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
    return [row[1] for row in rows]


def cleanup(db_path: Path, emails: list[str]) -> None:
    connection = sqlite3.connect(db_path, timeout=30.0)
    connection.execute("PRAGMA foreign_keys=ON")
    ids = [
        row[0] for row in connection.execute(
            f"SELECT id FROM users WHERE email IN ({','.join('?' * len(emails))})",
            emails,
        ).fetchall()
    ]
    if not ids:
        print("No matching test users found; database already clean.")
        connection.close()
        return
    placeholders = ",".join("?" * len(ids))

    # Messages hang off conversations, not users directly.
    conversations = [
        row[0] for row in connection.execute(
            f"SELECT conversation_id FROM ai_conversations WHERE user_id IN ({placeholders})", ids
        ).fetchall()
    ]
    if conversations:
        marks = ",".join("?" * len(conversations))
        connection.execute(f"DELETE FROM ai_messages WHERE conversation_id IN ({marks})", conversations)
        connection.execute(f"DELETE FROM ai_conversations WHERE conversation_id IN ({marks})", conversations)

    # Every remaining table that carries a user/owner column.
    tables = [
        row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    ]
    for table in tables:
        for column in user_columns(connection, table):
            if column in OWNER_COLUMNS:
                connection.execute(
                    f"DELETE FROM {table} WHERE {column} IN ({placeholders})", ids
                )

    connection.execute(f"DELETE FROM users WHERE id IN ({placeholders})", ids)
    connection.commit()

    remaining = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    print(f"Removed {len(ids)} test user(s) from {db_path}. Users remaining: {remaining}")
    connection.close()


def main() -> int:
    emails = sys.argv[1:] or DEFAULT_EMAILS
    cleanup(DEFAULT_DB, emails)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())