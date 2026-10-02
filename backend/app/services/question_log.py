"""Per-question attempt history.

``concept_mastery`` is an aggregate; this module keeps the per-question record
that the product layer needs as *evidence*:

  * mission engine  - "solve 3 practice questions" / mini challenge,
  * mastery map     - "recent attempts" drill-down,
  * early warning   - "repeated incorrect answers",
  * assignment intel - "common wrong answers".

Every query is scoped by ``user_id`` so one learner can never read another's
attempts.
"""
from __future__ import annotations

import json

from app.database.connection import _transaction, get_connection


def record_attempt(user_id: int, question_id: str, concept_key: str,
                   subject_slug: str = "", difficulty: str = "MEDIUM",
                   correct: bool = False, given: object = None) -> int | None:
    """Persist one graded attempt."""
    def work(connection):
        cursor = connection.execute(
            "INSERT INTO question_attempts (user_id, question_id, concept_key, "
            "subject_slug, difficulty, correct, given_answer) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (int(user_id), str(question_id)[:180], str(concept_key or "")[:200],
             str(subject_slug or "")[:120], str(difficulty or "MEDIUM")[:40],
             1 if correct else 0, json.dumps(given)[:200]),
        )
        return int(cursor.lastrowid)
    return _transaction(work)


def recent_for_concept(user_id: int, concept_key: str, limit: int = 10) -> list[dict]:
    connection = get_connection()
    rows = connection.execute(
        "SELECT question_id, correct, difficulty, created_at FROM question_attempts "
        "WHERE user_id = ? AND concept_key = ? ORDER BY id DESC LIMIT ?",
        (int(user_id), str(concept_key), max(1, min(int(limit), 50))),
    ).fetchall()
    connection.close()
    return [dict(row) for row in rows]


def stats_for_student(user_id: int, days: int = 14) -> dict:
    """Aggregate attempt evidence used by the early-warning engine."""
    connection = get_connection()
    row = connection.execute(
        "SELECT COUNT(*) AS attempts, COALESCE(SUM(correct), 0) AS correct "
        "FROM question_attempts WHERE user_id = ? "
        "AND created_at >= datetime('now', ?)",
        (int(user_id), f"-{int(days)} days"),
    ).fetchone()
    weakest = connection.execute(
        "SELECT concept_key, COUNT(*) AS attempts, COALESCE(SUM(correct), 0) AS correct "
        "FROM question_attempts WHERE user_id = ? "
        "AND created_at >= datetime('now', ?) "
        "GROUP BY concept_key ORDER BY (CAST(correct AS REAL) / attempts) ASC, attempts DESC "
        "LIMIT 5",
        (int(user_id), f"-{int(days)} days"),
    ).fetchall()
    recent = connection.execute(
        "SELECT concept_key, correct, created_at FROM question_attempts "
        "WHERE user_id = ? ORDER BY id DESC LIMIT 12",
        (int(user_id),),
    ).fetchall()
    connection.close()
    attempts = int(row["attempts"] or 0)
    correct = int(row["correct"] or 0)
    return {
        "attempts": attempts,
        "correct": correct,
        "incorrect": attempts - correct,
        "accuracy": round(100.0 * correct / attempts, 1) if attempts else None,
        "weak_concepts": [dict(item) for item in weakest],
        "recent": [dict(item) for item in recent],
    }
