from __future__ import annotations

from flask import Blueprint, jsonify, request, session

from app.services.auth_service import AuthService

bp = Blueprint("auth_v1", __name__, url_prefix="/api/v1")
service = AuthService()


@bp.post("/auth/login")
def login():
    payload = request.get_json(silent=True) or {}
    user = service.authenticate(payload.get("email", ""), payload.get("password", ""))
    if not user:
        return jsonify({"success": False, "code": "INVALID_CREDENTIALS", "message": "Invalid email or password."}), 401
    session.clear()
    session["user_id"] = user["id"]
    session.permanent = True
    return jsonify({"success": True, "code": "LOGIN_SUCCESS", "user": {k: v for k, v in user.items() if k != "password_hash"}})


@bp.post("/auth/register")
def register():
    payload = request.get_json(silent=True) or {}
    try:
        user = service.create_user(payload.get("name", ""), payload.get("email", ""), payload.get("password", ""))
    except ValueError as exc:
        return jsonify({"success": False, "code": "VALIDATION_ERROR", "message": str(exc)}), 400
    session.clear()
    session["user_id"] = user["id"]
    session.permanent = True
    return jsonify({"success": True, "code": "REGISTERED", "user": {k: v for k, v in user.items() if k != "password_hash"}}), 201
