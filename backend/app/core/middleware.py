from __future__ import annotations

from flask import g, request


def _allowed_cors_origin(origin: str, allowed: set[str]) -> str | None:
    """Return the origin to echo back, or None when it must not be trusted."""
    if not origin or not allowed:
        return None
    if "*" in allowed:
        return "*" if origin == "*" else origin
    return origin if origin in allowed else None


def register_middlewares(app):
    # The allow-list is read per-request from app.config (not snapshotted) so
    # tests and operators can change CORS_ORIGINS without re-registering.
    def _allowed() -> set[str]:
        raw = app.config.get("CORS_ORIGINS") or []
        return {str(o).strip().rstrip("/") for o in raw if str(o).strip()}

    @app.before_request
    def _cors_preflight():
        # Browsers send OPTIONS preflight before cross-origin fetch with
        # JSON bodies. Answer from the allow-list; never with credentials
        # when the origin is not explicitly trusted.
        if request.method != "OPTIONS":
            return None
        origin = (request.headers.get("Origin") or "").strip().rstrip("/")
        if not origin:
            return None
        from flask import make_response

        echoed = _allowed_cors_origin(origin, _allowed())
        if echoed is None:
            return make_response("", 403)
        response = make_response("", 204)
        response.headers["Access-Control-Allow-Origin"] = echoed
        response.headers["Vary"] = "Origin"
        requested = request.headers.get("Access-Control-Request-Headers", "")
        response.headers["Access-Control-Allow-Headers"] = requested or "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        response.headers["Access-Control-Max-Age"] = "600"
        return response

    @app.after_request
    def after_request(response):
        response.headers["X-LearnCraft-App"] = "learncraft"
        origin = (request.headers.get("Origin") or "").strip().rstrip("/")
        echoed = _allowed_cors_origin(origin, _allowed()) if origin else None
        if echoed:
            response.headers["Access-Control-Allow-Origin"] = echoed
            response.headers["Vary"] = "Origin"
        return response

    @app.before_request
    def before_request():
        # Lazily import: middleware is imported at app start while main.py
        # is still defining current_user; a top-level import would cycle.
        from app.main import current_user

        g.current_user = current_user()

