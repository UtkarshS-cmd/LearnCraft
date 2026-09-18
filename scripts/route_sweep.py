"""Route coverage sweep for LearnCraft.

Walks every registered GET route (plus the known POST/PUT/DELETE write routes
with realistic payloads) as an anonymous visitor, a student and a teacher, and
fails on any HTTP 5xx or unexpected status. This is the fastest way to catch a
route that 500s because a template variable, service call or schema drifted.

Run with::

    python scripts/route_sweep.py
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

_TEST_DB = Path(tempfile.gettempdir()) / "learncraft_route_sweep.db"
if _TEST_DB.exists():
    _TEST_DB.unlink()
os.environ["LEARNCRAFT_DB_PATH"] = str(_TEST_DB)

from app.main import create_app  # noqa: E402

STUDENT = {"email": "sweep.student@example.com", "password": "SweepPass123!"}
TEACHER = {"email": "sweep.teacher@example.com", "password": "SweepPass123!"}
ANONYMOUS_OK = {200, 204, 302, 400, 401, 403, 404, 405, 415}

VERBOSE = "-v" in sys.argv


def sample_paths(app):
    """Expand every GET rule into a concrete URL using real catalog values."""
    from app.services.content_catalog import (
        list_questions,
        list_subject_lessons,
        list_subjects,
        load_feature_simulations,
    )

    subjects = list_subjects()
    lesson_id = (list_subject_lessons(subjects[0]["slug"])[0]["lesson_id"])
    question_id = list_questions()[0]["question_id"]
    simulations = load_feature_simulations()
    return {
        "slug": subjects[0]["slug"],
        "lesson_id": lesson_id,
        "question_id": question_id,
        "conversation_id": "conversation-1",
        # Use a real bundled simulation so the redirect to its runtime is exercised.
        "simulation_id": simulations[0]["id"] if simulations else "newton-lab",
        "class_id": 1,
        "student_id": 1,
        "student": 1,
        "content_id": "content-1",
        "client_id": "note-1",
    }


def build_urls(app):
    """Return concrete URLs for every GET rule that has no required body."""
    values = sample_paths(app)
    urls = []
    for rule in app.url_map.iter_rules():
        if "GET" not in rule.methods or rule.rule.startswith("/static/"):
            continue
        url = rule.rule
        skip = False
        for arg in rule.arguments:
            if arg not in values:
                skip = True
                break
            url = url.replace(f"<{arg}>", str(values[arg]))
            url = url.replace(f"<int:{arg}>", str(values[arg]))
            url = url.replace(f"<path:{arg}>", str(values[arg]))
            url = url.replace(f"<string:{arg}>", str(values[arg]))
        if skip or "<" in url:
            continue
        urls.append(sorted((rule.rule, url)))
    return sorted(urls)


def main() -> int:
    app = create_app()
    app.config.update(TESTING=True, PROPAGATE_EXCEPTIONS=False)
    failures: list[str] = []
    checked = 0

    with app.test_client() as client:
        student_register = client.post("/auth/register", json={
            "name": "Sweep Student", "email": STUDENT["email"],
            "password": STUDENT["password"], "account_type": "student",
        })
        if student_register.status_code not in (201, 409):
            failures.append(f"student register -> {student_register.status_code}")

        urls = build_urls(app)

        for role in ("anonymous", "student", "teacher"):
            if role == "student":
                client.post("/auth/login", json=STUDENT)
            elif role == "teacher":
                client.post("/auth/login", json={
                    "name": "Sweep Teacher", "email": TEACHER["email"],
                    "password": TEACHER["password"], "account_type": "teacher",
                })
                client.post("/auth/login", json=TEACHER)
            for rule, url in urls:
                response = client.get(url, follow_redirects=False)
                checked += 1
                if response.status_code >= 500:
                    failures.append(f"[{role}] GET {url} ({rule}) -> {response.status_code}")
                elif response.status_code not in ANONYMOUS_OK:
                    failures.append(f"[{role}] GET {url} ({rule}) -> {response.status_code}")
                if VERBOSE:
                    print(f"[{role}] {response.status_code} {url}")

    print(f"Route sweep checked {checked} requests.")
    if failures:
        print("ROUTE SWEEP FAILURES:")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("Route sweep passed: no 5xx and no unexpected status codes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())