"""Regression tests for learner foundation (profile/pathway/mastery/adaptive/XP)."""
import os
import tempfile
import unittest
import uuid

DB_PATH = os.path.join(tempfile.gettempdir(), f"learncraft_learn_{os.getpid()}.db")
os.environ["LEARNCRAFT_DB_PATH"] = DB_PATH
os.environ["LEARNCRAFT_SECRET_KEY"] = "learn-test-secret"

from app.database.connection import initialize_database
from app.main import app


def _register(client, role="student"):
    email = f"{role}-{uuid.uuid4().hex}@example.com"
    r = client.post("/auth/register", json={"name": "L", "email": email,
                                            "password": "Password123!",
                                            "account_type": role})
    assert r.status_code == 201, r.get_data(as_text=True)
    return email


class LearnerFoundationTests(unittest.TestCase):
    def setUp(self):
        initialize_database()
        app.config["TESTING"] = True
        self.client = app.test_client()
        _register(self.client)

    def test_profile_roundtrip(self):
        g = self.client.get("/api/v1/profile/learner")
        self.assertEqual(g.status_code, 200)
        p = self.client.put("/api/v1/profile/learner", json={
            "education_level": "college", "pathway": "career",
            "goals": ["AI/ML"], "subjects": ["Python"],
            "daily_target_min": 60, "weekly_target_min": 300})
        self.assertEqual(p.status_code, 200)
        self.assertEqual(p.get_json()["profile"]["pathway"], "career")
        bad = self.client.put("/api/v1/profile/learner", json={"pathway": "nope"})
        self.assertEqual(bad.status_code, 400)

    def test_pathways(self):
        r = self.client.get("/api/v1/pathways")
        self.assertEqual(r.status_code, 200)
        ids = {i["id"] for i in r.get_json()["items"]}
        self.assertTrue({"school", "career", "gate"} <= ids)
        s = self.client.post("/api/v1/pathways/select", json={"pathway": "career"})
        self.assertEqual(s.status_code, 200)
        bad = self.client.post("/api/v1/pathways/select", json={"pathway": "nope"})
        self.assertEqual(bad.status_code, 400)
