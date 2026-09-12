from __future__ import annotations

from flask import Blueprint, jsonify

bp = Blueprint("quizzes_v1", __name__, url_prefix="/api/v1")


@bp.get("/quizzes")
def list_quizzes():
    return jsonify({"items": []})
