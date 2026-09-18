from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path


def _default_db_path() -> Path:
    # Resolve against the project root, never the process working directory,
    # so launching from another folder or a packaged desktop build keeps one DB.
    return (Path(__file__).resolve().parents[2] / "data" / "learncraft.db").as_posix()


class Config:
    SECRET_KEY = os.environ.get("LEARNCRAFT_SECRET_KEY", "dev-secret-key-change-me")
    DATABASE_PATH = os.environ.get("LEARNCRAFT_DB_PATH", _default_db_path())
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
