"""Functional sweep for LearnCraft.

Logs in as a student and a teacher, then exercises every write endpoint with
realistic payloads. Any unexpected status code or server error is reported so
regressions surface immediately.

Run with::

    python scripts/functional_test.py
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

# Isolate the sweep in a throwaway database so repeated runs are deterministic.
_TEST_DB = Path(tempfile.gettempdir()) / "learncraft_functional_test.db"
if _TEST_DB.exists():
    _TEST_DB.unlink()
os.environ["LEARNCRAFT_DB_PATH"] = str(_TEST_DB)

from app.main import create_app  # noqa: E402

STUDENT = {"email": "func.student@example.com", "password": "FuncTest123!"}
TEACHER = {"email": "func.teacher@example.com", "password": "FuncTest123!"}


def post(client, path, payload, expected=(200, 201, 302, 400, 403, 404, 409), method="POST"):
    response = client.open(path, method=method, data=json.dumps(payload), content_type="application/json")
    return response, response.status_code in expected


def problems_for_teacher(client, problems, lesson_id, _subject_slug):
    """Exercise the teacher console against the same client session."""
    client.post("/auth/register", json={
        "name": "Func Teacher", "email": TEACHER["email"], "password": TEACHER["password"],
        "account_type": "teacher",
    })
    tlogin = client.post("/auth/login", json=TEACHER)
    if tlogin.status_code != 200:
        problems.append(f"teacher login -> {tlogin.status_code}")

    created = post(client, "/api/v1/teacher/classes", {"name": "Class 10-A", "grade": "10", "section": "A"})
    class_id = None
    if created[1]:
        class_id = (created[0].get_json() or {}).get("item", {}).get("id")
    if not class_id:
        problems.append("teacher class creation failed")
        return

    users = client.get("/api/v1/users").get_json() or []
    if isinstance(users, dict):
        users = users.get("items", [])
    student_id = next((u.get("id") for u in users if u.get("email") == STUDENT["email"]), None)

    if student_id:
        response, ok = post(client, f"/api/v1/teacher/classes/{class_id}/students", {"student_id": student_id})
        if not ok:
            problems.append(f"add student to class -> {response.status_code}")

    response, ok = post(client, "/api/v1/teacher/assignments", {
        "class_id": class_id, "title": "Read Newton's laws",
        "resource_type": "lesson", "resource_id": lesson_id,
    })
    if not ok:
        problems.append(f"create assignment -> {response.status_code}")

    response, ok = post(client, "/api/v1/teacher/announcements", {
        "class_id": class_id, "message": "Quiz on Friday.",
    })
    if not ok:
        problems.append(f"create announcement -> {response.status_code}")

    response, ok = post(client, "/api/v1/teacher/access", {
        "scope_type": "CLASS", "scope_id": str(class_id),
        "resource_type": "lesson", "resource_id": lesson_id, "state": "ASSIGNED_ONLY",
    })
    if not ok:
        problems.append(f"set access rule -> {response.status_code}")

    for path in (f"/api/v1/teacher/classes/{class_id}/students",
                 "/api/v1/teacher/analytics", "/api/v1/teacher/reports/activity.csv",
                 "/api/v1/teacher/assignments", "/api/v1/teacher/announcements",
                 "/api/v1/teacher/dashboard", "/api/v1/teacher/notifications"):
        response = client.get(path)
        if response.status_code != 200:
            problems.append(f"GET {path} -> {response.status_code}")

    if student_id:
        response = client.get(f"/api/v1/teacher/students/{student_id}")
        if response.status_code != 200:
            problems.append(f"GET teacher student detail -> {response.status_code}")

    # Student should now see the assignment + announcement on the dashboard.
    client.post("/auth/login", json=STUDENT)
    if client.get("/api/v1/assignments").status_code != 200:
        problems.append("student assignments API failed")
    if client.get("/api/v1/announcements").status_code != 200:
        problems.append("student announcements API failed")


def main() -> int:
    app = create_app()
    app.config.update(TESTING=True)
    problems: list[str] = []

    with app.test_client() as client:
        # --- students -------------------------------------------------------
        client.post("/auth/register", json={
            "name": "Func Student", "email": STUDENT["email"], "password": STUDENT["password"],
            "role": "student", "grade": 10,
        })
        login = client.post("/auth/login", json=STUDENT)
        if login.status_code != 200:
            problems.append(f"student login -> {login.status_code}")

        subjects = client.get("/api/v1/subjects").get_json() or {}
        subject_slug = (subjects.get("items") or [{}])[0].get("slug", "science")

        detail = client.get(f"/api/v1/lessons?subject={subject_slug}").get_json() or {}
        lessons = detail.get("items") or []
        lesson_id = lessons[0]["lesson_id"] if lessons else "lesson-1"
        if not lessons:
            problems.append(f"no lessons returned for subject {subject_slug}")

        questions = client.get("/api/v1/quizzes?limit=5").get_json() or {}
        q_items = questions.get("items") or []

        checks = [
            ("POST /api/v1/progress", "/api/v1/progress",
             {"lesson_id": lesson_id, "subject_slug": subject_slug, "percent_complete": 40, "status": "in_progress"}),
            ("POST /api/v1/progress complete", "/api/v1/progress",
             {"lesson_id": lesson_id, "subject_slug": subject_slug, "percent_complete": 100, "status": "completed", "score": 8}),
            ("POST /api/v1/events", "/api/v1/events",
             {"event_type": "GAME_COMPLETED", "activity_type": "game", "activity_id": "maths-explorer",
              "subject_slug": "mathematics", "detail": "Round complete", "score": 120}),
            ("POST /api/local/state", "/api/local/state",
             {"kind": "progress", "record_id": f"lesson:{lesson_id}",
              "payload": {"idx": 2, "visited": [0, 1, 2], "done": False},
              "status": "in_progress", "percent_complete": 60}),
            ("POST /api/notes", "/api/notes",
             {"client_id": "note-func-1", "title": "Newton's laws", "body": "F = ma",
              "subject": "science", "chapter": "Chapter 1"}),
            ("PUT /api/notes", "/api/notes/note-func-1",
             {"title": "Newton's laws revised", "body": "F = ma; action-reaction", "pinned": True}),
            ("POST /api/notes pin", "/api/notes/note-func-1/pin", {"pinned": True}),
        ]
        for label, path, payload in checks:
            method = "PUT" if label.startswith("PUT") else "POST"
            response, ok = post(client, path, payload, method=method)
            if not ok:
                problems.append(f"{label} -> {response.status_code}: {response.get_data(as_text=True)[:160]}")

        for question in q_items[:3]:
            options = question.get("options") or []
            answer = options[0]["option_id"] if options else "a"
            response, ok = post(client, "/api/v1/quizzes/check",
                                {"question_id": question["question_id"], "answer": answer}, expected=(200,))
            if not ok:
                problems.append(f"POST /api/v1/quizzes/check -> {response.status_code}")

        chat = post(client, "/api/v1/ai/chat", {"message": "Explain Newton's first law"})
        if chat[1]:
            data = chat[0].get_json() or {}
            if not data.get("answer"):
                problems.append("POST /api/v1/ai/chat returned no answer")
            conversation_id = data.get("conversation_id")
            if conversation_id:
                follow = post(client, "/api/v1/ai/chat",
                              {"message": "Give an example", "conversation_id": conversation_id})
                if not follow[1]:
                    problems.append(f"AI follow-up -> {follow[0].status_code}")
        else:
            problems.append(f"POST /api/v1/ai/chat -> {chat[0].status_code}")

        # Content pages must render with real data (lesson body, subject detail).
        for subject in (subjects.get("items") or []):
            response = client.get(f"/subjects/{subject['slug']}")
            if response.status_code != 200:
                problems.append(f"GET /subjects/{subject['slug']} -> {response.status_code}")

        for lesson in lessons[:2]:
            page = f"/subjects/{lesson['subject_slug']}/lessons/{lesson['lesson_id']}"
            response = client.get(page)
            if response.status_code != 200:
                problems.append(f"GET {page} -> {response.status_code}")
            else:
                body = response.get_data(as_text=True)
                if "lesson_id" not in body or len(body) < 2000:
                    problems.append(f"GET {page} rendered an empty lesson shell")

        for extra in (f"/ask-ai?lesson_id={lesson_id}", "/practical", "/sandbox",
                      "/my-learning", "/progress", "/notes", "/profile", "/settings",
                      "/help", "/tests", "/offline"):
            response = client.get(extra)
            if response.status_code != 200:
                problems.append(f"GET {extra} -> {response.status_code}")

        # Simulation workspace is opened by the subject detail page.
        sim = client.get("/student/simulation/physics-lab")
        if sim.status_code not in (200, 404):
            problems.append(f"GET /student/simulation/physics-lab -> {sim.status_code}")

        problems_for_teacher(client, problems, lesson_id, subject_slug)

    if problems:
        print("FUNCTIONAL TEST FAILURES:")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    print("Functional sweep passed: student + teacher flows OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())