from __future__ import annotations

from flask import Blueprint, jsonify

from app.services.user_service import UserService

bp = Blueprint("users_v1", __name__, url_prefix="/api/v1")
service = UserService()


@bp.get("/users")
def list_users():
    return jsonify(service.get_users())
