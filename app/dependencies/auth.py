from __future__ import annotations

from functools import wraps

from flask import redirect, request, session


def get_current_user():
    from app.main import current_user

    return current_user()


def require_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return redirect("/login")
        return view(*args, **kwargs)

    return wrapped
