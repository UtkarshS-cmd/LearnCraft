"""Shared app configuration values for the LearnCraft package layout."""

import os
from datetime import timedelta


class Config:
    SECRET_KEY = os.environ.get("LEARNCRAFT_SECRET_KEY", "dev-secret-key-change-me")
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
}
