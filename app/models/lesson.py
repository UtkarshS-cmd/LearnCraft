from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Lesson:
    id: str = ""
    title: str = ""
    subject_slug: str = ""
    description: str = ""
    duration: str = ""
    blocks: list = field(default_factory=list)
