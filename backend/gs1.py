#!/usr/bin/env python3
"""Generate schema module part 1."""
from pathlib import Path
lines = [
    '"""Canonical curriculum schema definitions.',
    '',
    'Pipeline stages: RAW -> EXTRACT -> VERIFY -> IMPORT -> RUNTIME',
    '"""',
    'from __future__ import annotations',
    '',
    'import json',
    'from dataclasses import dataclass, field',
    'from enum import Enum',
    'from pathlib import Path',
    'from typing import Any',
    '',
    'CANONICAL_SCHEMA_VERSION = "2026.09.1"',
    'SCHEMA_DOC = Path(__file__).resolve().parent / "schema_doc.json"',
    '',
]
Path('app/schemas/curriculum.py').write_text('\n'.join(lines), encoding='utf-8')
print("Part 1 done")
