from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Subject:
    id: str = ""
    slug: str = ""
    name: str = ""
    description: str = ""
    color: str = "#4F46E5"
    lessons: list = field(default_factory=list)
