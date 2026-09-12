"""Auth route helpers exposed under the app package namespace."""

from server import (
    auth_login,
    auth_logout,
    auth_me,
    auth_register,
    auth_update_profile,
    current_user,
    require_auth,
)

__all__ = [
    "auth_login",
    "auth_logout",
    "auth_me",
    "auth_register",
    "auth_update_profile",
    "current_user",
    "require_auth",
]
