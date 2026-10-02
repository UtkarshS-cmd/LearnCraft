"""Learning Session Mode API (focused, resumable, evidence-based summary).

- ``GET  /api/v1/sessions/current``   resume an interrupted session
- ``POST /api/v1/sessions``           start (or resume) a session
- ``POST /api/v1/sessions/<id>/stage`` move to the next canonical stage
- ``POST /api/v1/sessions/<id>/finish`` complete + evidence-based summary
- ``POST /api/v1/sessions/<id>/abandon``
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request, session

from app.services.learning_session import (
    abandon_session,
    advance_stage,
    current_session,
    finish_session,
    get_session,
    stages,
    start_session,
)

bp = Blueprint("sessions_v1", __name__, url_prefix="/api/v1/sessions")


def _uid():
    return session.get("user_id")


def _unauthorized():
    return jsonify({"success": False, "code": "AUTH_REQUIRED",
                    "message": "Authentication required."}), 401


@bp.get("/stages")
def session_stages():
    """The canonical stage cycle (single source of truth)."""
    return jsonify({"success": True, "stages": stages()})


@bp.get("/current")
def current():
    user_id = _uid()
    if not user_id:
        return _unauthorized()
    item = current_session(int(user_id))
    return jsonify({"success": True, "session": item, "stages": stages(),
                    "active": bool(item)})


@bp.post("")
@bp.post("/")
def start():
    user_id = _uid()
    if not user_id:
        return _unauthorized()
    payload = request.get_json(silent=True) or {}
    mission_id = payload.get("mission_id")
    item = start_session(
        int(user_id),
        lesson_id=str(payload.get("lesson_id", ""))[:180],
        mission_id=int(mission_id) if str(mission_id or "").isdigit() else None,
        goal=str(payload.get("goal", ""))[:200],
        subject_slug=str(payload.get("subject_slug", ""))[:120],
    )
    return jsonify({"success": True, "session": item, "stages": stages()})


@bp.get("/<int:session_id>")
def detail(session_id: int):
    user_id = _uid()
    if not user_id:
        return _unauthorized()
    item = get_session(int(user_id), session_id)
    if not item:
        return jsonify({"success": False, "code": "NOT_FOUND",
                        "message": "Session not found."}), 404
    return jsonify({"success": True, "session": item, "stages": stages()})


@bp.post("/<int:session_id>/stage")
def stage(session_id: int):
    user_id = _uid()
    if not user_id:
        return _unauthorized()
    payload = request.get_json(silent=True) or {}
    item = advance_stage(int(user_id), session_id, payload.get("stage"))
    if not item:
        return jsonify({"success": False, "code": "NOT_FOUND",
                        "message": "No active session with that id."}), 404
    return jsonify({"success": True, "session": item, "stages": stages()})


@bp.post("/<int:session_id>/finish")
def finish(session_id: int):
    user_id = _uid()
    if not user_id:
        return _unauthorized()
    item = finish_session(int(user_id), session_id)
    if not item:
        return jsonify({"success": False, "code": "NOT_FOUND",
                        "message": "Session not found."}), 404
    return jsonify({"success": True, "session": item})


@bp.post("/<int:session_id>/abandon")
def abandon(session_id: int):
    user_id = _uid()
    if not user_id:
        return _unauthorized()
    if not abandon_session(int(user_id), session_id):
        return jsonify({"success": False, "code": "NOT_FOUND",
                        "message": "Session not found or already finished."}), 404
    return jsonify({"success": True})