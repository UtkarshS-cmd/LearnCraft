from __future__ import annotations

from flask import Blueprint, jsonify

bp = Blueprint("subjects_v1", __name__, url_prefix="/api/v1")


@bp.get("/subjects")
def list_subjects():
    return jsonify({"items": []})
