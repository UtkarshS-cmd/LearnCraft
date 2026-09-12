from __future__ import annotations

from flask import Blueprint, jsonify

bp = Blueprint("progress_v1", __name__, url_prefix="/api/v1")


@bp.get("/progress")
def list_progress():
    return jsonify({"items": []})
