from __future__ import annotations

import os
from pathlib import Path

DB_PATH = Path(os.environ.get("LEARNCRAFT_DB_PATH", Path("data") / "learncraft.db"))

if DB_PATH.exists():
    DB_PATH.unlink()
    print(f"Removed {DB_PATH}")
else:
    print(f"No database at {DB_PATH}")
