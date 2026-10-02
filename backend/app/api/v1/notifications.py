"""Notification centre API (persistent, per-user, server-authoritative).

- ``GET  /api/v1/notifications``          list + unread count
- ``GET  /api/v1/notifications/unread``  unread count only (cheap poll)
- ``POST /api/v1/notifications/<id>/read`` mark one read
- ``POST /api/v1/notifications/read``     mark all read
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request, session

from app.services.notifications import (
    list_notifications,
    mark_read,
    unread_count,
)

bp = Blueprint("notifications_v1", __name__, url_prefix="/api/v1/notifications")


def _uid():
    return session.get("user_id")


def _unauthorized():
    return jsonify({"success": False, "code": "AUTH_REQUIRED",
                    "message": "Authentication required."}), 401


@bp.get("")
@bp.get("/")
def notifications_index():
    user_id = _uid()
    if not user_id:
        return _unauthorized()
    limit = request.args.get("limit", type=int) or 30
    unread_only = str(request.args.get("unread", "")).lower() in ("1", "true", "yes")
    items = list_notifications(int(user_id), limit, unread_only)
    return jsonify({"success": True, "items": items, "count": len(items),
                    "unread": unread_count(int(user_id))})


@bp.get("/unread")
def notifications_unread():
    user_id = _uid()
    if not user_id:
        return _unauthorized()
    return jsonify({"success": True, "unread": unread_count(int(user_id))})


@bp.post("/<int:notification_id>/read")
def read_one(notification_id: int):
    user_id = _uid()
    if not user_id:
        return _unauthorized()
    changed = mark_read(int(user_id), notification_id)
    if not changed:
        return jsonify({"success": False, "code": "NOT_FOUND",
                        "message": "Notification not found."}), 404
    return jsonify({"success": True, "unread": unread_count(int(user_id))})


@bp.post("/read")
def read_all():
    user_id = _uid()
    if not user_id:
        return _unauthorized()
    mark_read(int(user_id))
    return jsonify({"success": True, "unread": 0})
