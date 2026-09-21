"""Static-asset reference checker for LearnCraft.

Scans every template and bundled JavaScript file for ``/static/...`` and
``/assets/...`` references and reports any that do not exist on disk. Broken
references leave buttons or pages silently dead, so this keeps the offline-first
frontend honest.

Run with::

    python scripts/check_assets.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Repo layout keeps frontend/ at the project root (sibling of backend/),
# not inside backend/. Fall back to backend/frontend for packaged layouts.
_PROJECT_ROOT = ROOT.parent if (ROOT.parent / "frontend").exists() else ROOT
STATIC_DIR = _PROJECT_ROOT / "frontend" / "static"
TEMPLATES = _PROJECT_ROOT / "frontend" / "templates"
PATTERN = re.compile(r"/(?:static|assets)/[A-Za-z0-9_./-]+")


def main() -> int:
    referenced: set[str] = set()
    for source in list(TEMPLATES.rglob("*.html")) + list(STATIC_DIR.rglob("*.js")):
        referenced.update(PATTERN.findall(source.read_text(encoding="utf-8", errors="ignore")))

    missing = []
    for ref in sorted(referenced):
        # Only /static/* is served by Flask's static folder.
        if not ref.startswith("/static/"):
            continue
        candidate = STATIC_DIR / ref[len("/static/"):]
        if not candidate.exists():
            missing.append(ref)

    if missing:
        print("Missing static assets referenced by templates/JS:")
        for ref in missing:
            print(f"  - {ref}")
        return 1

    print(f"Asset check passed: {len(referenced)} references resolved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())