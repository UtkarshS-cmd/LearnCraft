from __future__ import annotations

from flask import Blueprint, jsonify

bp = Blueprint("lessons_v1", __name__, url_prefix="/api/v1")


@bp.get("/lessons")
def list_lessons():
    return jsonify({"items": []})
