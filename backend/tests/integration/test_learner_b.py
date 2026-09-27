"""Mastery/adaptive/XP regression tests (part 2)."""
import os
import tempfile
import unittest
import uuid

DB_PATH = os.path.join(tempfile.gettempdir(), f"learncraft_learn2_{os.getpid()}.db")
os.environ["LEARNCRAFT_DB_PATH"] = DB_PATH
os.environ["LEARNCRAFT_SECRET_KEY"] = "learn2-test-secret"

from app.database.connection import initialize_database
from app.main import app
from app.services.content_catalog import import_packages, load_packages
from app.services.mastery import record_attempt


class MasteryTests(unittest.TestCase):
    def setUp(self):
        initialize_database()
        import_packages(load_packages())
        app.config["TESTING"] = True
        self.client = app.test_client()
        email = f"s-{uuid.uuid4().hex}@example.com"
        self.client.post("/auth/register", json={"name": "M", "email": email,
                                                 "password": "Password123!"})

    def test_mastery_math(self):
        from app.services.mastery_a import score_row
        m, parts = score_row({"attempts": 10, "correct": 9, "streak": 5,
                              "best_streak": 5, "difficulty_sum": 10.0,
                              "last_correct": 1, "last_attempt_at": None})
        self.assertGreater(m, 60)
        m2, _ = score_row({"attempts": 5, "correct": 1, "streak": 0,
                           "best_streak": 1, "difficulty_sum": 5.0,
                           "last_correct": 0, "last_attempt_at": None})
        self.assertLess(m2, 50)

    def test_quiz_updates_mastery_and_xp(self):
        from app.services.content_catalog import list_questions
        q = list_questions()[0]
        opts = [o for o in q["options"] if o.get("is_correct")]
        ans = opts[0]["option_id"] if opts else q.get("answer")
        r = self.client.post("/api/v1/quizzes/check",
                             json={"question_id": q["question_id"], "answer": ans})
        self.assertEqual(r.status_code, 200)
        m = self.client.get("/api/v1/mastery")
        self.assertEqual(m.status_code, 200)
        self.assertTrue(m.get_json()["items"])
        x = self.client.get("/api/v1/gamification")
        self.assertGreaterEqual(x.get_json()["xp"], 5)
        n = self.client.get("/api/v1/learning/next")
        self.assertEqual(n.status_code, 200)
        self.assertIn("reason", n.get_json()["next"])
