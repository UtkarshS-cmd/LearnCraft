"""Learning Session Mode (focused study session).

Reuses the EXISTING lesson-stage model (``content_catalog.STAGE_CYCLE``:
CONCEPT -> EXPLAIN -> INTERACT -> EXPERIMENT -> PRACTICE -> REFLECT -> APPLY)
instead of inventing a second stage architecture, and persists progress so a
session survives a reload or a closed browser. The session summary is computed
from recorded learning events, never invented.
"""
from __future__ import annotations

import json

from app.database.connection import _transaction, get_connection


def stages() -> list[str]:
    """The canonical stage cycle the lesson player already uses."""
    from app.services.content_catalog import STAGE_CYCLE

    return list(STAGE_CYCLE)


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def start_session(user_id: int, lesson_id: str = "", mission_id: int | None = None,
                  goal: str = "", subject_slug: str = "") -> dict:
    """Start (or resume) a session for this learner.

    Resuming reuses the learner's existing ACTIVE session so a browser reload
    lands back exactly where the learner left off.
    """
    def work(connection):
        existing = connection.execute(
            "SELECT id FROM learning_sessions WHERE user_id = ? AND state = 'active' "
            "ORDER BY id DESC LIMIT 1", (int(user_id),)).fetchone()
        if existing:
            connection.execute(
                "UPDATE learning_sessions SET "
                "lesson_id = COALESCE(NULLIF(?, ''), lesson_id), "
                "mission_id = COALESCE(?, mission_id), "
                "goal = COALESCE(NULLIF(?, ''), goal), "
                "subject_slug = COALESCE(NULLIF(?, ''), subject_slug), "
                "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (lesson_id, mission_id, goal, subject_slug, int(existing["id"])))
            return int(existing["id"]), True
        cursor = connection.execute(
            "INSERT INTO learning_sessions (user_id, mission_id, lesson_id, subject_slug, goal, "
            "stage, stage_index, state) VALUES (?, ?, ?, ?, ?, 'CONCEPT', 0, 'active')",
            (int(user_id), mission_id, lesson_id, subject_slug,
             goal or "Work through this lesson"))
        return int(cursor.lastrowid), False

    session_id, _resumed = _transaction(work)
    return get_session(user_id, session_id) or {"id": session_id}


def get_session(user_id: int, session_id: int) -> dict | None:
    connection = get_connection()
    row = connection.execute(
        "SELECT * FROM learning_sessions WHERE id = ? AND user_id = ?",
        (int(session_id), int(user_id))).fetchone()
    connection.close()
    return _decorate(dict(row)) if row else None


def current_session(user_id: int) -> dict | None:
    connection = get_connection()
    row = connection.execute(
        "SELECT * FROM learning_sessions WHERE user_id = ? AND state = 'active' "
        "ORDER BY id DESC LIMIT 1", (int(user_id),)).fetchone()
    connection.close()
    return _decorate(dict(row)) if row else None


def _decorate(row: dict) -> dict:
    cycle = stages()
    index = int(row.get("stage_index") or 0)
    row["stages"] = cycle
    row["stage_total"] = len(cycle)
    row["stage_position"] = index + 1
    row["percent"] = int(round(100 * index / max(1, len(cycle))))
    try:
        row["summary"] = json.loads(row.get("summary_json") or "{}")
    except (TypeError, ValueError):
        row["summary"] = {}
    row.pop("summary_json", None)
    row["resumable"] = row.get("state") == "active"
    return row


def advance_stage(user_id: int, session_id: int, stage: str | None = None) -> dict | None:
    """Move to the next stage in the canonical cycle (or an explicit stage)."""
    cycle = stages()

    def work(connection):
        row = connection.execute(
            "SELECT * FROM learning_sessions WHERE id = ? AND user_id = ? AND state = 'active'",
            (int(session_id), int(user_id))).fetchone()
        if not row:
            return False
        index = int(row["stage_index"] or 0)
        if stage:
            wanted = str(stage).upper()
            index = cycle.index(wanted) if wanted in cycle else index
        else:
            index = min(index + 1, len(cycle) - 1)
        connection.execute(
            "UPDATE learning_sessions SET stage = ?, stage_index = ?, "
            "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (cycle[index], index, int(session_id)))
        return True

    if not _transaction(work):
        return None
    return get_session(user_id, session_id)


def finish_session(user_id: int, session_id: int) -> dict | None:
    """Complete the session and attach an evidence-based summary."""
    summary = _session_evidence(user_id, session_id)

    def work(connection):
        cursor = connection.execute(
            "UPDATE learning_sessions SET state = 'completed', summary_json = ?, "
            "completed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP "
            "WHERE id = ? AND user_id = ?",
            (json.dumps(summary), int(session_id), int(user_id)))
        return cursor.rowcount > 0

    if not _transaction(work):
        return None
    try:
        from app.services.gamification import award

        award(int(user_id), "session_completed", f"session:{session_id}")
    except Exception:
        pass
    return get_session(user_id, session_id)


def abandon_session(user_id: int, session_id: int) -> bool:
    def work(connection):
        cursor = connection.execute(
            "UPDATE learning_sessions SET state = 'abandoned', updated_at = CURRENT_TIMESTAMP "
            "WHERE id = ? AND user_id = ? AND state = 'active'",
            (int(session_id), int(user_id)))
        return cursor.rowcount > 0
    return bool(_transaction(work))


def _session_evidence(user_id: int, session_id: int) -> dict:
    """Summary built from what actually happened during the session."""
    connection = get_connection()
    try:
        row = connection.execute(
            "SELECT started_at FROM learning_sessions WHERE id = ? AND user_id = ?",
            (int(session_id), int(user_id))).fetchone()
        if not row:
            return {}
        started = row["started_at"]
        attempts = connection.execute(
            "SELECT COUNT(*) AS total, COALESCE(SUM(correct), 0) AS correct "
            "FROM question_attempts WHERE user_id = ? AND created_at >= ?",
            (int(user_id), started)).fetchone()
        lessons = connection.execute(
            "SELECT COUNT(*) AS total FROM learning_progress WHERE user_id = ? "
            "AND updated_at >= ? AND status = 'completed'",
            (int(user_id), started)).fetchone()
        notes = connection.execute(
            "SELECT COUNT(*) AS total FROM notes WHERE user_id = ? AND updated_at >= ? "
            "AND deleted_at IS NULL", (int(user_id), started)).fetchone()
    finally:
        connection.close()
    total = int(attempts["total"] or 0)
    correct = int(attempts["correct"] or 0)
    return {
        "questions_answered": total,
        "questions_correct": correct,
        "accuracy": round(100.0 * correct / total, 1) if total else None,
        "lessons_completed": int(lessons["total"] or 0),
        "notes_written": int(notes["total"] or 0),
        "source": "question_attempts, learning_progress and notes since session start",
    }