"""Verify the additive schema migration on an existing and a fresh database."""
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("LEARNCRAFT_SECRET_KEY", "migration-check-secret")

NEW_TABLES = ["missions", "mission_steps", "learning_sessions", "notifications",
              "question_attempts", "assignment_submissions", "search_index"]


def tables(db_path):
    con = sqlite3.connect(db_path)
    names = {row[0] for row in
             con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    con.close()
    return names


def main() -> int:
    from app.database.connection import initialize_database

    # 1) Existing installation must migrate in place, keeping its users.
    existing = BACKEND / "data" / "learncraft.db"
    if existing.exists():
        before_tables = tables(existing)
        before_users = sqlite3.connect(existing).execute(
            "SELECT COUNT(*) FROM users").fetchone()[0]
        initialize_database()
        after_tables = tables(existing)
        con = sqlite3.connect(existing)
        after_users = con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        note_cols = [r[1] for r in con.execute("PRAGMA table_info(notes)")]
        con.close()
        print(f"[existing] users {before_users} -> {after_users} "
              f"({'preserved' if before_users == after_users else 'LOST DATA'})")
        print(f"[existing] new tables added: {sorted(after_tables - before_tables)}")
        print(f"[existing] note columns: {note_cols}")
        missing = [t for t in NEW_TABLES if t not in after_tables]
        if missing:
            print(f"[existing] MISSING: {missing}")
            return 1
        if before_users != after_users:
            return 1
        # Re-running must be idempotent.
        initialize_database()
        if "tags_json" not in [r[1] for r in sqlite3.connect(existing).execute(
                "PRAGMA table_info(notes)")]:
            print("[existing] re-run broke notes columns")
            return 1
        print("[existing] re-run idempotent: ok")
    else:
        print("[existing] no shipped database; skipped")

    # 2) Fresh database must contain every product-layer table.
    fresh = Path(tempfile.gettempdir()) / f"learncraft_fresh_check_{os.getpid()}.db"
    for suffix in ("", "-wal", "-shm"):
        Path(str(fresh) + suffix).unlink(missing_ok=True)
    os.environ["LEARNCRAFT_DB_PATH"] = str(fresh)
    initialize_database()
    fresh_tables = tables(fresh)
    missing = [t for t in NEW_TABLES if t not in fresh_tables]
    print(f"[fresh] {len(fresh_tables)} tables; missing: {missing}")
    for suffix in ("", "-wal", "-shm"):
        Path(str(fresh) + suffix).unlink(missing_ok=True)
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
