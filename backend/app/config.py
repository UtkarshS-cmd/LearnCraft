"""Shared app configuration values for the LearnCraft package layout.

Legacy shim: the deployment source of truth is now
``app.core.config`` (APP_HOST/APP_PORT/APP_ENV/CORS_ORIGINS + .env loading).
This module re-exports the same values so older imports keep working.
"""

from __future__ import annotations

import os
from datetime import timedelta

from app.core.config import get_cors_origins, get_env, get_secret_key


class Config:
    SECRET_KEY = get_secret_key() or os.environ.get(
        "LEARNCRAFT_SECRET_KEY", "dev-secret-key-change-me"
    )
    SESSION_COOKIE_NAME = "learncraft_session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    JSON_SORT_KEYS = False


DEFAULT_CONFIG = {
    "SECRET_KEY": Config.SECRET_KEY,
    "SESSION_COOKIE_NAME": Config.SESSION_COOKIE_NAME,
    "SESSION_COOKIE_HTTPONLY": Config.SESSION_COOKIE_HTTPONLY,
    "SESSION_COOKIE_SAMESITE": Config.SESSION_COOKIE_SAMESITE,
    "PERMANENT_SESSION_LIFETIME": Config.PERMANENT_SESSION_LIFETIME,
    "JSON_SORT_KEYS": Config.JSON_SORT_KEYS,
    "APP_ENV": get_env("development"),
    "CORS_ORIGINS": get_cors_origins(),
}

