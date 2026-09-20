#!/usr/bin/env python3
"""Append dataclasses to curriculum schema."""
from pathlib import Path

p = Path('app/schemas/curriculum.py')
content = p.read_text(encoding='utf-8')

dataclasses_code = '''
@dataclass
class SourceMetadata:
    """Source provenance for any curriculum entity."""
    source_id: str
    source_type: str
    title: str
    publisher: str | None = None
    url: str | None = None
    version: str | None = None
    academic_year: str | None = None
    accessed_at: str | None = None
    checksum_sha256: str | None = None
    notes: str | None = None

    def to_dict(self) -> dict:
        d = {"source_id": self.source_id, "source_type": self.source_type, "title": self.title}
        for k in ("publisher", "url", "version", "academic_year",
                  "accessed_at", "checksum_sha256", "notes"):
            v = getattr(self, k, None)
            if v is not None:
                d[k] = v
        return d

    @classmethod
    def from_dict(cls, data: dict) -> SourceMetadata:
        return cls(**{k: v for k, v in data.items() if v is not None})

'''

p.write_text(content + dataclasses_code, encoding='utf-8')
print(f"Added SourceMetadata. Total: {len(p.read_text().splitlines())} lines")
