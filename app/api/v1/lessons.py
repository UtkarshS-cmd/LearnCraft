from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.services.content_catalog import get_lesson

bp = Blueprint("lessons_v1", __name__, url_prefix="/api/v1")


@bp.get("/lessons")
def list_lessons():
    lesson_id = request.args.get("id")
    if lesson_id:
        lesson = get_lesson(lesson_id)
        if not lesson:
            return jsonify({"success": False, "message": "Lesson not found."}), 404
        return jsonify(lesson)
    return jsonify({"items": []})
