from __future__ import annotations

from flask import Blueprint, jsonify, session

from app.database.connection import get_user_progress

bp = Blueprint("dashboard_v1", __name__, url_prefix="/api/v1")


@bp.get("/dashboard")
def dashboard():
    """Per-student dashboard snapshot computed from persisted progress rows.

    Returns a zeroed snapshot for anonymous callers so the offline shell and
    health probes keep working without a session.
    """
    user_id = session.get("user_id")
    rows = get_user_progress(user_id) if user_id else []
    completed = sum(row.get("status") == "completed" for row in rows)
    completion_rate = (
        round(sum(int(row.get("percent_complete", 0) or 0) for row in rows) / len(rows))
        if rows else 0
    )
    subjects = sorted({row["subject_slug"] for row in rows if row.get("subject_slug")})
    return jsonify({
        "status": "ok",
        "data": {
            "active_students": 1 if user_id else 0,
            "completion_rate": completion_rate,
            "lessons_tracked": len(rows),
            "lessons_completed": completed,
            "subjects_in_progress": subjects,
            "offline_mode": True,
        },
    })
