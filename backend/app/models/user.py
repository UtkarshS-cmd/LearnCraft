from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class User:
    id: int | None = None
    name: str = ""
    email: str = ""
    password_hash: str = ""
    role: str = "STUDENT"
    avatar: str | None = None
    bio: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    preferences: dict = field(default_factory=dict)

    @property
    def initials(self) -> str:
        parts = [piece for piece in self.name.split() if piece]
        if not parts:
            return "LC"
        initials = "".join(part[0].upper() for part in parts[:2])
        return initials[:2] or "LC"
