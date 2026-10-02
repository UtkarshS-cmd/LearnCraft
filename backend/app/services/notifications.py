"""Centralized, persistent notification centre.

The existing bell in ``base.html`` kept "seen" state in ``localStorage`` only,
which meant unread state was per-browser, per-device and lost on clear. This
service persists notifications in SQLite so they follow the account, are
scoped per user (never another learner's), and can be read/unread from any UI.

Notifications are created by real domain events:
  * ``assignment_assigned``  - teacher creates an assignment for a class
  * ``announcement``         - teacher posts an announcement
  * ``join_approved``        - teacher approves a student into a class
  * ``mission_completed``    - a mission finishes (verified by the engine)
  * ``assignment_submitted`` - a student submits teacher-assigned work
  * ``level_up``             - gamification level increased
  * ``early_warning``        - teacher-side signal needs attention

De-duplication uses ``dedupe_key`` so a polled event cannot spam the list.
"""
from __future__ import annotations

from app.database.connection import _transaction, get_connection

KIND_ASSIGNMENT = "assignment_assigned"
KIND_ANNOUNCEMENT = "announcement"
KIND_JOIN = "join_approved"
KIND_MISSION = "mission_completed"
KIND_SUBMISSION = "assignment_submitted"
KIND_LEVEL = "level_up"
KIND_EARLY_WARNING = "early_warning"


def _row(row) -> dict:
    return {
        "id": int(row["id"]),
        "kind": row["kind"],
        "title": row["title"],
        "body": row["body"],
        "href": row["href"],
        "read": bool(row["read_at"]),
        "read_at": row["read_at"],
        "created_at": row["created_at"],
    }


def notify(user_id: int, kind: str, title: str, body: str = "", href: str = "",
           dedupe_key: str | None = None) -> int | None:
    """Create a notification (idempotent when ``dedupe_key`` is given)."""
    def work(connection):
        if dedupe_key:
            existing = connection.execute(
                "SELECT id FROM notifications WHERE user_id = ? AND dedupe_key = ?",
                (int(user_id), dedupe_key),
            ).fetchone()
            if existing:
                return None
            cursor = connection.execute(
                "INSERT INTO notifications (user_id, kind, title, body, href, dedupe_key) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (int(user_id), kind, str(title)[:200], str(body)[:400],
                 str(href)[:300], dedupe_key[:160]),
            )
        else:
            cursor = connection.execute(
                "INSERT INTO notifications (user_id, kind, title, body, href) "
                "VALUES (?, ?, ?, ?, ?)",
                (int(user_id), kind, str(title)[:200], str(body)[:400], str(href)[:300]),
            )
        return int(cursor.lastrowid)
    return _transaction(work)


def list_notifications(user_id: int, limit: int = 30, unread_only: bool = False) -> list[dict]:
    connection = get_connection()
    sql = "SELECT * FROM notifications WHERE user_id = ?"
    if unread_only:
        sql += " AND read_at IS NULL"
    sql += " ORDER BY id DESC LIMIT ?"
    rows = connection.execute(sql, (int(user_id), max(1, min(int(limit or 30), 100)))).fetchall()
    connection.close()
    return [_row(row) for row in rows]


def unread_count(user_id: int) -> int:
    connection = get_connection()
    row = connection.execute(
        "SELECT COUNT(*) AS total FROM notifications WHERE user_id = ? AND read_at IS NULL",
        (int(user_id),),
    ).fetchone()
    connection.close()
    return int(row["total"] if row else 0)


def mark_read(user_id: int, notification_id: int | None = None) -> int:
    """Mark one notification read, or all of them when id is omitted."""
    def work(connection):
        if notification_id is None:
            cursor = connection.execute(
                "UPDATE notifications SET read_at = CURRENT_TIMESTAMP "
                "WHERE user_id = ? AND read_at IS NULL", (int(user_id),))
        else:
            cursor = connection.execute(
                "UPDATE notifications SET read_at = CURRENT_TIMESTAMP "
                "WHERE id = ? AND user_id = ? AND read_at IS NULL",
                (int(notification_id), int(user_id)))
        return cursor.rowcount
    return int(_transaction(work))
