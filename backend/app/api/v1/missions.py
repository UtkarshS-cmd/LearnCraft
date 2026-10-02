"""Mission Engine API (learner-scoped).

- ``GET  /api/v1/missions``            list, regenerated from learning state
- ``GET  /api/v1/missions/<id>``       one mission with recomputed progress
- ``POST /api/v1/missions/<id>/start`` mark active (records start time)
- ``POST /api/v1/missions/<id>/progress`` recompute progress from real events
- ``POST /api/v1/missions/<id>/dismiss``
- ``GET  /api/v1/missions/summary``    counters for dashboard widgets

Every route is scoped to ``session['user_id']``; another learner's mission id
returns 404 (never their data).
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request, session

from app.services.mission_engine import (
    dismiss_mission,
    get_mission,
    list_missions,
    mission_summary,
    refresh_mission,
    start_mission,
)

bp = Blueprint("missions_v1", __name__, url_prefix="/api/v1/missions")


def _uid():
    return session.get("user_id")


@bp.get("")
@bp.get("/")
def missions_index():
    user_id = _uid()
    if not user_id:
        return jsonify({"success": False, "message": "Authentication required."}), 401
    limit = request.args.get("limit", type=int) or 12
    items = list_missions(int(user_id), limit=limit)
    return jsonify({"success": True, "items": items, "count": len(items),
                    "summary": mission_summary(int(user_id))})


@bp.get("/summary")
def missions_summary():
    user_id = _uid()
    if not user_id:
        return jsonify({"success": False, "message": "Authentication required."}), 401
    return jsonify({"success": True, "summary": mission_summary(int(user_id))})


@bp.get("/<int:mission_id>")
def mission_detail(mission_id: int):
    user_id = _uid()
    if not user_id:
        return jsonify({"success": False, "message": "Authentication required."}), 401
    item = get_mission(int(user_id), mission_id)
    if not item:
        return jsonify({"success": False, "code": "NOT_FOUND",
                        "message": "Mission not found."}), 404
    return jsonify({"success": True, "mission": item})


@bp.post("/<int:mission_id>/start")
def mission_start(mission_id: int):
    user_id = _uid()
    if not user_id:
        return jsonify({"success": False, "message": "Authentication required."}), 401
    item = start_mission(int(user_id), mission_id)
    if not item:
        return jsonify({"success": False, "code": "NOT_FOUND",
                        "message": "Mission not found or already finished."}), 404
    return jsonify({"success": True, "mission": item})


@bp.post("/<int:mission_id>/progress")
def mission_progress(mission_id: int):
    """Recompute step/mission progress from recorded learning events."""
    user_id = _uid()
    if not user_id:
        return jsonify({"success": False, "message": "Authentication required."}), 401
    item = refresh_mission(int(user_id), mission_id)
    if not item:
        return jsonify({"success": False, "code": "NOT_FOUND",
                        "message": "Mission not found."}), 404
    return jsonify({"success": True, "mission": item})


@bp.post("/<int:mission_id>/dismiss")
def mission_dismiss(mission_id: int):
    user_id = _uid()
    if not user_id:
        return jsonify({"success": False, "message": "Authentication required."}), 401
    if not dismiss_mission(int(user_id), mission_id):
        return jsonify({"success": False, "code": "NOT_FOUND",
                        "message": "Mission not found or already completed."}), 404
    return jsonify({"success": True})
