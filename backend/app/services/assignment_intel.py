"""Assignment intelligence: what actually happened after work was assigned.

Extends (never replaces) the existing assignment + quiz engine. It answers,
from persisted rows only: completion state (targets vs submissions), concepts
students struggled with, common wrong answers, students needing support, and
mastery movement since the assignment was created.
"""
from __future__ import annotations

from app.database.connection import get_connection


def assignment_insights(teacher_id: int, assignment_id: int) -> dict:
    """Insights for one assignment owned by this teacher ({} when not)."""
    connection = get_connection()
    try:
        assignment = connection.execute(
            "SELECT * FROM teacher_assignments WHERE id = ? AND teacher_id = ?",
            (int(assignment_id), int(teacher_id))).fetchone()
        if not assignment:
            return {}
        targets = [int(row["student_id"]) for row in connection.execute(
            "SELECT student_id FROM assignment_targets WHERE assignment_id = ?",
            (int(assignment_id),)).fetchall()]
        submissions = [dict(row) for row in connection.execute(
            "SELECT s.student_id, s.score, s.submitted_at, u.name AS student_name "
            "FROM assignment_submissions s JOIN users u ON u.id = s.student_id "
            "WHERE s.assignment_id = ?", (int(assignment_id),)).fetchall()]
        return _insights(connection, dict(assignment), targets, submissions)
    finally:
        connection.close()


def _concept_keys_for_resource(resource_id: str) -> list[str]:
    """Candidate mastery keys for an assigned resource.

    Mastery rows in LearnCraft are keyed either by concept id (newer quiz
    checks) or by chapter/lesson id (older rows), so intelligence must consider
    every key that could legitimately match instead of assuming one shape.
    """
    if not resource_id:
        return []
    from app.services.concept_map import _graph, graph_node

    keys = [resource_id]
    if graph_node(resource_id).get("chapter_id"):
        return keys
    for class_name in _installed_classes():
        for concept_id, node in _graph(class_name)["nodes"].items():
            if node.get("lesson_id") == resource_id:
                keys.append(concept_id)
                if node.get("chapter_id"):
                    keys.append(node["chapter_id"])
    return list(dict.fromkeys(keys))


def _installed_classes() -> list[str]:
    from app.services.curriculum_pipeline import available_class_dirs

    return [d.name for d in available_class_dirs()]


def _concept_rows(connection, targets: list[int], keys: list[str]) -> list[dict]:
    if not targets or not keys:
        return []
    target_ph = ",".join("?" for _ in targets)
    key_ph = ",".join("?" for _ in keys)
    return [dict(row) for row in connection.execute(
        f"SELECT concept_key, AVG(mastery) AS mastery, SUM(attempts) AS attempts, "
        f"AVG(accuracy) AS accuracy FROM concept_mastery "
        f"WHERE user_id IN ({target_ph}) AND concept_key IN ({key_ph}) GROUP BY concept_key",
        tuple(targets) + tuple(keys)).fetchall()]


def _common_wrong_answers(connection, targets: list[int], keys: list[str]) -> list[dict]:
    """Most-missed questions for this cohort on the assigned concept."""
    if not targets or not keys:
        return []
    target_ph = ",".join("?" for _ in targets)
    key_ph = ",".join("?" for _ in keys)
    rows = connection.execute(
        f"SELECT question_id, COUNT(*) AS misses FROM question_attempts "
        f"WHERE user_id IN ({target_ph}) AND concept_key IN ({key_ph}) AND correct = 0 "
        f"GROUP BY question_id ORDER BY misses DESC LIMIT 5",
        tuple(targets) + tuple(keys)).fetchall()
    return [{"question_id": row["question_id"], "misses": int(row["misses"]),
             "source": "question_attempts where correct = 0"} for row in rows]


def _mastery_movement(rows: list[dict]) -> dict:
    average = round(sum(float(r["mastery"] or 0) for r in rows) / len(rows), 1) if rows else 0
    return {"average_mastery": average, "concepts": len(rows),
            "source": "concept_mastery.average for the assigned cohort"}


def _now(connection) -> str:
    return connection.execute("SELECT CURRENT_TIMESTAMP AS now").fetchone()["now"]


def _student_support(connection, student_id: int, keys: list[str], submitted: bool,
                     due_at, now: str) -> dict:
    """Neutral reasons why one student may need support on this assignment."""
    row = connection.execute("SELECT name FROM users WHERE id = ?", (int(student_id),)).fetchone()
    mastery = _student_concept_mastery(connection, student_id, keys)
    misses = _student_misses(connection, student_id, keys)
    reasons = []
    if not submitted:
        reasons.append("Past due and not submitted." if due_at and str(due_at) < now
                       else "Not submitted yet.")
    if mastery and float(mastery["mastery"] or 0) < 40:
        reasons.append(f"Concept mastery is {round(float(mastery['mastery']), 1)}%.")
    if int(misses) >= 2:
        reasons.append(f"{misses} incorrect answers on this concept.")
    return {"student_id": int(student_id), "student_name": row["name"] if row else "",
            "reasons": reasons, "submitted": submitted,
            "source": "assignment_submissions + concept_mastery + question_attempts"}
def _student_concept_mastery(connection, student_id: int, keys: list[str]):
    if not keys:
        return None
    key_ph = ",".join("?" for _ in keys)
    return connection.execute(
        f"SELECT concept_key, mastery FROM concept_mastery WHERE user_id = ? "
        f"AND concept_key IN ({key_ph}) ORDER BY mastery ASC LIMIT 1",
        tuple([int(student_id)] + keys)).fetchone()


def _student_misses(connection, student_id: int, keys: list[str]) -> int:
    if not keys:
        return 0
    key_ph = ",".join("?" for _ in keys)
    return int(connection.execute(
        f"SELECT COUNT(*) AS total FROM question_attempts WHERE user_id = ? "
        f"AND concept_key IN ({key_ph}) AND correct = 0",
        tuple([int(student_id)] + keys)).fetchone()["total"] or 0)


def _insights(connection, assignment: dict, targets: list[int],
              submissions: list[dict]) -> dict:
    """Assemble the full insight payload for one assignment."""
    submitted_ids = {row["student_id"] for row in submissions}
    keys = _concept_keys_for_resource(assignment.get("resource_id") or "")
    now = _now(connection)
    rows = _concept_rows(connection, targets, keys)

    struggled = []
    for row in rows:
        accuracy = row["accuracy"]
        if accuracy is None or float(accuracy) < 60:
            struggled.append({
                "concept": row["concept_key"],
                "average_mastery": round(float(row["mastery"] or 0), 1),
                "attempts": int(row["attempts"] or 0),
                "accuracy": round(float(accuracy), 1) if accuracy is not None else None,
                "source": "concept_mastery for the assigned cohort",
            })
    struggled.sort(key=lambda item: item["accuracy"] if item["accuracy"] is not None else 0)

    needs_support = [
        _student_support(connection, student_id, keys,
                         student_id in submitted_ids, assignment.get("due_at"), now)
        for student_id in targets
    ]
    needs_support = [item for item in needs_support if item["reasons"]]
    needs_support.sort(key=lambda item: len(item["reasons"]), reverse=True)

    return {
        "assignment": {
            "id": int(assignment["id"]), "title": assignment["title"],
            "class_id": assignment.get("class_id"),
            "resource_type": assignment.get("resource_type"),
            "resource_id": assignment.get("resource_id") or "",
            "due_at": assignment.get("due_at"), "created_at": assignment.get("created_at"),
        },
        "completion": {
            "assigned": len(targets),
            "submitted": len(submissions),
            "outstanding": len(targets) - len(submissions),
            "rate": round(100.0 * len(submissions) / len(targets)) if targets else 0,
            "due_at": assignment.get("due_at"),
            "source": "assignment_targets vs assignment_submissions",
        },
        "concepts": {
            "focus": keys,
            "struggled": struggled[:8],
            "movement": _mastery_movement(rows),
            "source": "concept_mastery + question_attempts",
        },
        "common_wrong_answers": _common_wrong_answers(connection, targets, keys),
        "students_needing_support": needs_support[:10],
        "submissions": submissions,
    }