"""End-to-end smoke test for the LearnCraft application.

Boots the Flask app with its test client, exercises every HTML page, the
authentication flow and the main JSON APIs, and fails loudly on any error so
regressions are easy to spot.

Run with::

    python scripts/smoke_test.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Isolate in a throwaway database: the smoke test registers accounts and must
# never touch the shipped data/learncraft.db.
_DB = Path(tempfile.gettempdir()) / f"learncraft_smoke_{os.getpid()}.db"
if _DB.exists():
    _DB.unlink()
os.environ["LEARNCRAFT_DB_PATH"] = str(_DB)

from app.main import create_app  # noqa: E402


PAGES = [
    "/login",
    "/register",
    "/offline",
    "/home",
    "/my-learning",
    "/subjects",
    "/practical",
    "/assignments",
    "/sandbox",
    "/progress",
    "/notes",
    "/profile",
    "/settings",
    "/help",
    "/tests",
    "/ask-ai",
    "/teacher",
]

API_GET = [
    "/api/health",
    "/api/v1/subjects",
    "/api/v1/lessons",
    "/api/v1/quizzes",
    "/api/v1/content-manifest",
    "/api/system/status",
]


def main() -> int:
    app = create_app()
    app.config.update(TESTING=True)
    failures: list[str] = []

    with app.test_client() as client:
        for path in PAGES:
            response = client.get(path, follow_redirects=False)
            status = response.status_code
            # Pages behind auth redirect (302) when anonymous; that is expected.
            if status not in (200, 302):
                failures.append(f"GET {path} -> {status}")

        for path in API_GET:
            response = client.get(path)
            if response.status_code not in (200, 302):
                failures.append(f"GET {path} -> {response.status_code}")

        # Content collections must expose real seeded data, not empty shells.
        for path in ("/api/v1/subjects", "/api/v1/lessons", "/api/v1/quizzes",
                     "/api/v1/content-manifest"):
            payload = (client.get(path).get_json() or {})
            items = payload.get("items") if isinstance(payload, dict) else payload
            if not items:
                failures.append(f"GET {path} returned no items (content catalog not seeded?)")

        # ---- Authentication flow -------------------------------------------
        email = "smoke.student@example.com"
        password = "SmokeTest123!"
        register = client.post(
            "/auth/register",
            data=json.dumps(
                {
                    "email": email,
                    "password": password,
                    "name": "Smoke Student",
                    "account_type": "student",
                }
            ),
            content_type="application/json",
        )
        if register.status_code not in (200, 201, 409):
            failures.append(f"POST /auth/register -> {register.status_code}")
        login = client.post(
            "/auth/login",
            data=json.dumps({"email": email, "password": password}),
            content_type="application/json",
        )
        if login.status_code != 200:
            failures.append(f"POST /auth/login -> {login.status_code}")

        # Authenticated pages/APIs must render directly (no auth redirect).
        for path in ("/home", "/subjects", "/my-learning", "/practical", "/assignments",
                     "/sandbox", "/progress", "/notes", "/profile", "/settings",
                     "/help", "/tests", "/ask-ai", "/api/v1/dashboard",
                     "/api/v1/progress", "/api/v1/users", "/api/content/catalog"):
            response = client.get(path)
            if response.status_code != 200:
                failures.append(f"[auth] GET {path} -> {response.status_code}")

        # The teacher console must reject a student account outright.
        teacher_as_student = client.get("/teacher")
        if teacher_as_student.status_code not in (403, 302):
            failures.append(f"[auth] student GET /teacher -> {teacher_as_student.status_code}")

    if failures:
        print("SMOKE TEST FAILURES:")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print(f"Smoke test passed: {len(PAGES)} pages and {len(API_GET)} APIs checked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())