from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from app.database.connection import get_connection

VALID_ACCESS_STATES = {"ENABLED", "DISABLED", "LOCKED", "ASSIGNED_ONLY"}


def _dicts(rows):
    return [dict(row) for row in rows]


def teacher_classes(teacher_id: int) -> list[dict]:
    connection = get_connection()
    rows = connection.execute(
        "SELECT c.*, COUNT(cm.student_id) AS student_count FROM teacher_classes c "
        "LEFT JOIN class_members cm ON cm.class_id = c.id WHERE c.teacher_id = ? "
        "GROUP BY c.id ORDER BY c.name", (int(teacher_id),)
    ).fetchall()
    connection.close()
    return _dicts(rows)


def create_class(teacher_id: int, name: str, grade: str = "", section: str = "") -> dict:
    connection = get_connection()
    cursor = connection.execute(
        "INSERT INTO teacher_classes (teacher_id, name, grade, section) VALUES (?, ?, ?, ?)",
        (int(teacher_id), name.strip(), grade.strip(), section.strip()),
    )
    connection.commit()
    row = connection.execute("SELECT * FROM teacher_classes WHERE id = ?", (cursor.lastrowid,)).fetchone()
    connection.close()
    return dict(row)


def class_owned(teacher_id: int, class_id: int) -> bool:
    connection = get_connection()
    row = connection.execute("SELECT 1 FROM teacher_classes WHERE id = ? AND teacher_id = ?", (int(class_id), int(teacher_id))).fetchone()
    connection.close()
    return bool(row)


def add_class_member(teacher_id: int, class_id: int, student_id: int) -> bool:
    if not class_owned(teacher_id, class_id):
        return False
    connection = get_connection()
    student = connection.execute("SELECT id FROM users WHERE id = ? AND role = 'STUDENT'", (int(student_id),)).fetchone()
    if not student:
        connection.close()
        return False
    connection.execute("INSERT OR IGNORE INTO class_members (class_id, student_id) VALUES (?, ?)", (int(class_id), int(student_id)))
    connection.commit()
    connection.close()
    return True


def class_students(teacher_id: int, class_id: int) -> list[dict]:
    connection = get_connection()
    rows = connection.execute(
        "SELECT u.id, u.name, u.email, u.avatar, up.student_class, cm.joined_at "
        "FROM class_members cm JOIN teacher_classes c ON c.id = cm.class_id "
        "JOIN users u ON u.id = cm.student_id LEFT JOIN user_profiles up ON up.user_id = u.id "
        "WHERE c.teacher_id = ? AND c.id = ? ORDER BY u.name", (int(teacher_id), int(class_id))
    ).fetchall()
    connection.close()
    return _dicts(rows)


def record_event(user_id: int, event_type: str, *, subject_slug=None, activity_type=None, activity_id=None,
                 detail="", score=None, duration_seconds=None, metadata=None) -> dict:
    event_id = str(uuid.uuid4())
    connection = get_connection()
    cursor = connection.execute(
        "INSERT INTO activity_events (event_id, user_id, event_type, subject_slug, activity_type, activity_id, detail, score, duration_seconds, metadata_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (event_id, int(user_id), event_type, subject_slug, activity_type, activity_id, detail, score, duration_seconds, json.dumps(metadata or {})),
    )
    teacher_rows = connection.execute(
        "SELECT DISTINCT c.teacher_id FROM teacher_classes c JOIN class_members cm ON cm.class_id = c.id WHERE cm.student_id = ?",
        (int(user_id),),
    ).fetchall()
    for teacher in teacher_rows:
        connection.execute(
            "INSERT INTO teacher_notifications (teacher_id, event_id, kind, message) VALUES (?, ?, ?, ?)",
            (teacher["teacher_id"], cursor.lastrowid, event_type, detail or event_type.replace("_", " ").title()),
        )
    connection.commit()
    row = connection.execute(
        "SELECT e.*, u.name AS student_name FROM activity_events e JOIN users u ON u.id = e.user_id WHERE e.id = ?",
        (cursor.lastrowid,),
    ).fetchone()
    connection.close()
    return dict(row)


def dashboard_snapshot(teacher_id: int) -> dict:
    connection = get_connection()
    student_ids = [row[0] for row in connection.execute(
        "SELECT DISTINCT cm.student_id FROM class_members cm JOIN teacher_classes c ON c.id = cm.class_id WHERE c.teacher_id = ?", (int(teacher_id),)
    ).fetchall()]
    ids = tuple(student_ids)
    count = len(student_ids)
    events = []
    students = []
    if ids:
        placeholders = ",".join("?" for _ in ids)
        students = _dicts(connection.execute(
            f"SELECT u.id, u.name, u.email, u.avatar FROM users u WHERE u.id IN ({placeholders}) ORDER BY u.name", ids
        ).fetchall())
        for student in students:
            latest = connection.execute(
                "SELECT event_type, detail, subject_slug, activity_type, activity_id, score, created_at "
                "FROM activity_events WHERE user_id=? ORDER BY created_at DESC LIMIT 1", (student["id"],)
            ).fetchone()
            student.update(dict(latest) if latest else {})
            if latest:
                age = (datetime.now(timezone.utc) - datetime.fromisoformat(latest["created_at"].replace("Z", "+00:00")).replace(tzinfo=timezone.utc)).total_seconds()
                student["status"] = "OFFLINE" if latest["event_type"] == "USER_LOGOUT" or age > 1800 else ("ACTIVE" if age <= 300 else "IDLE")
            else:
                student["status"] = "OFFLINE"
        events = _dicts(connection.execute(
            f"SELECT e.*, u.name AS student_name FROM activity_events e JOIN users u ON u.id=e.user_id WHERE e.user_id IN ({placeholders}) ORDER BY e.created_at DESC LIMIT 50", ids
        ).fetchall())
        active_now = sum(student["status"] == "ACTIVE" for student in students)
        inactive = sum(student["status"] == "IDLE" for student in students)
        progress = connection.execute(
            f"SELECT COUNT(*) FROM learning_progress WHERE user_id IN ({placeholders}) AND status='completed'", ids
        ).fetchone()[0]
        games = connection.execute(
            f"SELECT COUNT(*) FROM activity_events WHERE user_id IN ({placeholders}) AND event_type='GAME_COMPLETED'", ids
        ).fetchone()[0]
        quizzes = connection.execute(
            f"SELECT COUNT(*) FROM activity_events WHERE user_id IN ({placeholders}) AND event_type='QUIZ_SUBMITTED'", ids
        ).fetchone()[0]
        score = connection.execute(
            f"SELECT AVG(score) FROM activity_events WHERE user_id IN ({placeholders}) AND score IS NOT NULL", ids
        ).fetchone()[0]
    else:
        active_now = inactive = progress = games = quizzes = 0
        score = None
    connection.close()
    return {"kpis": {"total_students": count, "active_now": active_now, "idle": inactive, "offline": count - active_now - inactive, "lessons_completed": progress,
                      "games_played": games, "quizzes_completed": quizzes, "average_score": round(score, 1) if score is not None else None,
                      "active_classes": len(teacher_classes(teacher_id))}, "students": students, "events": events}


def access_state(student_id: int, resource_type: str, resource_id: str) -> str:
    connection = get_connection()
    individual = connection.execute(
        "SELECT state FROM access_rules WHERE scope_type='STUDENT' AND scope_id=? AND resource_type=? AND resource_id=?",
        (str(student_id), resource_type, resource_id),
    ).fetchone()
    if individual:
        connection.close()
        return individual["state"]
    class_rule = connection.execute(
        "SELECT ar.state FROM access_rules ar JOIN class_members cm ON cm.class_id=CAST(ar.scope_id AS INTEGER) "
        "WHERE ar.scope_type='CLASS' AND cm.student_id=? AND ar.resource_type=? AND ar.resource_id=? "
        "ORDER BY ar.updated_at DESC LIMIT 1", (int(student_id), resource_type, resource_id),
    ).fetchone()
    connection.close()
    return class_rule["state"] if class_rule else "ENABLED"


def access_allowed(student_id: int, resource_type: str, resource_id: str) -> bool:
    state = access_state(student_id, resource_type, resource_id)
    if state in {"DISABLED", "LOCKED"}:
        return False
    if state != "ASSIGNED_ONLY":
        return True
    connection = get_connection()
    row = connection.execute(
        "SELECT 1 FROM teacher_assignments a JOIN assignment_targets t ON t.assignment_id=a.id "
        "WHERE t.student_id=? AND a.resource_type=? AND a.resource_id=? "
        "AND (a.start_at IS NULL OR a.start_at <= CURRENT_TIMESTAMP) "
        "AND (a.due_at IS NULL OR a.due_at >= CURRENT_TIMESTAMP) LIMIT 1",
        (int(student_id), resource_type, resource_id),
    ).fetchone()
    connection.close()
    return bool(row)


def set_access_rule(teacher_id: int, scope_type: str, scope_id: str, resource_type: str, resource_id: str, state: str) -> dict:
    if state not in VALID_ACCESS_STATES or scope_type not in {"CLASS", "STUDENT"}:
        raise ValueError("Invalid access rule.")
    if scope_type == "CLASS" and not class_owned(teacher_id, int(scope_id)):
        raise PermissionError("Class is not owned by this teacher.")
    connection = get_connection()
    previous = connection.execute(
        "SELECT state FROM access_rules WHERE scope_type=? AND scope_id=? AND resource_type=? AND resource_id=?",
        (scope_type, str(scope_id), resource_type, resource_id),
    ).fetchone()
    connection.execute(
        "INSERT INTO access_rules (scope_type, scope_id, resource_type, resource_id, state, updated_by) VALUES (?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(scope_type, scope_id, resource_type, resource_id) DO UPDATE SET state=excluded.state, updated_by=excluded.updated_by, updated_at=CURRENT_TIMESTAMP",
        (scope_type, str(scope_id), resource_type, resource_id, state, int(teacher_id)),
    )
    connection.execute(
        "INSERT INTO teacher_audit_logs (teacher_id, action, scope, previous_state, new_state) VALUES (?, ?, ?, ?, ?)",
        (int(teacher_id), "ACCESS_PERMISSION_CHANGED", f"{scope_type}:{scope_id}:{resource_type}:{resource_id}", previous["state"] if previous else None, state),
    )
    connection.commit()
    connection.close()
    return {"scope_type": scope_type, "scope_id": str(scope_id), "resource_type": resource_type, "resource_id": resource_id, "state": state}


def recent_notifications(teacher_id: int) -> list[dict]:
    connection = get_connection()
    rows = connection.execute("SELECT * FROM teacher_notifications WHERE teacher_id=? ORDER BY created_at DESC LIMIT 50", (int(teacher_id),)).fetchall()
    connection.close()
    return _dicts(rows)


def analytics_snapshot(teacher_id: int) -> dict:
    connection = get_connection()
    ids = [row[0] for row in connection.execute(
        "SELECT DISTINCT cm.student_id FROM class_members cm JOIN teacher_classes c ON c.id=cm.class_id WHERE c.teacher_id=?", (int(teacher_id),)
    ).fetchall()]
    if not ids:
        connection.close()
        return {"subjects": [], "topic_gaps": [], "leaderboard": []}
    placeholders = ",".join("?" for _ in ids)
    subjects = _dicts(connection.execute(
        f"SELECT subject_slug, COUNT(*) AS attempts, AVG(score) AS average_score, "
        f"SUM(CASE WHEN event_type IN ('LESSON_COMPLETED','QUIZ_SUBMITTED','GAME_COMPLETED') THEN 1 ELSE 0 END) AS completions "
        f"FROM activity_events WHERE user_id IN ({placeholders}) AND subject_slug IS NOT NULL GROUP BY subject_slug ORDER BY subject_slug", ids
    ).fetchall())
    topics = _dicts(connection.execute(
        f"SELECT COALESCE(activity_id, 'Unknown') AS topic, COUNT(*) AS attempts, AVG(score) AS average_score "
        f"FROM activity_events WHERE user_id IN ({placeholders}) AND score IS NOT NULL GROUP BY activity_id HAVING AVG(score) < 60 ORDER BY average_score", ids
    ).fetchall())
    leaderboard = _dicts(connection.execute(
        f"SELECT u.id, u.name, SUM(CASE WHEN e.event_type IN ('LESSON_COMPLETED','GAME_COMPLETED','QUIZ_SUBMITTED') THEN 1 ELSE 0 END) AS completed, "
        f"AVG(e.score) AS average_score FROM users u JOIN activity_events e ON e.user_id=u.id WHERE u.id IN ({placeholders}) GROUP BY u.id ORDER BY completed DESC, average_score DESC", ids
    ).fetchall())
    connection.close()
    for item in subjects + topics + leaderboard:
        if item.get("average_score") is not None:
            item["average_score"] = round(item["average_score"], 1)
    return {"subjects": subjects, "topic_gaps": topics, "leaderboard": leaderboard}


def create_assignment(teacher_id: int, payload: dict) -> dict:
    class_id = payload.get("class_id")
    if class_id and not class_owned(teacher_id, int(class_id)):
        raise PermissionError("Class is not owned by this teacher.")
    connection = get_connection()
    cursor = connection.execute(
        "INSERT INTO teacher_assignments (teacher_id, class_id, resource_type, resource_id, title, start_at, due_at, attempts, difficulty, time_limit_minutes) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (int(teacher_id), class_id, payload.get("resource_type", "lesson"), payload.get("resource_id", ""), payload.get("title", "Assigned activity"),
         payload.get("start_at"), payload.get("due_at"), payload.get("attempts"), payload.get("difficulty"), payload.get("time_limit_minutes")),
    )
    if class_id:
        students = connection.execute("SELECT student_id FROM class_members WHERE class_id=?", (int(class_id),)).fetchall()
        connection.executemany("INSERT INTO assignment_targets (assignment_id, student_id) VALUES (?, ?)", [(cursor.lastrowid, row[0]) for row in students])
    connection.commit()
    row = connection.execute("SELECT * FROM teacher_assignments WHERE id=?", (cursor.lastrowid,)).fetchone()
    connection.close()
    return dict(row)


def student_assignments(student_id: int) -> list[dict]:
    connection = get_connection()
    rows = connection.execute(
        "SELECT a.* FROM teacher_assignments a JOIN assignment_targets t ON t.assignment_id=a.id WHERE t.student_id=? "
        "AND (a.start_at IS NULL OR a.start_at <= CURRENT_TIMESTAMP) ORDER BY a.due_at IS NULL, a.due_at", (int(student_id),)
    ).fetchall()
    connection.close()
    return _dicts(rows)


def create_announcement(teacher_id: int, class_id: int | None, message: str) -> dict:
    if class_id and not class_owned(teacher_id, class_id):
        raise PermissionError("Class is not owned by this teacher.")
    connection = get_connection()
    cursor = connection.execute("INSERT INTO teacher_announcements (teacher_id, class_id, message) VALUES (?, ?, ?)", (int(teacher_id), class_id, message.strip()))
    connection.commit()
    row = connection.execute("SELECT * FROM teacher_announcements WHERE id=?", (cursor.lastrowid,)).fetchone()
    connection.close()
    return dict(row)


def student_announcements(student_id: int) -> list[dict]:
    connection = get_connection()
    rows = connection.execute(
        "SELECT a.* FROM teacher_announcements a LEFT JOIN class_members cm ON cm.class_id=a.class_id "
        "WHERE a.class_id IS NULL OR cm.student_id=? ORDER BY a.created_at DESC LIMIT 50", (int(student_id),)
    ).fetchall()
    connection.close()
    return _dicts(rows)