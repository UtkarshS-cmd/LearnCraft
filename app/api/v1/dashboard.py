from __future__ import annotations

from flask import Blueprint, jsonify

bp = Blueprint("dashboard_v1", __name__, url_prefix="/api/v1")


@bp.get("/dashboard")
def dashboard():
    return jsonify({
        "status": "ok",
        "data": {
            "active_students": 0,
            "completion_rate": 0,
            "offline_mode": True,
        },
    })
