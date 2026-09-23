"""Pytest-wide database isolation.

Each integration test module used to set ``LEARNCRAFT_DB_PATH`` at import time,
so the database a run actually used depended on module import order — and any
module imported before those assignments ran against the real
``data/learncraft.db``. This conftest pins one throwaway database for the whole
pytest session *before* any ``app`` module is imported, so tests can never
pollute the shipped database again.
"""

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TEST_DB = Path(tempfile.gettempdir()) / f"learncraft_pytest_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

# Legacy integration modules still pin their own LEARNCRAFT_DB_PATH at import
# time (test_auth -> learncraft_test_*, test_teacher_control -> learncraft_*,
# etc.), and those throwaway files persist across sessions. Stale rows (e.g. a
# previously registered student@example.com) then fail this session's
# registrations with 409 EMAIL_EXISTS. Purge every learncraft test database in
# the temp directory before the session starts; the real database lives in
# backend/data and is never touched by this cleanup.
for stale in Path(tempfile.gettempdir()).glob("learncraft_*.db"):
    for candidate in (stale, stale.with_suffix(".db-wal"), stale.with_suffix(".db-shm")):
        try:
            candidate.unlink()
        except OSError:
            pass

os.environ["LEARNCRAFT_DB_PATH"] = str(TEST_DB)
os.environ["LEARNCRAFT_SECRET_KEY"] = "pytest-secret-key"

import pytest  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _isolated_database():
    """Guarantee a fresh isolated database for the whole session."""
    if TEST_DB.exists():
        TEST_DB.unlink()
    yield
    # Keep the file around on failure to debug, remove it on a clean exit.
    if TEST_DB.exists():
        TEST_DB.unlink()