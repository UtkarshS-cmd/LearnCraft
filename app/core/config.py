from __future__ import annotations

import os
from datetime import timedelta


class Config:
    SECRET_KEY = os.environ.get("LEARNCRAFT_SECRET_KEY", "dev-secret-key-change-me")
    DATABASE_PATH = os.environ.get("LEARNCRAFT_DB_PATH", os.path.join(os.getcwd(), "data", "learncraft.db"))
    SESSION_COOKIE_NAME = "learncraft_session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    JSON_SORT_KEYS = False


def get_config() -> dict:
    return {
        "SECRET_KEY": Config.SECRET_KEY,
        "DATABASE_PATH": Config.DATABASE_PATH,
        "SESSION_COOKIE_NAME": Config.SESSION_COOKIE_NAME,
        "SESSION_COOKIE_HTTPONLY": Config.SESSION_COOKIE_HTTPONLY,
        "SESSION_COOKIE_SAMESITE": Config.SESSION_COOKIE_SAMESITE,
        "PERMANENT_SESSION_LIFETIME": Config.PERMANENT_SESSION_LIFETIME,
        "JSON_SORT_KEYS": Config.JSON_SORT_KEYS,
    }
