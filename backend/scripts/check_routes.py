"""Cross-check that every URL the frontend calls is actually registered.

Scans the frontend (templates, JS, sandbox games) for ``fetch(...)``/``api(...)``
style calls with a static path and reports any path that has no matching Flask
route, plus verifies key static assets referenced by the service worker exist.

Run with::

    python scripts/check_routes.py
"""

from __future__ import annotations

import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Read-only route check: point the app at a throwaway DB so bootstrapping
# never writes schema/seed data into the shipped data/learncraft.db.
_DB = Path(tempfile.gettempdir()) / f"learncraft_routes_{os.getpid()}.db"
if _DB.exists():
    _DB.unlink()
os.environ["LEARNCRAFT_DB_PATH"] = str(_DB)

from app.main import create_app  # noqa: E402

FRONTEND = ROOT / "frontend"
# Repo layout keeps frontend/ at the project root (sibling of backend/), not
# inside backend/. Fall back to backend/frontend for packaged layouts.
if not FRONTEND.exists():
    FRONTEND = ROOT.parent / "frontend"

CALL_RE = re.compile(r"""(?:fetch|\bapi|apiPost|apiJson)\s*\(\s*['"`](/[^'"`\s]*)['"`]""")
ASSET_RE = re.compile(r"""^\s*'(/[^']+)',\s*$""")


def normalise(path: str) -> str:
    """Drop query strings and template/JS expressions so paths can be compared."""
    path = path.split("?")[0].rstrip()
    path = re.sub(r"\$\{[^}]*\}", "X", path)
    path = re.sub(r"\{\{[^}]*\}\}", "X", path)
    return path


def frontend_paths() -> set[str]:
    found: set[str] = set()
    patterns = ["*.html", "pages/*.html", "static/js/*.js", "static/sandbox-games/*/js/*.js",
                "static/sandbox-games/*/*.html"]
    for pattern in patterns:
        for file in FRONTEND.glob(pattern):
            text = file.read_text(encoding="utf-8", errors="ignore")
            for match in CALL_RE.finditer(text):
                found.add(normalise(match.group(1)))
    return found


def main() -> int:
    app = create_app()
    rules = list(app.url_map.iter_rules())

    def matches(path: str) -> bool:
        if path in {"/", "X"}:
            return True
        for rule in rules:
            regex = re.sub(r"<[^>]+>", "[^/]+", str(rule))
            if re.fullmatch(regex, path):
                return True
        # Concatenated calls such as fetch("/api/v1/resources/" + id + "/open")
        # end at the closing quote, leaving a fragment ending in "/". Accept it
        # when a registered rule continues from that prefix.
        if path.endswith("/") and any(str(rule).startswith(path) for rule in rules):
            return True
        return False

    problems: list[str] = []
    for path in sorted(frontend_paths()):
        if not matches(path):
            problems.append(f"frontend calls {path} but no Flask route matches")

    # Static assets the service worker pre-caches must really exist on disk.
    sw = (FRONTEND / "static" / "js" / "service-worker.js").read_text(encoding="utf-8")
    block = sw.split("APP_ASSETS = [", 1)[1].split("]", 1)[0]
    for match in ASSET_RE.finditer(block):
        asset = match.group(1)
        # '/offline' is a route, not a file.
        target = FRONTEND / asset.lstrip("/") if asset.startswith("/static/") else None
        if target is not None and not target.exists():
            problems.append(f"service worker pre-caches missing asset {asset}")

    if problems:
        print("ROUTE CHECK FAILURES:")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    print(f"Route check passed: {len(rules)} routes match every frontend call and cached asset.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())