"""Report table row counts for a LearnCraft database.

Usage::

    python scripts/db_report.py [path-to-db]
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def report(label: str, path: Path) -> None:
    if not path.exists():
        print(f"{label}: missing ({path})")
        return
    connection = sqlite3.connect(path)
    tables = [
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    ]
    print(f"{label}: {path} ({path.stat().st_size} bytes)")
    for table in tables:
        count = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table}: {count}")
    connection.close()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        report("database", Path(sys.argv[1]))
    else:
        report("current", ROOT / "data" / "learncraft.db")