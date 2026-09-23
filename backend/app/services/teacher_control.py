from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from app.database.connection import get_connection

VALID_ACCESS_STATES = {"ENABLED", "DISABLED", "LOCKED", "ASSIGNED_ONLY"}


def enqueue_student_join_requests(student_id: int) -> int:
    """Auto-register a freshly created student with every teaching teacher.

    Called right after a student account is created so teachers see the
    learner in a pending queue and can approve them into a class with one
    click — instead of the old manual "type a numeric user ID" flow.
    Returns the number of pending requests created.
    """
    from app.database.connection import _transaction

    def work(connection):
        # Every teacher/admin gets the request; class_id is the teacher's first
        # class when one exists, otherwise NULL (they can pick a class at
        # approval time). This way a student who registers before the teacher
        # creates any class still shows up in the approval queue.
        teachers = connection.execute(
            "SELECT u.id AS teacher_id, "
            "(SELECT MIN(c.id) FROM teacher_classes c WHERE c.teacher_id = u.id) AS class_id "
            "FROM users u WHERE u.role IN ('TEACHER', 'ADMIN') ORDER BY u.id",
        ).fetchall()
        created = 0
        for teacher in teachers:
            cursor = connection.execute(
                "INSERT OR IGNORE INTO student_join_requests (student_id, teacher_id, class_id, status) "
                "VALUES (?, ?, ?, 'PENDING')",
                (int(student_id), int(teacher["teacher_id"]), teacher["class_id"]),
            )
            created += cursor.rowcount
        if created:
            student = connection.execute("SELECT name FROM users WHERE id = ?", (int(student_id),)).fetchone()
            student_name = student["name"] if student else "A new student"
            for teacher in teachers:
                connection.execute(
                    "INSERT INTO teacher_notifications (teacher_id, kind, message) VALUES (?, ?, ?)",
                    (int(teacher["teacher_id"]), "STUDENT_JOIN_REQUEST",
                     f"{student_name} created an account and is waiting for approval into your class."),
                )
        return created

    return int(_transaction(work))


def teacher_join_requests(teacher_id: int) -> list[dict]:
    """Pending student join requests for this teacher's dashboard."""
    connection = get_connection()
    rows = connection.execute(
        "SELECT r.id, r.student_id, r.class_id, r.status, r.created_at, u.name, u.email, u.avatar, c.name AS class_name "
        "FROM student_join_requests r JOIN users u ON u.id = r.student_id "
        "LEFT JOIN teacher_classes c ON c.id = r.class_id "
        "WHERE r.teacher_id = ? AND r.status = 'PENDING' ORDER BY r.created_at DESC",
        (int(teacher_id),),
    ).fetchall()
    connection.close()
    return _dicts(rows)


def decide_join_request(teacher_id: int, request_id: int, approve: bool, class_id: int | None = None) -> dict | None:
    """Approve or reject a student join request.

    Approval adds the student to the (suggested or overridden) class, which
    is exactly what connects them to this teacher's assignments,
    announcements, analytics, activity feed and access-control rules.
    Returns a summary dict, or ``None`` when the request is not pending /
    not owned by this teacher.
    """
    from app.database.connection import _transaction

    def work(connection):
        row = connection.execute(
            "SELECT * FROM student_join_requests WHERE id = ? AND teacher_id = ? AND status = 'PENDING'",
            (int(request_id), int(teacher_id)),
        ).fetchone()
        if not row:
            return None
        target_class = int(class_id) if class_id else row["class_id"]
        if approve and target_class:
            owned = connection.execute(
                "SELECT 1 FROM teacher_classes WHERE id = ? AND teacher_id = ?",
                (target_class, int(teacher_id)),
            ).fetchone()
            if not owned:
                return None
            connection.execute(
                "INSERT OR IGNORE INTO class_members (class_id, student_id) VALUES (?, ?)",
                (target_class, int(row["student_id"])),
            )
        connection.execute(
            "UPDATE student_join_requests SET status = ?, class_id = ?, decided_at = CURRENT_TIMESTAMP WHERE id = ?",
            ("APPROVED" if approve else "REJECTED", target_class, int(request_id)),
        )
        return {"request_id": int(request_id), "student_id": int(row["student_id"]),
                "class_id": target_class, "status": "APPROVED" if approve else "REJECTED"}

    return _transaction(work)


def _clean_due_at(value):
    """Normalize optional assignment due dates to SQLite timestamps.

    Accepts ``YYYY-MM-DD HH:MM:SS`` (also ``T``-separated / date-only) and
    stores ``None`` for blank values; rejects anything else so bad input
    fails fast instead of persisting garbage comparisons.
    """
    if value in (None, ""):
        return None
    text = str(value).strip()
    if not text:
        return None
    text = text.replace("T", " ")
    if len(text) == 10:
        text = f"{text} 00:00:00"
    try:
        datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        raise ValueError("due_at must look like YYYY-MM-DD HH:MM:SS.")
    return text


def _dicts(rows):
    return [dict(row) for row in rows]


def teacher_classes(teacher_id: int) -> list[dict]:
    from app.database.connection import _transaction

    def work(connection):
        return connection.execute(
            "SELECT c.*, COUNT(cm.student_id) AS student_count FROM teacher_classes c "
            "LEFT JOIN class_members cm ON cm.class_id = c.id WHERE c.teacher_id = ? "
            "GROUP BY c.id ORDER BY c.name", (int(teacher_id),)
        ).fetchall()
    return _dicts(_transaction(work))


def create_class(teacher_id: int, name: str, grade: str = "", section: str = "") -> dict:
    from app.database.connection import _transaction

    cleaned = str(name or "").strip()
    if not cleaned:
        raise ValueError("Class name is required.")

    def work(connection):
        cursor = connection.execute(
            "INSERT INTO teacher_classes (teacher_id, name, grade, section) VALUES (?, ?, ?, ?)",
            (int(teacher_id), cleaned, str(grade or "").strip(), str(section or "").strip()),
        )
        return connection.execute("SELECT * FROM teacher_classes WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return dict(_transaction(work))


def class_owned(teacher_id: int, class_id: int) -> bool:
    connection = get_connection()
    row = connection.execute("SELECT 1 FROM teacher_classes WHERE id = ? AND teacher_id = ?", (int(class_id), int(teacher_id))).fetchone()
    connection.close()
    return bool(row)


def remove_class_member(teacher_id: int, class_id: int, student_id: int) -> bool:
    if not class_owned(teacher_id, class_id):
        return False
    from app.database.connection import _transaction

    def work(connection):
        cursor = connection.execute(
            "DELETE FROM class_members WHERE class_id = ? AND student_id = ?",
            (int(class_id), int(student_id)),
        )
        return cursor.rowcount > 0
    return bool(_transaction(work))


def delete_class(teacher_id: int, class_id: int) -> bool:
    if not class_owned(teacher_id, class_id):
        return False
    from app.database.connection import _transaction

    def work(connection):
        # FK cascades are enforced (PRAGMA foreign_keys=ON) but deleting the
        # class would orphan sent work; keep student-visible rows, only ungroup.
        connection.execute("DELETE FROM class_members WHERE class_id = ?", (int(class_id),))
        connection.execute(
            "DELETE FROM access_rules WHERE scope_type = 'CLASS' AND scope_id = ?", (str(class_id),)
        )
        connection.execute("UPDATE teacher_assignments SET class_id = NULL WHERE class_id = ?", (int(class_id),))
        connection.execute("UPDATE teacher_announcements SET class_id = NULL WHERE class_id = ?", (int(class_id),))
        cursor = connection.execute(
            "DELETE FROM teacher_classes WHERE id = ? AND teacher_id = ?", (int(class_id), int(teacher_id))
        )
        return cursor.rowcount > 0
    return bool(_transaction(work))


def add_class_member(teacher_id: int, class_id: int, student_id: int) -> bool:
    if not class_owned(teacher_id, class_id):
        return False
    from app.database.connection import _transaction

    def work(connection):
        student = connection.execute("SELECT id FROM users WHERE id = ? AND role = 'STUDENT'", (int(student_id),)).fetchone()
        if not student:
            return False
        connection.execute("INSERT OR IGNORE INTO class_members (class_id, student_id) VALUES (?, ?)", (int(class_id), int(student_id)))
        return True
    return bool(_transaction(work))


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
    from app.database.connection import _transaction

    event_id = str(uuid.uuid4())

    def work(connection):
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
        return connection.execute(
            "SELECT e.*, u.name AS student_name FROM activity_events e JOIN users u ON u.id = e.user_id WHERE e.id = ?",
            (cursor.lastrowid,),
        ).fetchone()
    return dict(_transaction(work))


def dashboard_snapshot(teacher_id: int) -> dict:
    connection = get_connection()
    student_ids = [row[0] for row in connection.execute(
        "SELECT DISTINCT cm.student_id FROM class_members cm JOIN teacher_classes c ON c.id = cm.class_id WHERE c.teacher_id = ?", (int(teacher_id),)
    ).fetchall()]
    pending_requests = connection.execute(
        "SELECT COUNT(*) FROM student_join_requests WHERE teacher_id = ? AND status = 'PENDING'", (int(teacher_id),)
    ).fetchone()[0]
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
                      "active_classes": len(teacher_classes(teacher_id)), "pending_requests": pending_requests}, "students": students, "events": events}


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
    from app.database.connection import _transaction

    def work(connection):
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
    _transaction(work)
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
    from app.database.connection import _transaction

    due_at = _clean_due_at(payload.get("due_at"))
    class_id = payload.get("class_id")
    if class_id in ("", None):
        class_id = None
    else:
        class_id = int(class_id)
        if not class_owned(teacher_id, class_id):
            raise PermissionError("Class is not owned by this teacher.")

    def work(connection):
        cursor = connection.execute(
            "INSERT INTO teacher_assignments (teacher_id, class_id, title, resource_type, resource_id, due_at) VALUES (?, ?, ?, ?, ?, ?)",
            (int(teacher_id), class_id, str(payload.get("title") or "Untitled assignment").strip() or "Untitled assignment",
             str(payload.get("resource_type") or "lesson"), str(payload.get("resource_id") or ""), due_at),
        )
        assignment_id = cursor.lastrowid
        students = (
            [row["student_id"] for row in connection.execute("SELECT student_id FROM class_members WHERE class_id = ?", (class_id,)).fetchall()]
            if class_id is not None else
            [row["student_id"] for row in connection.execute(
                "SELECT cm.student_id FROM class_members cm JOIN teacher_classes c ON c.id = cm.class_id JOIN users u ON u.id = cm.student_id WHERE c.teacher_id = ? AND u.role = 'STUDENT'",
                (int(teacher_id),)).fetchall()]
        )
        connection.executemany(
            "INSERT OR IGNORE INTO assignment_targets (assignment_id, student_id) VALUES (?, ?)",
            [(assignment_id, int(student_id)) for student_id in students],
        )
        return connection.execute("SELECT * FROM teacher_assignments WHERE id = ?", (assignment_id,)).fetchone()
    return dict(_transaction(work))


def student_assignments(student_id: int) -> list[dict]:
    connection = get_connection()
    rows = connection.execute(
        "SELECT a.* FROM teacher_assignments a JOIN assignment_targets t ON t.assignment_id=a.id WHERE t.student_id=? "
        "AND (a.start_at IS NULL OR a.start_at <= CURRENT_TIMESTAMP) ORDER BY a.due_at IS NULL, a.due_at", (int(student_id),)
    ).fetchall()
    connection.close()
    return _dicts(rows)


def teacher_sent_assignments(teacher_id: int) -> list[dict]:
    connection = get_connection()
    rows = connection.execute(
        "SELECT a.*, c.name AS class_name, "
        "(SELECT COUNT(*) FROM assignment_targets t WHERE t.assignment_id = a.id) AS student_count "
        "FROM teacher_assignments a LEFT JOIN teacher_classes c ON c.id = a.class_id "
        "WHERE a.teacher_id = ? ORDER BY a.created_at DESC LIMIT 50", (int(teacher_id),)
    ).fetchall()
    connection.close()
    return _dicts(rows)


def teacher_sent_announcements(teacher_id: int) -> list[dict]:
    connection = get_connection()
    rows = connection.execute(
        "SELECT a.*, c.name AS class_name FROM teacher_announcements a "
        "LEFT JOIN teacher_classes c ON c.id = a.class_id "
        "WHERE a.teacher_id = ? ORDER BY a.created_at DESC LIMIT 50", (int(teacher_id),)
    ).fetchall()
    connection.close()
    return _dicts(rows)


def create_announcement(teacher_id: int, class_id: int | None, message: str) -> dict:
    from app.database.connection import _transaction

    cleaned = str(message or "").strip()
    if not cleaned:
        raise ValueError("Announcement message is required.")
    if class_id in ("", None):
        class_id = None
    else:
        class_id = int(class_id)
        if not class_owned(teacher_id, class_id):
            raise PermissionError("Class is not owned by this teacher.")

    def work(connection):
        cursor = connection.execute("INSERT INTO teacher_announcements (teacher_id, class_id, message) VALUES (?, ?, ?)", (int(teacher_id), class_id, cleaned))
        return connection.execute("SELECT * FROM teacher_announcements WHERE id=?", (cursor.lastrowid,)).fetchone()
    return dict(_transaction(work))


def student_announcements(student_id: int) -> list[dict]:
    """Announcements visible to one student (class-scoped + global).

    The LEFT JOIN must constrain the membership to this student, otherwise a
    class announcement leaks to every student in any class.
    """
    connection = get_connection()
    rows = connection.execute(
        "SELECT a.* FROM teacher_announcements a LEFT JOIN class_members cm ON cm.class_id = a.class_id AND cm.student_id = ? "
        "WHERE a.class_id IS NULL OR cm.student_id IS NOT NULL ORDER BY a.created_at DESC LIMIT 50", (int(student_id),)
    ).fetchall()
    connection.close()
    return _dicts(rows)


def student_owned_by_teacher(teacher_id: int, student_id: int) -> bool:
    connection = get_connection()
    row = connection.execute(
        "SELECT 1 FROM class_members cm JOIN teacher_classes c ON c.id=cm.class_id WHERE c.teacher_id=? AND cm.student_id=?",
        (int(teacher_id), int(student_id)),
    ).fetchone()
    connection.close()
    return bool(row)


def student_profile(teacher_id: int, student_id: int) -> dict | None:
    if not student_owned_by_teacher(teacher_id, student_id):
        return None
    connection = get_connection()
    user = connection.execute("SELECT id, name, email, avatar, created_at FROM users WHERE id=? AND role='STUDENT'", (int(student_id),)).fetchone()
    if not user:
        connection.close()
        return None
    progress = _dicts(connection.execute("SELECT * FROM learning_progress WHERE user_id=? ORDER BY updated_at DESC", (int(student_id),)).fetchall())
    events = _dicts(connection.execute("SELECT * FROM activity_events WHERE user_id=? ORDER BY created_at DESC LIMIT 100", (int(student_id),)).fetchall())
    assignments = _dicts(connection.execute("SELECT a.* FROM teacher_assignments a JOIN assignment_targets t ON t.assignment_id=a.id WHERE t.student_id=?", (int(student_id),)).fetchall())
    connection.close()
    scores = [event["score"] for event in events if event.get("score") is not None]
    return {"student": dict(user), "progress": progress, "events": events, "assignments": assignments,
            "summary": {"lessons_completed": sum(row["status"] == "completed" for row in progress),
                        "games_completed": sum(event["event_type"] == "GAME_COMPLETED" for event in events),
                        "quiz_submissions": sum(event["event_type"] == "QUIZ_SUBMITTED" for event in events),
                        "average_score": round(sum(scores) / len(scores), 1) if scores else None}}


def mark_notifications_read(teacher_id: int, notification_id: int | None = None) -> None:
    from app.database.connection import _transaction

    def work(connection):
        if notification_id is None:
            connection.execute("UPDATE teacher_notifications SET read_at=CURRENT_TIMESTAMP WHERE teacher_id=? AND read_at IS NULL", (int(teacher_id),))
        else:
            connection.execute("UPDATE teacher_notifications SET read_at=CURRENT_TIMESTAMP WHERE id=? AND teacher_id=?", (int(notification_id), int(teacher_id)))
    _transaction(work)


def activity_report(teacher_id: int, student_id: int | None = None) -> list[dict]:
    connection = get_connection()
    params = [int(teacher_id)]
    query = "SELECT e.created_at, u.name AS student_name, e.event_type, e.subject_slug, e.activity_type, e.activity_id, e.detail, e.score FROM activity_events e JOIN users u ON u.id=e.user_id JOIN class_members cm ON cm.student_id=e.user_id JOIN teacher_classes c ON c.id=cm.class_id WHERE c.teacher_id=?"
    if student_id is not None:
        query += " AND e.user_id=?"
        params.append(int(student_id))
    query += " GROUP BY e.id ORDER BY e.created_at DESC"
    rows = _dicts(connection.execute(query, params).fetchall())
    connection.close()
    return rows