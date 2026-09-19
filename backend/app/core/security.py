import re
from datetime import timedelta
from typing import Any

from flask import current_app
from werkzeug.security import check_password_hash, generate_password_hash


def password_policy(password: str) -> tuple[bool, str | None]:
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"[A-Z]", password):
        return False, "Password must include at least one uppercase letter."
    if not re.search(r"[a-z]", password):
        return False, "Password must include at least one lowercase letter."
    if not re.search(r"\d", password):
        return False, "Password must include at least one number."
    if not re.search(r"[^A-Za-z0-9]", password):
        return False, "Password must include at least one special character."
    return True, None


def hash_password(password: str) -> str:
    return generate_password_hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return check_password_hash(password_hash, password)


def session_cookie_name() -> str:
    return current_app.config.get("SESSION_COOKIE_NAME", "learncraft_session")


def session_duration_minutes() -> int:
    return int(current_app.config.get("PERMANENT_SESSION_LIFETIME", timedelta(days=7)).total_seconds() // 60)


def make_response_payload(success: bool, message: str, code: str, data: Any | None = None, status: int = 200):
    payload = {"success": success, "message": message, "code": code}
    if data is not None:
        payload["data"] = data
    return payload, status
