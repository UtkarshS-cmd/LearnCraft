"""Regression tests for the 2026-09-24 security audit fixes.

Covers: same-origin (CSRF) guard on writes, POST-only /logout, answer-free
question feed, per-user sync queue ownership, and the service worker's
private-cache purge on sign-out.
"""

import json
import os
import tempfile
import unittest

DB_PATH = os.path.join(tempfile.gettempdir(), f"learncraft_security_{os.getpid()}.db")
os.environ["LEARNCRAFT_DB_PATH"] = DB_PATH
os.environ["LEARNCRAFT_SECRET_KEY"] = "security-test-secret"

from app.api.v1.subjects import _public_question
from app.database.connection import get_connection, initialize_database
from app.main import app
from app.services.content_catalog import import_packages, load_packages

STUDENT_PASSWORD = "Password123!"


def register_and_login(client, email):
    """Register (idempotently) then log in; mirrors the offline API tests."""
    client.post("/auth/register", json={"name": "Security Tester", "email": email,
                                        "password": STUDENT_PASSWORD})
    return client.post("/auth/login", json={"email": email, "password": STUDENT_PASSWORD})


class SecurityAuditTests(unittest.TestCase):
    def setUp(self):
        initialize_database()
        import_packages(load_packages())
        app.config["TESTING"] = True
        self.client = app.test_client()
        register_and_login(self.client, "security_student@example.com")

    # --- CSRF same-origin guard -------------------------------------------------

    def test_cross_origin_writes_are_rejected(self):
        payload = {"kind": "progress", "record_id": "lesson:audit-csrf", "payload": {"step": 1}}

        evil_origin = self.client.post("/api/local/state", json=payload,
                                       headers={"Origin": "http://evil.example"})
        self.assertEqual(evil_origin.status_code, 403)
        self.assertEqual(evil_origin.get_json()["code"], "CSRF_BLOCKED")

        evil_referer = self.client.post("/api/local/state", json=payload,
                                        headers={"Referer": "http://evil.example/page"})
        self.assertEqual(evil_referer.status_code, 403)

        same_origin = self.client.post("/api/local/state", json=payload,
                                       headers={"Origin": "http://localhost"})
        self.assertEqual(same_origin.status_code, 200)

        # Reads are safe methods and stay available from anywhere.
        read = self.client.get("/api/sync/queue", headers={"Origin": "http://evil.example"})
        self.assertEqual(read.status_code, 200)

    def test_logout_is_post_only_and_clears_the_session(self):
        self.assertEqual(self.client.get("/logout").status_code, 405)

        response = self.client.post("/logout")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

        # Session gone: protected pages redirect back to the login page.
        self.assertEqual(self.client.get("/profile").status_code, 302)

    # --- Question feed never leaks solution fields ------------------------------

    def test_question_feed_strips_solution_fields(self):
        response = self.client.get("/api/v1/questions?subject=science")
        self.assertEqual(response.status_code, 200)
        items = response.get_json()["items"]
        self.assertTrue(items, "seeded question feed is empty")

        checked_options = 0
        for item in items:
            for key in ("answer", "explanation", "correct_answer", "correct_option_id", "is_correct"):
                self.assertNotIn(key, item)
            self.assertTrue(item["prompt"])
            for option in item["options"]:
                self.assertNotIn("is_correct", option)
                self.assertIn("option_id", option)
                self.assertIn("option_text", option)
                checked_options += 1
            # Non-secret provenance must survive for offline source cards.
            self.assertIn("source_reference", item)
        self.assertGreater(checked_options, 0, "no MCQ options found to validate stripping")

    def test_public_question_helper_strips_synthetic_solution(self):
        raw = {
            "question_id": "syn-1",
            "prompt": "What is the unit of force?",
            "answer": "newton",
            "explanation": "One newton accelerates 1 kg by 1 m/s^2.",
            "source_reference": "textbook p.1",
            "options": [
                {"option_id": "A", "option_text": "joule", "is_correct": 0},
                {"option_id": "B", "option_text": "newton", "is_correct": 1},
            ],
        }
        clean = _public_question(raw)
        self.assertEqual(clean["question_id"], "syn-1")
        self.assertEqual(clean["source_reference"], "textbook p.1")
        self.assertEqual(clean["options"][1]["option_text"], "newton")
        for forbidden in ("answer", "explanation", "is_correct"):
            self.assertNotIn(forbidden, clean)
        for option in clean["options"]:
            self.assertNotIn("is_correct", option)

    # --- Sync queue ownership ---------------------------------------------------

    def test_sync_queue_is_scoped_to_the_session_user(self):
        event_id = "evt_security_scope_1"
        created = self.client.post("/api/local/state", json={
            "kind": "submission", "record_id": "assignment:audit-scope-1",
            "payload": {"answers": {"q1": "force"}}, "status": "SUBMITTED",
            "event_id": event_id,
        })
        self.assertEqual(created.status_code, 200)

        mine = [item["event_id"] for item in self.client.get("/api/sync/queue").get_json()]
        self.assertIn(event_id, mine)

        self.client.post("/logout")
        register_and_login(self.client, "security_other@example.com")
        other = [item["event_id"] for item in self.client.get("/api/sync/queue").get_json()]
        self.assertNotIn(event_id, other)

    def test_queued_events_record_the_session_owner(self):
        me = self.client.get("/auth/me").get_json()["user"]["id"]
        self.client.post("/api/local/state", json={
            "kind": "submission", "record_id": "assignment:audit-identity-1",
            "payload": {"user_id": 999999, "answers": {"q1": "mass"}}, "status": "SUBMITTED",
            "event_id": "evt_security_identity_1",
        })

        connection = get_connection()
        try:
            row = connection.execute(
                "SELECT user_id, payload_json FROM sync_queue WHERE event_id = ?",
                ("evt_security_identity_1",),
            ).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["user_id"], me)
            # A spoofed client-side user_id can never win over the session identity.
            self.assertEqual(json.loads(row["payload_json"])["user_id"], me)

            submission = connection.execute(
                "SELECT payload_json FROM local_submissions WHERE submission_id = ?",
                ("assignment:audit-identity-1",),
            ).fetchone()
            self.assertIsNotNone(submission)
            self.assertEqual(json.loads(submission["payload_json"])["user_id"], me)
        finally:
            connection.close()

    # --- Deployment / service worker hygiene ------------------------------------

    def test_service_worker_purges_private_pages_on_logout(self):
        data = self.client.get("/service-worker.js").data.decode()
        self.assertIn("learncraft-shell-v4", data)
        self.assertIn("learncraft-private-v1", data)
        self.assertIn("caches.open(PRIVATE_CACHE)", data)
        self.assertIn("caches.delete(PRIVATE_CACHE)", data)
        self.assertIn("/auth/logout", data)

    def test_werkzeug_debugger_is_opt_in(self):
        import inspect
        import app.main as main_module
        source = inspect.getsource(main_module)
        self.assertIn('os.environ.get("FLASK_DEBUG"', source)
        self.assertNotIn("debug=True", source)


if __name__ == "__main__":
    unittest.main()
