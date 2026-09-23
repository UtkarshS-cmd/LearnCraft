from __future__ import annotations

from flask import Blueprint, jsonify, request, session

from app.services.teacher_control import enqueue_student_join_requests

from app.services.auth_service import AuthService, EmailExistsError

bp = Blueprint("auth_v1", __name__, url_prefix="/api/v1")
service = AuthService()


@bp.post("/auth/login")
def login():
    payload = request.get_json(silent=True) or {}
    user = service.authenticate(str(payload.get("email", "")), str(payload.get("password", "")))
    if not user:
        return jsonify({"success": False, "code": "INVALID_CREDENTIALS", "message": "Invalid email or password."}), 401
    if not service.validate_portal(user, payload.get("portal", "student")):
        return jsonify({"success": False, "code": "TEACHER_ACCOUNT_REQUIRED", "message": "This account is not a teacher account."}), 403
    session.clear()
    session["user_id"] = user["id"]
    session.permanent = True
    return jsonify({"success": True, "code": "LOGIN_SUCCESS", "user": {k: v for k, v in user.items() if k != "password_hash"}})


@bp.post("/auth/register")
def register():
    payload = request.get_json(silent=True) or {}
    account_type = str(payload.get("account_type", "student")).strip().lower()
    if account_type not in {"student", "teacher"}:
        return jsonify({"success": False, "code": "VALIDATION_ERROR", "message": "Invalid account type."}), 400
    try:
        # Same canonical service as /auth/register — identical role mapping.
        user = service.create_user(
            str(payload.get("name", "")), str(payload.get("email", "")),
            str(payload.get("password", "")), account_type,
        )
    except EmailExistsError:
        return jsonify({"success": False, "code": "EMAIL_EXISTS", "message": "An account with this email already exists."}), 409
    except ValueError as exc:
        return jsonify({"success": False, "code": "VALIDATION_ERROR", "message": str(exc)}), 400
    auto_registered = 0
    if user.get("role") == "STUDENT":
        # Auto-register the new learner with every teacher that has a class,
        # so the teacher can connect via assignments & announcements.
        try:
            auto_registered = enqueue_student_join_requests(user["id"])
        except Exception:
            auto_registered = 0
    session.clear()
    session["user_id"] = user["id"]
    session.permanent = True
    return jsonify({"success": True, "code": "REGISTERED", "auto_registered": auto_registered,
                    "user": {k: v for k, v in user.items() if k != "password_hash"}}), 201
