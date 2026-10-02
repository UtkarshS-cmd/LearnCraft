"""Teacher early-warning engine.

Turns persisted learning data into NEUTRAL, evidence-backed signals so a
teacher can decide where to intervene. It never labels a learner: statuses
describe the *evidence*, not the person, and every status ships the exact
numbers behind it.

Signals (all derived from real rows):
  * ``REPEATED_INCORRECT``  - several incorrect answers in the last 14 days
  * ``REPEATED_ATTEMPTS``   - many attempts with no accuracy gain
  * ``DECLINING_ACTIVITY``  - this week's events well below last week's
  * ``STALLED_ASSIGNMENT``  - an assignment is past due and not submitted
  * ``WEAK_PREREQUISITE``   - a concept below 40% mastery
  * ``LONG_INACTIVITY``     - no learning activity for a week or more
  * ``IMPROVING`` / ``STRONG_PROGRESS`` - positive counterparts

Severity ladder (neutral wording): NEEDS_ATTENTION > FALLING_BEHIND > STALLED
> IMPROVING > STRONG_PROGRESS.
"""
from __future__ import annotations

from app.database.connection import get_connection

NEEDS_ATTENTION = "NEEDS_ATTENTION"
FALLING_BEHIND = "FALLING_BEHIND"
STALLED = "STALLED"
IMPROVING = "IMPROVING"
STRONG_PROGRESS = "STRONG_PROGRESS"

SEVERITY = {NEEDS_ATTENTION: 5, FALLING_BEHIND: 4, STALLED: 3,
            IMPROVING: 2, STRONG_PROGRESS: 1}

WEAK_MASTERY = 40.0
INACTIVE_DAYS = 7
STATUSES = [NEEDS_ATTENTION, FALLING_BEHIND, STALLED, IMPROVING, STRONG_PROGRESS]


def _student_ids(teacher_id: int) -> list[int]:
    connection = get_connection()
    rows = connection.execute(
        "SELECT DISTINCT cm.student_id FROM class_members cm "
        "JOIN teacher_classes c ON c.id = cm.class_id WHERE c.teacher_id = ?",
        (int(teacher_id),),
    ).fetchall()
    connection.close()
    return [int(row["student_id"]) for row in rows]


def _days_since(timestamp) -> int | None:
    from datetime import datetime, timezone

    if not timestamp:
        return None
    try:
        value = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return max(0, (datetime.now(timezone.utc) - value).days)
    except (TypeError, ValueError):
        return None


def _overall_status(signals: list[dict]) -> str:
    statuses = [s["status"] for s in signals if s.get("status")]
    if not statuses:
        return STRONG_PROGRESS
    return max(statuses, key=lambda s: SEVERITY.get(s, 0))


def _collect(connection, student_id: int) -> dict:
    """One pass over the persisted evidence for a single student."""
    last_event = connection.execute(
        "SELECT created_at, event_type FROM activity_events WHERE user_id = ? "
        "ORDER BY created_at DESC LIMIT 1", (int(student_id),)).fetchone()
    this_week = connection.execute(
        "SELECT COUNT(*) AS total FROM activity_events WHERE user_id = ? "
        "AND created_at >= datetime('now', '-7 days')", (int(student_id),)).fetchone()["total"]
    prev_week = connection.execute(
        "SELECT COUNT(*) AS total FROM activity_events WHERE user_id = ? "
        "AND created_at >= datetime('now', '-14 days') AND created_at < datetime('now', '-7 days')",
        (int(student_id),)).fetchone()["total"]
    attempts = connection.execute(
        "SELECT COUNT(*) AS total, COALESCE(SUM(correct), 0) AS correct "
        "FROM question_attempts WHERE user_id = ? AND created_at >= datetime('now', '-14 days')",
        (int(student_id),)).fetchone()
    mastery_rows = connection.execute(
        "SELECT concept_key, mastery FROM concept_mastery WHERE user_id = ? "
        "ORDER BY mastery ASC LIMIT 8", (int(student_id),)).fetchall()
    pending = connection.execute(
        "SELECT a.id, a.title, a.due_at FROM teacher_assignments a "
        "JOIN assignment_targets t ON t.assignment_id = a.id "
        "LEFT JOIN assignment_submissions s ON s.assignment_id = a.id AND s.student_id = t.student_id "
        "WHERE t.student_id = ? AND s.id IS NULL ORDER BY a.due_at IS NULL, a.due_at",
        (int(student_id),)).fetchall()
    now = connection.execute("SELECT CURRENT_TIMESTAMP AS now").fetchone()["now"]
    return {
        "last_event": dict(last_event) if last_event else None,
        "this_week": int(this_week),
        "prev_week": int(prev_week),
        "attempts": int(attempts["total"] or 0),
        "correct": int(attempts["correct"] or 0),
        "weak": [dict(row) for row in mastery_rows
                 if float(row["mastery"] or 0) < WEAK_MASTERY],
        "pending": [dict(row) for row in pending],
        "overdue": [dict(row) for row in pending
                    if row["due_at"] and str(row["due_at"]) < str(now)],
    }
def _signals_from(data: dict) -> list[dict]:
    """Map the collected evidence to neutral, evidence-backed signals."""
    signals: list[dict] = []
    attempts, correct = data["attempts"], data["correct"]
    incorrect = attempts - correct
    accuracy = round(100.0 * correct / attempts, 1) if attempts else None
    days_idle = _days_since(data["last_event"]["created_at"]) if data["last_event"] else None

    if incorrect >= 3:
        signals.append({
            "code": "REPEATED_INCORRECT", "status": NEEDS_ATTENTION,
            "evidence": f"{incorrect} of {attempts} recent answers were incorrect.",
            "metric": {"incorrect": incorrect, "attempts": attempts},
            "source": "question_attempts (last 14 days)",
        })
    if attempts >= 6 and accuracy is not None and accuracy < 45:
        signals.append({
            "code": "REPEATED_ATTEMPTS", "status": NEEDS_ATTENTION,
            "evidence": f"{attempts} attempts at {accuracy}% accuracy - not improving yet.",
            "metric": {"attempts": attempts, "accuracy": accuracy},
            "source": "question_attempts (last 14 days)",
        })
    if data["prev_week"] >= 3 and data["this_week"] < data["prev_week"] / 2:
        signals.append({
            "code": "DECLINING_ACTIVITY", "status": FALLING_BEHIND,
            "evidence": f"{data['this_week']} learning events this week vs "
                        f"{data['prev_week']} last week.",
            "metric": {"this_week": data["this_week"], "last_week": data["prev_week"]},
            "source": "activity_events",
        })
    if data["overdue"]:
        signals.append({
            "code": "STALLED_ASSIGNMENT", "status": STALLED,
            "evidence": f"{len(data['overdue'])} assignment(s) past due and not submitted.",
            "metric": {"overdue": len(data["overdue"]),
                       "titles": [row["title"] for row in data["overdue"][:3]]},
            "source": "teacher_assignments.due_at vs assignment_submissions",
        })
    elif data["pending"]:
        signals.append({
            "code": "ASSIGNMENT_OPEN", "status": None,
            "evidence": f"{len(data['pending'])} assignment(s) still open.",
            "metric": {"open": len(data["pending"])},
            "source": "assignment_targets",
        })
    if data["weak"]:
        signals.append({
            "code": "WEAK_PREREQUISITE", "status": NEEDS_ATTENTION,
            "evidence": f"{len(data['weak'])} concept(s) below {WEAK_MASTERY:.0f}% mastery: "
                        + ", ".join(row["concept_key"] for row in data["weak"][:3]),
            "metric": {"weak_concepts": len(data["weak"])},
            "source": "concept_mastery",
        })
    if days_idle is not None and days_idle >= INACTIVE_DAYS:
        signals.append({
            "code": "LONG_INACTIVITY", "status": FALLING_BEHIND,
            "evidence": f"No learning activity for {days_idle} day(s).",
            "metric": {"days_idle": days_idle},
            "source": "activity_events.created_at",
        })
    if accuracy is not None and attempts >= 4 and accuracy >= 80:
        signals.append({
            "code": "STRONG_PROGRESS", "status": STRONG_PROGRESS,
            "evidence": f"{accuracy}% accuracy across {attempts} recent attempts.",
            "metric": {"accuracy": accuracy},
            "source": "question_attempts (last 14 days)",
        })
    if days_idle is not None and days_idle <= 1 and (accuracy or 0) >= 60:
        signals.append({
            "code": "IMPROVING", "status": IMPROVING,
            "evidence": f"Active today with {accuracy}% recent accuracy.",
            "metric": {"accuracy": accuracy},
            "source": "activity_events + question_attempts",
        })
    return signals


def student_signals(teacher_id: int, student_id: int) -> dict:
    """Full, evidence-backed signal report for one of this teacher's students."""
    from app.services.teacher_control import student_owned_by_teacher

    if not student_owned_by_teacher(teacher_id, student_id):
        return {}
    connection = get_connection()
    try:
        student = connection.execute(
            "SELECT id, name, email, avatar FROM users WHERE id = ? AND role = 'STUDENT'",
            (int(student_id),)).fetchone()
        if not student:
            return {}
        data = _collect(connection, student_id)
    finally:
        connection.close()

    signals = _signals_from(data)
    accuracy = (round(100.0 * data["correct"] / data["attempts"], 1)
                if data["attempts"] else None)
    days_idle = _days_since(data["last_event"]["created_at"]) if data["last_event"] else None
    return {
        "student": {"id": int(student["id"]), "name": student["name"],
                    "email": student["email"], "avatar": student["avatar"]},
        "status": _overall_status(signals),
        "signals": signals,
        "metrics": {
            "events_this_week": data["this_week"],
            "events_last_week": data["prev_week"],
            "attempts_14d": data["attempts"],
            "accuracy_14d": accuracy,
            "days_since_activity": days_idle,
            "open_assignments": len(data["pending"]),
            "overdue_assignments": len(data["overdue"]),
            "weak_concepts": [row["concept_key"] for row in data["weak"][:5]],
        },
        "last_event": data["last_event"],
    }


def class_signals(teacher_id: int) -> list[dict]:
    """Signal overview for every student of this teacher, most severe first."""
    reports = []
    for student_id in _student_ids(teacher_id):
        report = student_signals(teacher_id, student_id)
        if report:
            reports.append(report)
    reports.sort(key=lambda r: (-SEVERITY.get(r["status"], 0),
                                str(r["student"]["name"]).lower()))
    return reports
