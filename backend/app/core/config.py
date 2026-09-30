"""Deployment configuration for LearnCraft (local / LAN / hotspot / Docker / cloud).

Offline-first: stdlib-only `.env` parsing, no network access on import.
`APP_*` names win; historical `LEARNCRAFT_*` names still work.
"""

from __future__ import annotations

import os
from pathlib import Path


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_port(value: str | None, default: int = 5000) -> int:
    try:
        port = int(str(value).strip())
    except (TypeError, ValueError, AttributeError):
        return default
    return port if 1 <= port <= 65535 else default


def _parse_origins(raw: str | None) -> list[str]:
    if not raw:
        return []
    origins: list[str] = []
    for item in raw.split(","):
        origin = item.strip().rstrip("/")
        if origin and origin not in origins:
            origins.append(origin)
    return origins


def load_dotenv(path: str | Path | None = None) -> str | None:
    """Minimal stdlib .env loader. Env vars already set always win."""
    candidates: list[Path] = []
    if path:
        candidates.append(Path(path))
    else:
        here = Path(__file__).resolve()
        candidates.extend([here.parents[2] / ".env", here.parents[3] / ".env"])
    for candidate in candidates:
        if not candidate.is_file():
            continue
        try:
            text = candidate.read_text(encoding="utf-8")
        except OSError:
            continue
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, _, value = stripped.partition("=")
            key = key.strip()
            if not key or key in os.environ:
                continue
            os.environ[key] = value.strip().strip("'").strip('"').strip()
        return str(candidate)
    return None


load_dotenv()


def _first(*names: str, default: str = "") -> str:
    for name in names:
        value = os.environ.get(name)
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    return default


def get_host(default: str = "127.0.0.1") -> str:
    """Interface to bind. 0.0.0.0 = all NICs (LAN + hotspot)."""
    return _first("APP_HOST", "LEARNCRAFT_HOST", "HOST", default=default) or default


def get_port(default: int = 5000) -> int:
    raw = _first("APP_PORT", "LEARNCRAFT_PORT", "PORT", default="")
    return _parse_port(raw, default) if raw else default


def get_env(default: str = "development") -> str:
    return _first("APP_ENV", "FLASK_ENV", "LEARNCRAFT_ENV", default=default).lower() or default


def is_production() -> bool:
    return get_env() == "production"


def is_debug_enabled() -> bool:
    """Debug debugger opt-in; never on in production."""
    if is_production():
        return False
    # Legacy literal kept for the security regression test + operators who
    # already export FLASK_DEBUG=1 locally.
    if os.environ.get("FLASK_DEBUG", "0").strip().lower() in {"1", "true", "yes", "on"}:
        return True
    return _parse_bool(_first("APP_DEBUG", "LEARNCRAFT_DEBUG", default=""), False)


def get_cors_origins() -> list[str]:
    """Allowed browser origins. Same-origin needs NO entry here."""
    raw = _first("CORS_ORIGINS", "LEARNCRAFT_CORS_ORIGINS", default="")
    origins = _parse_origins(raw)
    if "*" in origins:
        return origins if not is_production() else []
    return origins


def get_secret_key() -> str | None:
    return _first("LEARNCRAFT_SECRET_KEY", "SECRET_KEY", default="") or None


def get_database_path(fallback: str = "") -> str:
    return _first("LEARNCRAFT_DB_PATH", "DATABASE_URL", default=fallback)


def get_network_mode(default: str = "OFFLINE") -> str:
    return _first("LEARNCRAFT_NETWORK_MODE", default=default).upper() or default


def get_master_url() -> str:
    return _first("LEARNCRAFT_MASTER_URL", default="")


def should_trust_proxy() -> bool:
    """Honour X-Forwarded-* from a reverse proxy. Default ON in production."""
    if "APP_TRUST_PROXY" in os.environ or "LEARNCRAFT_TRUST_PROXY" in os.environ:
        return _parse_bool(_first("APP_TRUST_PROXY", "LEARNCRAFT_TRUST_PROXY", default=""), False)
    return is_production()


__all__ = [
    "get_cors_origins",
    "get_database_path",
    "get_env",
    "get_host",
    "get_master_url",
    "get_network_mode",
    "get_port",
    "get_secret_key",
    "is_debug_enabled",
    "is_production",
    "load_dotenv",
    "should_trust_proxy",
]

