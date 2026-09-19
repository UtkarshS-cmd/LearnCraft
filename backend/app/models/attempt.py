from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Attempt:
    id: int | None = None
    user_id: int | None = None
    quiz_id: str | None = None
    score: float = 0.0
    submitted_at: str | None = None
    status: str = "draft"
