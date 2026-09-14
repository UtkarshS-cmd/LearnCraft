import os
import tempfile
import unittest
import uuid

DB_PATH = os.path.join(tempfile.gettempdir(), f"learncraft_teacher_{os.getpid()}.db")
os.environ["LEARNCRAFT_DB_PATH"] = DB_PATH
os.environ["LEARNCRAFT_SECRET_KEY"] = "teacher-test-secret"

from app.core.security import hash_password
from app.database.connection import create_user, get_connection, initialize_database
from app.main import app


class TeacherControlTests(unittest.TestCase):
    def setUp(self):
        initialize_database()
        app.config["TESTING"] = True
        self.teacher = create_user("Teacher One", f"teacher-{uuid.uuid4().hex}@example.com", hash_password("Password123!"), role="TEACHER")
        self.student = create_user("Student One", f"student-{uuid.uuid4().hex}@example.com", hash_password("Password123!"), role="STUDENT")
        self.teacher_client = app.test_client()
        self.student_client = app.test_client()
        self.teacher_client.post("/auth/login", json={"email": self.teacher["email"], "password": "Password123!"})
        self.student_client.post("/auth/login", json={"email": self.student["email"], "password": "Password123!"})

    def test_teacher_can_create_class_observe_event_and_lock_subject(self):
        created = self.teacher_client.post("/api/v1/teacher/classes", json={"name": "Class X A"})
        self.assertEqual(created.status_code, 201)
        class_id = created.get_json()["item"]["id"]
        added = self.teacher_client.post(f"/api/v1/teacher/classes/{class_id}/students", json={"student_id": self.student["id"]})
        self.assertEqual(added.status_code, 201)

        progress = self.student_client.post("/api/v1/progress", json={
            "lesson_id": "cbse-x-2026-27-science-life-processes-photosynthesis",
            "subject_slug": "science", "status": "in_progress", "percent_complete": 30,
        })
        self.assertEqual(progress.status_code, 200)
        dashboard = self.teacher_client.get("/api/v1/teacher/dashboard")
        self.assertEqual(dashboard.status_code, 200)
        payload = dashboard.get_json()
        self.assertEqual(payload["kpis"]["total_students"], 1)
        self.assertTrue(any(event["user_id"] == self.student["id"] for event in payload["events"]))

        locked = self.teacher_client.post("/api/v1/teacher/access", json={
            "scope_type": "CLASS", "scope_id": class_id,
            "resource_type": "subject", "resource_id": "science", "state": "LOCKED",
        })
        self.assertEqual(locked.status_code, 200)
        blocked = self.student_client.get("/subjects/science")
        self.assertEqual(blocked.status_code, 403)

        audit = get_connection().execute("SELECT action, new_state FROM teacher_audit_logs ORDER BY id DESC LIMIT 1").fetchone()
        self.assertEqual(dict(audit), {"action": "ACCESS_PERMISSION_CHANGED", "new_state": "LOCKED"})

        assignment = self.teacher_client.post("/api/v1/teacher/assignments", json={
            "class_id": class_id, "resource_type": "simulation", "resource_id": "newton-lab",
            "title": "Newton Lab", "due_at": "2099-01-01 10:00:00",
        })
        self.assertEqual(assignment.status_code, 201)
        self.assertEqual(len(self.student_client.get("/api/v1/assignments").get_json()["items"]), 1)

        announcement = self.teacher_client.post("/api/v1/teacher/announcements", json={
            "class_id": class_id, "message": "Complete the Newton Lab before tomorrow."
        })
        self.assertEqual(announcement.status_code, 201)
        self.assertEqual(len(self.student_client.get("/api/v1/announcements").get_json()["items"]), 1)
        analytics = self.teacher_client.get("/api/v1/teacher/analytics")
        self.assertEqual(analytics.status_code, 200)
        self.assertIn("leaderboard", analytics.get_json())

        assigned_only = self.teacher_client.post("/api/v1/teacher/access", json={
            "scope_type": "CLASS", "scope_id": class_id,
            "resource_type": "simulation", "resource_id": "newton-lab", "state": "ASSIGNED_ONLY",
        })
        self.assertEqual(assigned_only.status_code, 200)
        self.assertEqual(self.student_client.get("/student/simulation/newton-lab").status_code, 302)

    def test_student_cannot_access_teacher_api_or_page(self):
        self.assertEqual(self.student_client.get("/teacher").status_code, 403)
        self.assertEqual(self.student_client.get("/api/v1/teacher/dashboard").status_code, 403)


if __name__ == "__main__":
    unittest.main()
