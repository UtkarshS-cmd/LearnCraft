from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, jsonify, request, session

from app.database.connection import get_user_progress, save_learning_progress

bp = Blueprint("progress_v1", __name__, url_prefix="/api/v1")


@bp.get("/progress")
def list_progress():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "message": "Authentication required."}), 401
    return jsonify({"items": get_user_progress(user_id)})


@bp.post("/progress")
def save_progress():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "message": "Authentication required."}), 401
    payload = request.get_json(silent=True) or {}
    lesson_id = str(payload.get("lesson_id", "")).strip()
    subject_slug = str(payload.get("subject_slug", "")).strip()
    if not lesson_id or not subject_slug:
        return jsonify({"success": False, "message": "lesson_id and subject_slug are required."}), 400
    percent = max(0, min(100, int(payload.get("percent_complete", 0))))
    status = str(payload.get("status", "in_progress"))
    if status not in {"not_started", "in_progress", "practiced", "completed"}:
        return jsonify({"success": False, "message": "Invalid progress status."}), 400
    save_learning_progress(user_id, subject_slug=subject_slug, chapter_id=payload.get("chapter_id"),
                           lesson_id=lesson_id, status=status, percent_complete=percent,
                           score=payload.get("score", 0),
                           last_activity=datetime.now(timezone.utc).isoformat())
    return jsonify({"success": True, "lesson_id": lesson_id, "percent_complete": percent, "status": status}), 200
