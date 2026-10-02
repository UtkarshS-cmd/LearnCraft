"""Class Pulse: a teacher-facing overview where every number has a source.

Each metric carries ``value``, ``source`` (the table it came from) and ``href``
(the drill-down view), so a teacher can verify where a number came from before
acting on it. Nothing here is decorative: every field is computed from
persisted rows.
"""
from __future__ import annotations

from app.database.connection import get_connection
from app.services.early_warning import (
    FALLING_BEHIND,
    NEEDS_ATTENTION,
    STALLED,
    _student_ids,
    class_signals,
)

ACTIVE_WINDOW_DAYS = 7
INACTIVE_WINDOW_DAYS = 14
ATTENTION_STATUSES = {NEEDS_ATTENTION, FALLING_BEHIND, STALLED}


def _metric(value, source: str, href: str, label: str = "") -> dict:
    return {"value": value, "source": source, "href": href, "label": label}


def _empty_metrics() -> dict:
    return {
        "assignments": {
            "total": _metric(0, "teacher_assignments", "/teacher#assignments", "Assigned"),
            "completed": _metric(0, "assignment_submissions", "/teacher#assignments",
                                 "Submitted"),
            "completion_rate": _metric(0, "assignment_submissions / assignment_targets",
                                       "/teacher#assignments", "Completion"),
            "overdue": _metric(0, "teacher_assignments.due_at", "/teacher#assignments",
                               "Past due"),
        },
        "mastery": {
            "average": _metric(0, "concept_mastery.mastery", "/mastery", "Average mastery"),
            "concepts_tracked": _metric(0, "concept_mastery", "/mastery", "Concepts tracked"),
        },
        "difficult_concepts": [], "recent_activity": [], "recent_achievements": [],
    }


def _scoped_student_ids(teacher_id: int, class_id: int | None) -> list[int]:
    ids = _student_ids(teacher_id)
    if class_id is None:
        return ids
    connection = get_connection()
    rows = connection.execute(
        "SELECT student_id FROM class_members WHERE class_id = ?", (int(class_id),)).fetchall()
    connection.close()
    return [int(row["student_id"]) for row in rows]


def class_pulse(teacher_id: int, class_id: int | None = None) -> dict:
    """Class-level snapshot with sourced metrics and drill-down links."""
    student_ids = _scoped_student_ids(teacher_id, class_id)
    signals = [r for r in class_signals(teacher_id)
               if not class_id or r["student"]["id"] in student_ids]

    active = inactive = 0
    for report in signals:
        days = report["metrics"].get("days_since_activity")
        if days is None or days > INACTIVE_WINDOW_DAYS:
            inactive += 1
        elif days <= ACTIVE_WINDOW_DAYS:
            active += 1
    needs_attention = [r for r in signals if r["status"] in ATTENTION_STATUSES]

    if not student_ids:
        metrics = _empty_metrics()
    else:
        connection = get_connection()
        try:
            metrics = _connection_metrics(connection, student_ids)
        finally:
            connection.close()

    return {
        "class_id": class_id,
        "students": {
            "total": _metric(len(student_ids),
                             "class_members joined to teacher_classes",
                             "/teacher#students", "Students"),
            "active": _metric(active, "activity_events in the last 7 days",
                              "/teacher#students", "Active this week"),
            "inactive": _metric(inactive, "no activity for 14+ days",
                                "/teacher#students", "Inactive"),
            "needs_attention": _metric(len(needs_attention),
                                       "early_warning.class_signals",
                                       "/teacher#early-warning", "Needs attention"),
        },
        "assignments": metrics["assignments"],
        "mastery": metrics["mastery"],
        "difficult_concepts": metrics["difficult_concepts"],
        "recent_activity": metrics["recent_activity"],
        "recent_achievements": metrics["recent_achievements"],
        "students_needing_attention": [
            {"student": report["student"], "status": report["status"],
             "signals": [s["evidence"] for s in report["signals"] if s.get("status")][:3],
             "href": f"/api/v1/teacher/students/{report['student']['id']}/signals"}
            for report in needs_attention[:8]
        ],
    }


def _connection_metrics(connection, student_ids: list[int]) -> dict:
    """Assignment, mastery, activity and achievement metrics for a cohort."""
    placeholders = ",".join("?" for _ in student_ids)
    params = tuple(student_ids)

    total_assignments = connection.execute(
        f"SELECT COUNT(DISTINCT a.id) AS total FROM teacher_assignments a "
        f"JOIN assignment_targets t ON t.assignment_id = a.id "
        f"WHERE t.student_id IN ({placeholders})", params).fetchone()["total"]
    completed = connection.execute(
        f"SELECT COUNT(*) AS total FROM assignment_submissions "
        f"WHERE student_id IN ({placeholders})", params).fetchone()["total"]
    targeted = connection.execute(
        f"SELECT COUNT(*) AS total FROM assignment_targets "
        f"WHERE student_id IN ({placeholders})", params).fetchone()["total"]
    overdue = connection.execute(
        f"SELECT COUNT(DISTINCT a.id) AS total FROM teacher_assignments a "
        f"JOIN assignment_targets t ON t.assignment_id = a.id "
        f"LEFT JOIN assignment_submissions s ON s.assignment_id = a.id "
        f"AND s.student_id = t.student_id "
        f"WHERE t.student_id IN ({placeholders}) AND s.id IS NULL "
        f"AND a.due_at IS NOT NULL AND a.due_at < CURRENT_TIMESTAMP",
        params).fetchone()["total"]

    mastery_row = connection.execute(
        f"SELECT COUNT(*) AS tracked, AVG(mastery) AS average FROM concept_mastery "
        f"WHERE user_id IN ({placeholders})", params).fetchone()
    difficult = connection.execute(
        f"SELECT concept_key, AVG(mastery) AS mastery, COUNT(*) AS learners "
        f"FROM concept_mastery WHERE user_id IN ({placeholders}) "
        f"GROUP BY concept_key HAVING AVG(mastery) < 60 ORDER BY mastery ASC LIMIT 6",
        params).fetchall()
    recent = connection.execute(
        f"SELECT e.created_at, e.event_type, e.detail, u.name AS student_name "
        f"FROM activity_events e JOIN users u ON u.id = e.user_id "
        f"WHERE e.user_id IN ({placeholders}) ORDER BY e.created_at DESC LIMIT 10",
        params).fetchall()
    achievements = connection.execute(
        f"SELECT u.name AS student_name, g.level, g.xp FROM gamification g "
        f"JOIN users u ON u.id = g.user_id WHERE g.user_id IN ({placeholders}) "
        f"ORDER BY g.xp DESC LIMIT 6", params).fetchall()

    completion_rate = round(100.0 * int(completed) / int(targeted)) if int(targeted) else 0
    return {
        "assignments": {
            "total": _metric(int(total_assignments or 0), "teacher_assignments",
                             "/teacher#assignments", "Assigned"),
            "completed": _metric(int(completed or 0), "assignment_submissions",
                                 "/teacher#assignments", "Submitted"),
            "completion_rate": _metric(completion_rate,
                                       "assignment_submissions / assignment_targets",
                                       "/teacher#assignments", "Completion"),
            "overdue": _metric(int(overdue or 0), "teacher_assignments.due_at",
                               "/teacher#assignments", "Past due"),
        },
        "mastery": {
            "average": _metric(round(float(mastery_row["average"] or 0), 1),
                               "concept_mastery.mastery", "/mastery", "Average mastery"),
            "concepts_tracked": _metric(int(mastery_row["tracked"] or 0),
                                        "concept_mastery", "/mastery", "Concepts tracked"),
        },
        "difficult_concepts": [
            {"concept": row["concept_key"],
             "average_mastery": round(float(row["mastery"] or 0), 1),
             "learners": int(row["learners"] or 0),
             "source": "concept_mastery grouped by concept_key",
             "href": f"/mastery?concept={row['concept_key']}"}
            for row in difficult
        ],
        "recent_activity": [
            {"at": row["created_at"], "event": row["event_type"],
             "student": row["student_name"], "detail": row["detail"],
             "source": "activity_events", "href": "/teacher#activity"}
            for row in recent
        ],
        "recent_achievements": [
            {"student": row["student_name"], "level": int(row["level"] or 1),
             "xp": int(row["xp"] or 0), "source": "gamification",
             "href": "/teacher#students"}
            for row in achievements
        ],
    }