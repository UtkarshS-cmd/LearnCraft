"""Version 1 API package."""

from .auth import bp as auth_bp
from .dashboard import bp as dashboard_bp
from .users import bp as users_bp

__all__ = ["auth_bp", "dashboard_bp", "users_bp"]
