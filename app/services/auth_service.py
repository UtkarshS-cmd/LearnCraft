from __future__ import annotations

from app.core.security import hash_password, password_policy, verify_password
from app.repositories.user_repository import UserRepository


class EmailExistsError(ValueError):
    """Raised when registration is attempted with an already-registered email."""


class AuthService:
    def __init__(self, repository: UserRepository | None = None):
        self.repository = repository or UserRepository()

    def validate_password(self, password: str):
        return password_policy(password)

    def create_user(self, name: str, email: str, password: str, account_type: str = "student"):
        valid, message = password_policy(password)
        if not valid:
            raise ValueError(message)
        email = str(email).strip().lower()
        if self.repository.get_by_email(email):
            raise EmailExistsError("An account with this email already exists.")
        role = "TEACHER" if str(account_type).strip().lower() in {"teacher", "admin"} else "STUDENT"
        return self.repository.create(name=name, email=email, password_hash=hash_password(password), role=role)

    def authenticate(self, email: str, password: str):
        user = self.repository.get_by_email(str(email).strip().lower())
        if not user:
            return None
        if not verify_password(password, user["password_hash"]):
            return None
        return user

    def validate_portal(self, user, portal: str) -> bool:
        """Portal check shared by both /auth/* and /api/v1/auth/* login paths."""
        if str(portal or "").strip().lower() == "teacher":
            return user.get("role") in {"TEACHER", "ADMIN"}
        return True
