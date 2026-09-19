from __future__ import annotations

from flask import Blueprint, jsonify, session

from app.services.user_service import UserService
from app.database.connection import user_payload

bp = Blueprint("users_v1", __name__, url_prefix="/api/v1")
service = UserService()


def _user_id():
    return session.get("user_id")


def _require_teacher():
    user = _user_id()
    if not user:
        return None, (jsonify({"success": False, "code": "UNAUTHORIZED", "message": "Authentication required."}), 401)
    payload = user_payload(user) if isinstance(user, dict) else None
    if payload and payload.get("role") not in {"TEACHER", "ADMIN"}:
        return None, (jsonify({"success": False, "code": "FORBIDDEN", "message": "Insufficient permissions."}), 403)
    return user, None


@bp.get("/users")
def list_users():
    user_id, err = _require_teacher()
    if err:
        return err
    users = service.get_users()
    safe = []
    for u in users:
        p = user_payload(u)
        safe.append({k: v for k, v in p.items() if k != "password_hash"})
    return jsonify({"items": safe})
