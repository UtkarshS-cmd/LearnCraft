from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Quiz:
    id: str = ""
    lesson_id: str = ""
    title: str = ""
    questions: list = field(default_factory=list)
