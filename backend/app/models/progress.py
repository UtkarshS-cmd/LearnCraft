from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Progress:
    id: int | None = None
    user_id: int | None = None
    subject_slug: str | None = None
    chapter_id: str | None = None
    lesson_id: str | None = None
    status: str = "not_started"
    percent_complete: int = 0
    score: float = 0.0
    last_activity: str | None = None
