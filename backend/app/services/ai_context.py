"""Controlled learning context for the AI copilot.

The existing AI stack already supports ``ONLINE`` / ``OFFLINE`` / ``AUTO`` and a
built-in fallback, so nothing about provider selection changes here. This module
only builds the *learning context* object and decides what is allowed into it.

Rules enforced here:
  * only the SIGNED-IN learner's own rows are read (no client-supplied user id),
  * only learning signals are included - never name, email, class, teacher or
    any other PII,
  * the whole context can be inspected by the learner through
    ``GET /api/v1/ai/context`` so nothing is sent silently,
  * the learner can turn learner-state sharing off per request
    (``share_learning_state: false``).
"""
from __future__ import annotations

MAX_WEAK_CONCEPTS = 3
MAX_MISSES = 3


def build_learning_context(payload: dict, session_user_id=None):
    """Return an :class:`app.services.ai_tutor.AIContext` for this turn."""
    from app.services.ai_tutor import AIContext

    payload = payload if isinstance(payload, dict) else {}
    context = AIContext(
        subject=str(payload.get("subject", ""))[:120],
        chapter=str(payload.get("chapter", ""))[:160],
        topic=str(payload.get("topic", ""))[:160],
        lesson_id=str(payload.get("lesson_id", ""))[:180],
        question=str(payload.get("current_question", ""))[:1000],
        mode=str(payload.get("mode", "Explain"))[:30],
    )
    if not session_user_id:
        return context
    if str(payload.get("share_learning_state", "true")).lower() in ("0", "false", "no"):
        return context

    context.learner_summary = learner_state_summary(int(session_user_id), context)
    return context


def learner_state_summary(user_id: int, context=None) -> str:
    """A short, privacy-safe summary of this learner's own learning state."""
    parts: list[str] = []
    for label, value in _facts(user_id).items():
        if value:
            parts.append(f"{label}: {value}")
    if context and context.lesson_id:
        parts.insert(0, f"Current lesson: {context.lesson_id}")
    if context and context.question:
        parts.append(f"Question on screen: {context.question[:160]}")
    return " | ".join(parts)


def _facts(user_id: int) -> dict:
    from app.database.connection import get_connection

    connection = get_connection()
    try:
        weak = connection.execute(
            "SELECT concept_key, mastery FROM concept_mastery WHERE user_id = ? "
            "ORDER BY mastery ASC LIMIT ?", (int(user_id), MAX_WEAK_CONCEPTS)).fetchall()
        misses = connection.execute(
            "SELECT concept_key, COUNT(*) AS misses FROM question_attempts "
            "WHERE user_id = ? AND correct = 0 GROUP BY concept_key "
            "ORDER BY misses DESC LIMIT ?", (int(user_id), MAX_MISSES)).fetchall()
        session_row = connection.execute(
            "SELECT lesson_id, stage FROM learning_sessions WHERE user_id = ? "
            "AND state = 'active' ORDER BY id DESC LIMIT 1", (int(user_id),)).fetchone()
        mission = connection.execute(
            "SELECT title, kind FROM missions WHERE user_id = ? AND state IN "
            "('offered', 'active') ORDER BY id DESC LIMIT 1", (int(user_id),)).fetchone()
    except Exception:
        return {}
    finally:
        connection.close()

    facts: dict[str, str] = {}
    if weak:
        facts["weak concepts"] = ", ".join(
            f"{row['concept_key']} ({round(float(row['mastery'] or 0))}%)" for row in weak)
    if misses:
        facts["recently missed"] = ", ".join(
            f"{row['concept_key']} x{int(row['misses'])}" for row in misses)
    if session_row:
        facts["active session stage"] = f"{session_row['stage']} ({session_row['lesson_id']})"
    if mission:
        facts["current mission"] = f"{mission['title']} ({mission['kind']})"
    return facts


def context_preview(user_id: int, payload: dict) -> dict:
    """Exactly what would be sent, so the learner can see it (no secrets)."""
    context = build_learning_context(payload, session_user_id=user_id)
    return {
        "subject": context.subject,
        "chapter": context.chapter,
        "topic": context.topic,
        "lesson_id": context.lesson_id,
        "mode": context.mode,
        "shares_learner_state": bool(context.learner_summary),
        "learner_state": context.learner_summary,
        "excluded": ["name", "email", "class membership", "teacher data", "other learners"],
    }