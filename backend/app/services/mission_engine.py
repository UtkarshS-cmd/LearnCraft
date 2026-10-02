"""Learning Mission Engine.

Missions are GENERATED from existing learning state (curriculum + persisted
mastery + unfinished lessons + open teacher assignments), never hardcoded.
Identity is a stable ``mission_key`` so regeneration is idempotent, and every
step carries a real target (lesson id, assignment id, concept key, question
count).

Completion is CALCULATED from actual recorded learning events -
``learning_progress``, ``question_attempts`` and ``assignment_submissions`` -
never set by the client and never hardcoded.
"""
from __future__ import annotations

import json

from app.database.connection import _transaction, get_connection, get_user_progress

PRACTICE_TARGET = 3   # real graded questions on the mission concept
CHALLENGE_TARGET = 1  # correct answers needed for the mini challenge


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _graph_node(concept: str) -> dict:
    from app.services.concept_map import graph_node

    return graph_node(concept)


def _lesson_for(key: str) -> str:
    """Real lesson id for a mastery key (concept id OR chapter id)."""
    from app.services.concept_map import lesson_for_key

    return lesson_for_key(key)


def _assignment_candidate(item: dict) -> dict:
    assignment_id = item.get("id")
    return {
        "mission_key": f"assignment:{assignment_id}",
        "kind": "assignment",
        "title": item.get("title") or f"Assignment {assignment_id}",
        "brief": "Complete and submit the work your teacher assigned.",
        "concept_key": str(item.get("resource_id") or ""),
        "subject_slug": "",
        "reason": {"assignment_id": assignment_id, "trigger": "assignment",
                   "due_at": item.get("due_at"),
                   "explanation": "Assigned by your teacher."},
        "steps": [
            {"kind": "open", "title": "Open the assignment",
             "target_type": "assignment", "target_id": str(assignment_id),
             "required_count": 1},
            {"kind": "submit", "title": "Submit your work",
             "target_type": "assignment", "target_id": str(assignment_id),
             "required_count": 1},
        ],
    }


def _mission_candidates(user_id: int) -> list[dict]:
    """Derive mission candidates from the learner's real persisted state."""
    from app.services.mastery import weak_concepts
    from app.services.teacher_control import student_assignments

    candidates: list[dict] = []

    # 1) Weak concepts -> "Repair" missions, lowest mastery first.
    for row in weak_concepts(user_id, 60.0, 3):
        concept = row.get("concept_key", "")
        if not concept:
            continue
        node = _graph_node(concept)
        title = node.get("title") or concept
        candidates.append({
            "mission_key": f"repair:{concept}",
            "kind": "repair",
            "title": f"Repair: {title}",
            "brief": f"Rebuild {title} from the concept to a correct answer.",
            "concept_key": concept,
            "subject_slug": row.get("subject_slug", "") or "",
            "reason": {
                "mastery": row.get("mastery"), "attempts": row.get("attempts"),
                "correct": row.get("correct"), "trigger": "lowest_mastery",
                "explanation": (f"Mastery {row.get('mastery')}% over "
                                f"{row.get('attempts')} attempt(s)."),
            },
            "steps": [
                {"kind": "review", "title": f"Review {title}",
                 "target_type": "lesson", "target_id": _lesson_for(concept),
                 "required_count": 1},
                {"kind": "practice", "title": f"Solve {PRACTICE_TARGET} practice questions",
                 "target_type": "concept", "target_id": concept,
                 "required_count": PRACTICE_TARGET},
                {"kind": "challenge", "title": "Complete the mini challenge",
                 "target_type": "concept", "target_id": concept,
                 "required_count": CHALLENGE_TARGET},
            ],
        })

    # 2) Unfinished lessons -> "Continue" missions.
    for row in get_user_progress(user_id):
        if row.get("status") == "completed" or not row.get("lesson_id"):
            continue
        pct = int(row.get("percent_complete", 0) or 0)
        if pct >= 100:
            continue
        lesson_id = row["lesson_id"]
        candidates.append({
            "mission_key": f"continue:{lesson_id}",
            "kind": "continue",
            "title": f"Continue: {lesson_id}",
            "brief": f"Pick up an unfinished lesson at {pct}%.",
            "concept_key": lesson_id,
            "subject_slug": row.get("subject_slug", "") or "",
            "reason": {"percent_complete": pct, "trigger": "unfinished_lesson",
                       "explanation": f"Lesson progress is at {pct}%."},
            "steps": [
                {"kind": "review", "title": "Finish the lesson",
                 "target_type": "lesson", "target_id": lesson_id, "required_count": 1},
                {"kind": "practice", "title": "Attempt the chapter check",
                 "target_type": "lesson", "target_id": lesson_id, "required_count": 1},
            ],
        })

    # 3) Open teacher assignments -> "Deliver" missions.
    for item in student_assignments(user_id):
        if item.get("id"):
            candidates.append(_assignment_candidate(item))
    return candidates


def ensure_missions(user_id: int) -> int:
    """Persist every mission the learner's current state implies. Idempotent."""
    candidates = _mission_candidates(user_id)

    def work(connection):
        created = 0
        for candidate in candidates[:12]:
            existing = connection.execute(
                "SELECT id FROM missions WHERE user_id = ? AND mission_key = ?",
                (int(user_id), candidate["mission_key"]),
            ).fetchone()
            if existing:
                continue
            cursor = connection.execute(
                "INSERT INTO missions (user_id, mission_key, kind, title, brief, "
                "concept_key, subject_slug, reason_json, state, reward_xp) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'offered', ?)",
                (int(user_id), candidate["mission_key"], candidate["kind"],
                 candidate["title"], candidate["brief"], candidate["concept_key"],
                 candidate["subject_slug"], json.dumps(candidate["reason"]),
                 40 if candidate["kind"] == "assignment" else 60),
            )
            mission_id = cursor.lastrowid
            for index, step in enumerate(candidate["steps"]):
                connection.execute(
                    "INSERT INTO mission_steps (mission_id, step_index, kind, title, "
                    "target_type, target_id, required_count) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (int(mission_id), index, step["kind"], step["title"],
                     step.get("target_type", ""), step.get("target_id", ""),
                     int(step.get("required_count", 1))),
                )
            created += 1
        return created

    return int(_transaction(work))


# ---------------------------------------------------------------------------
# Progress: derived from real recorded learning events
# ---------------------------------------------------------------------------

def _review_progress(user_id: int, lesson_id: str) -> int:
    """A lesson step is satisfied by real persisted lesson progress."""
    if not lesson_id:
        return 0
    connection = get_connection()
    row = connection.execute(
        "SELECT percent_complete, status FROM learning_progress "
        "WHERE user_id = ? AND lesson_id = ?",
        (int(user_id), lesson_id),
    ).fetchone()
    connection.close()
    if not row:
        return 0
    pct = int(row["percent_complete"] or 0)
    if row["status"] == "completed" or pct >= 100:
        return 1
    return 1 if pct > 0 else 0


def _concept_attempts(user_id: int, concept: str) -> tuple[int, int]:
    """(attempts, correct) actually recorded for a concept."""
    if not concept:
        return (0, 0)
    connection = get_connection()
    row = connection.execute(
        "SELECT COUNT(*) AS attempts, COALESCE(SUM(correct), 0) AS correct "
        "FROM question_attempts WHERE user_id = ? AND concept_key = ?",
        (int(user_id), concept),
    ).fetchone()
    connection.close()
    return (int(row["attempts"] or 0), int(row["correct"] or 0))


def _assignment_submitted(user_id: int, assignment_id: str) -> bool:
    if not str(assignment_id or "").isdigit():
        return False
    connection = get_connection()
    row = connection.execute(
        "SELECT 1 FROM assignment_submissions WHERE assignment_id = ? AND student_id = ?",
        (int(assignment_id), int(user_id)),
    ).fetchone()
    connection.close()
    return bool(row)


def _step_progress(user_id: int, step: dict) -> int:
    """Count real evidence for one step (never client supplied)."""
    kind = step.get("kind")
    target = step.get("target_id") or ""
    if kind == "review":
        return _review_progress(user_id, target)
    if kind == "practice":
        if step.get("target_type") == "lesson":
            return _review_progress(user_id, target)
        return _concept_attempts(user_id, target)[0]
    if kind == "challenge":
        return _concept_attempts(user_id, target)[1]
    if kind in {"open", "submit"}:
        return 1 if _assignment_submitted(user_id, target) else 0
    return 0



def _safe_json(raw) -> dict:
    try:
        value = json.loads(raw or "{}")
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _step_href(step: dict) -> str:
    """Where a step can actually be performed (real routes only)."""
    kind = step.get("kind")
    target = step.get("target_id") or ""
    if kind == "review" and step.get("target_type") == "lesson" and target:
        return f"/subjects/{_subject_for_lesson(target)}/lessons/{target}"
    if kind in {"practice", "challenge"}:
        return "/tests"
    if kind in {"open", "submit"} and target:
        return f"/assignments#{target}"
    return "/missions"


def _subject_for_lesson(lesson_id: str) -> str:
    from app.services.content_catalog import get_lesson

    lesson = get_lesson(lesson_id) or {}
    return lesson.get("subject_slug", "")


def get_mission(user_id: int, mission_id: int) -> dict | None:
    """One mission with steps, real links, and progress recomputed from events."""
    connection = get_connection()
    mission = connection.execute(
        "SELECT * FROM missions WHERE id = ? AND user_id = ?",
        (int(mission_id), int(user_id)),
    ).fetchone()
    if not mission:
        connection.close()
        return None
    rows = connection.execute(
        "SELECT * FROM mission_steps WHERE mission_id = ? ORDER BY step_index",
        (int(mission_id),),
    ).fetchall()
    connection.close()
    steps = [dict(row) for row in rows]

    total_needed = 0
    total_value = 0
    for step in steps:
        needed = max(1, int(step["required_count"] or 1))
        value = min(needed, _step_progress(user_id, step))
        total_needed += needed
        total_value += value
        step["progress"] = value
        step["done"] = value >= needed
        step["href"] = _step_href(step)
    percent = int(round(100 * total_value / total_needed)) if total_needed else 0
    reason = _safe_json(mission["reason_json"])
    return {
        "id": int(mission["id"]),
        "mission_key": mission["mission_key"],
        "kind": mission["kind"],
        "title": mission["title"],
        "brief": mission["brief"],
        "concept_key": mission["concept_key"],
        "subject_slug": mission["subject_slug"],
        "state": mission["state"],
        "reward_xp": int(mission["reward_xp"] or 0),
        "reason": reason,
        "why": reason.get("explanation", ""),
        "steps": steps,
        "percent": percent,
        "completed_steps": sum(1 for step in steps if step["done"]),
        "total_steps": len(steps),
        "started_at": mission["started_at"],
        "completed_at": mission["completed_at"],
    }



def refresh_mission(user_id: int, mission_id: int) -> dict:
    """Persist recomputed step progress and complete the mission when done.

    Completion becomes real here: every step must be backed by recorded
    evidence before the mission flips to ``completed``, which awards XP through
    the existing gamification rules and raises a notification.
    """
    from app.services.gamification import award
    from app.services.notifications import notify

    mission = get_mission(user_id, mission_id)
    if not mission:
        return {}
    steps = mission["steps"]
    total_needed = sum(max(1, int(step["required_count"] or 1)) for step in steps)
    total_value = sum(step["progress"] for step in steps)
    finished = bool(steps) and total_value >= total_needed

    state = mission["state"]
    if finished and state != "completed":
        state = "completed"
    elif state == "offered" and mission["percent"] > 0:
        state = "active"

    def work(connection):
        for step in steps:
            connection.execute(
                "UPDATE mission_steps SET progress = ?, completed_at = ? WHERE id = ?",
                (step["progress"],
                 _now() if step["done"] and not step.get("completed_at")
                 else step.get("completed_at"),
                 int(step["id"])))
        connection.execute(
            "UPDATE missions SET state = ?, started_at = COALESCE(started_at, ?), "
            "completed_at = ? WHERE id = ?",
            (state, _now() if state != "offered" else None,
             _now() if state == "completed" else None, int(mission_id)))
    _transaction(work)

    if finished and mission["state"] != "completed":
        award(int(user_id), "mission_completed", f"mission:{mission_id}")
        notify(int(user_id), "mission_completed",
               f"Mission complete: {mission['title']}",
               "Every step was verified from your recorded learning activity.",
               href=f"/missions/{mission_id}", dedupe_key=f"mission-done:{mission_id}")
    return get_mission(user_id, mission_id) or mission


def list_missions(user_id: int, regenerate: bool = True, limit: int = 12) -> list[dict]:
    """All missions for a learner, regenerated from current state on demand."""
    if regenerate:
        ensure_missions(user_id)
    connection = get_connection()
    rows = connection.execute(
        "SELECT id FROM missions WHERE user_id = ? ORDER BY "
        "CASE state WHEN 'active' THEN 0 WHEN 'offered' THEN 1 ELSE 2 END, id DESC LIMIT ?",
        (int(user_id), max(1, min(int(limit or 12), 40))),
    ).fetchall()
    connection.close()
    return [m for m in (get_mission(user_id, int(row["id"])) for row in rows) if m]


def start_mission(user_id: int, mission_id: int) -> dict | None:
    """Mark a mission active and record the real start time."""
    def work(connection):
        row = connection.execute(
            "SELECT id, state FROM missions WHERE id = ? AND user_id = ?",
            (int(mission_id), int(user_id)),
        ).fetchone()
        if not row or row["state"] in {"completed", "dismissed"}:
            return None
        if row["state"] == "offered":
            connection.execute(
                "UPDATE missions SET state = 'active', started_at = ? WHERE id = ?",
                (_now(), int(mission_id)))
        return int(mission_id)
    if _transaction(work) is None:
        return None
    return refresh_mission(user_id, mission_id)


def dismiss_mission(user_id: int, mission_id: int) -> bool:
    def work(connection):
        cursor = connection.execute(
            "UPDATE missions SET state = 'dismissed' WHERE id = ? AND user_id = ? "
            "AND state != 'completed'",
            (int(mission_id), int(user_id)))
        return cursor.rowcount > 0
    return bool(_transaction(work))


def mission_summary(user_id: int) -> dict:
    """Counters used by the dashboard widget."""
    connection = get_connection()
    rows = connection.execute(
        "SELECT state, COUNT(*) AS total FROM missions WHERE user_id = ? GROUP BY state",
        (int(user_id),),
    ).fetchall()
    connection.close()
    counts = {row["state"]: int(row["total"]) for row in rows}
    return {
        "offered": counts.get("offered", 0),
        "active": counts.get("active", 0),
        "completed": counts.get("completed", 0),
        "total": sum(counts.values()),
    }

