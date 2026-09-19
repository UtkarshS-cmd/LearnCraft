from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str
    password: str = Field(..., min_length=8)


class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    email: str
    password: str = Field(..., min_length=8)
