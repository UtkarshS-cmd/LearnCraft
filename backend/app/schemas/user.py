from __future__ import annotations

from pydantic import BaseModel, Field


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    role: str = "STUDENT"
    avatar: str | None = None
    bio: str | None = None


class ProfileUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    email: str | None = None
    avatar: str | None = None
    bio: str | None = Field(default=None, max_length=250)
