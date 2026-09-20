#!/usr/bin/env python3
"""Generate the complete curriculum schema module."""
from pathlib import Path

output_path = Path('app/schemas/curriculum.py')

# Write the module in parts
parts = []

# Part 1: Docstring and imports
parts.append('''"""
Canonical curriculum schema definitions.

This module defines the data structures used across the RAW -> EXTRACT -> VERIFY -> IMPORT -> RUNTIME
pipeline. All curriculum packages (Class IX and Class X) must validate against these shapes before
they are imported into the runtime database.

Pipeline stages
---------------
RAW
    Source documents downloaded by scripts/ingest_sources.py and stored in data/raw/.
    These are checksummed and never modified in place.

EXTRACT
    Structured JSON produced by scripts/extract_content.py or equivalent AI-assisted tooling.
    AI-generated content is marked verified: false at this stage.

VERIFY
    Human review cycle. Once a package passes review, verified is set to true and the
    verified_at timestamp is recorded.

IMPORT
    scripts/import_content.py reads verified packages and writes them into the SQLite catalog.

RUNTIME
    The backend API and frontend consume the imported catalog. Roadmaps, concept graphs, and
    simulation mappings are derived from curriculum data at runtime, never hardcoded.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

''')

# Part 2: Enums
parts.append('''
# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Difficulty(str, Enum):
    FOUNDATION = "FOUNDATION"
    EASY = "EASY"
    MEDIUM = "MEDIUM"
    HARD = "HARD"
    BOARD_LEVEL = "BOARD_LEVEL"
    CHALLENGE = "CHALLENGE"


class QuestionType(str, Enum):
    MCQ = "MCQ"
    MULTIPLE_CORRECT = "MULTIPLE_CORRECT"
    TRUE_FALSE = "TRUE_FALSE"
    SHORT_ANSWER = "SHORT_ANSWER"
    LONG_ANSWER = "LONG_ANSWER"
    APPLICATION = "APPLICATION"
    SCENARIO_BASED = "SCENARIO_BASED"
    COMPETENCY_BASED = "COMPETENCY_BASED"
    ASSERTION_REASON = "ASSERTION_REASON"
    FILL_BLANK = "FILL_BLANK"
    NUMERICAL = "NUMERICAL"
    CASE_BASED = "CASE_BASED"
    DIAGRAM_BASED = "DIAGRAM_BASED"


class VerificationStatus(str, Enum):
    PENDING = "PENDING"
    AI_GENERATED = "AI_GENERATED"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class CompetencyCategory(str, Enum):
    REMEMBER = "Remember"
    UNDERSTAND = "Understand"
    APPLY = "Apply"
    ANALYZE = "Analyze"
    EVALUATE = "Evaluate"
    CREATE = "Create"


class Board(str, Enum):
    CBSE = "CBSE"
    NCERT = "NCERT"


CANONICAL_SCHEMA_VERSION = "2026.09.1"
SCHEMA_DOC = Path(__file__).resolve().parent / "schema_doc.json"

''')

# Part 3: SourceMetadata
parts.append('''
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
        for k in ("publisher", "url", "version", "academic_year", "accessed_at",
                  "checksum_sha256", "notes"):
            v = getattr(self, k, None)
            if v is not None:
                d[k] = v
        return d

    @classmethod
    def from_dict(cls, data: dict) -> SourceMetadata:
        return cls(**{k: v for k, v in data.items() if v is not None})

    def __eq__(self, other):
        if not isinstance(other, SourceMetadata):
            return False
        return self.source_id == other.source_id

''')

# Write all parts
output_path.write_text(''.join(parts), encoding='utf-8')
print(f"Written base schema: {output_path.stat().st_size} bytes")
