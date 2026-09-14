from __future__ import annotations

from flask import Blueprint, jsonify, request, session

from app.services.teacher_control import (
    add_class_member,
    class_owned,
    class_students,
    create_class,
    dashboard_snapshot,
    analytics_snapshot,
    create_announcement,
    create_assignment,
    recent_notifications,
    set_access_rule,
    teacher_classes,
)

bp = Blueprint("teacher_v1", __name__, url_prefix="/api/v1/teacher")


def teacher_id():
    from app.main import current_user

    user = current_user()
    if not user or user.get("role") not in {"TEACHER", "ADMIN"}:
        return None
    return int(user["id"])


def forbidden():
    return jsonify({"success": False, "message": "Teacher access required.", "code": "FORBIDDEN"}), 403


@bp.get("/dashboard")
def dashboard():
    user_id = teacher_id()
    if not user_id:
        return forbidden()
    return jsonify({"success": True, **dashboard_snapshot(user_id)})


@bp.get("/classes")
def classes():
    user_id = teacher_id()
    if not user_id:
        return forbidden()
    return jsonify({"success": True, "items": teacher_classes(user_id)})


@bp.post("/classes")
def create_teacher_class():
    user_id = teacher_id()
    if not user_id:
        return forbidden()
    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name", "")).strip()
    if not name:
        return jsonify({"success": False, "message": "Class name is required.", "code": "VALIDATION_ERROR"}), 400
    return jsonify({"success": True, "item": create_class(user_id, name, str(payload.get("grade", "")), str(payload.get("section", ""))) }), 201


@bp.get("/classes/<int:class_id>/students")
def students(class_id):
    user_id = teacher_id()
    if not user_id or not class_owned(user_id, class_id):
        return forbidden()
    return jsonify({"success": True, "items": class_students(user_id, class_id)})


@bp.post("/classes/<int:class_id>/students")
def add_student(class_id):
    user_id = teacher_id()
    if not user_id:
        return forbidden()
    payload = request.get_json(silent=True) or {}
    student_id = payload.get("student_id")
    if not student_id or not add_class_member(user_id, class_id, int(student_id)):
        return jsonify({"success": False, "message": "Class or student was not found.", "code": "NOT_FOUND"}), 404
    return jsonify({"success": True, "message": "Student added to class."}), 201


@bp.post("/access")
def access():
    user_id = teacher_id()
    if not user_id:
        return forbidden()
    payload = request.get_json(silent=True) or {}
    try:
        item = set_access_rule(
            user_id,
            str(payload.get("scope_type", "CLASS")).upper(),
            str(payload.get("scope_id", "")),
            str(payload.get("resource_type", "lesson")),
            str(payload.get("resource_id", "")),
            str(payload.get("state", "ENABLED")).upper(),
        )
    except (ValueError, PermissionError) as exc:
        return jsonify({"success": False, "message": str(exc), "code": "VALIDATION_ERROR"}), 400
    return jsonify({"success": True, "item": item})


@bp.get("/notifications")
def notifications():
    user_id = teacher_id()
    if not user_id:
        return forbidden()
    return jsonify({"success": True, "items": recent_notifications(user_id)})


@bp.get("/analytics")
def analytics():
    user_id = teacher_id()
    if not user_id:
        return forbidden()
    return jsonify({"success": True, **analytics_snapshot(user_id)})


@bp.post("/assignments")
def assignment():
    user_id = teacher_id()
    if not user_id:
        return forbidden()
    try:
        return jsonify({"success": True, "item": create_assignment(user_id, request.get_json(silent=True) or {})}), 201
    except PermissionError as exc:
        return jsonify({"success": False, "message": str(exc), "code": "FORBIDDEN"}), 403


@bp.post("/announcements")
def announcement():
    user_id = teacher_id()
    if not user_id:
        return forbidden()
    payload = request.get_json(silent=True) or {}
    message = str(payload.get("message", "")).strip()
    if not message:
        return jsonify({"success": False, "message": "Announcement message is required.", "code": "VALIDATION_ERROR"}), 400
    try:
        return jsonify({"success": True, "item": create_announcement(user_id, payload.get("class_id"), message)}), 201
    except PermissionError as exc:
        return jsonify({"success": False, "message": str(exc), "code": "FORBIDDEN"}), 403
