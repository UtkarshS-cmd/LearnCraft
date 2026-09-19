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
        game_event = self.student_client.post("/api/v1/events", json={
            "event_type": "GAME_COMPLETED", "activity_type": "game", "activity_id": "newton-lab-force",
            "subject_slug": "science", "detail": "Newton Lab completed", "score": 80,
        })
        self.assertEqual(game_event.status_code, 201)
        dashboard = self.teacher_client.get("/api/v1/teacher/dashboard")
        self.assertEqual(dashboard.status_code, 200)
        payload = dashboard.get_json()
        self.assertEqual(payload["kpis"]["total_students"], 1)
        self.assertTrue(any(event["user_id"] == self.student["id"] for event in payload["events"]))
        profile = self.teacher_client.get(f"/api/v1/teacher/students/{self.student['id']}")
        self.assertEqual(profile.status_code, 200)
        self.assertEqual(profile.get_json()["summary"]["games_completed"], 1)

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
        report = self.teacher_client.get("/api/v1/teacher/reports/activity.csv")
        self.assertEqual(report.status_code, 200)
        self.assertIn("GAME_COMPLETED", report.get_data(as_text=True))
        notifications = self.teacher_client.get("/api/v1/teacher/notifications")
        self.assertTrue(notifications.get_json()["items"])
        marked = self.teacher_client.post("/api/v1/teacher/notifications/read", json={})
        self.assertEqual(marked.status_code, 200)

        assigned_only = self.teacher_client.post("/api/v1/teacher/access", json={
            "scope_type": "CLASS", "scope_id": class_id,
            "resource_type": "simulation", "resource_id": "newton-lab", "state": "ASSIGNED_ONLY",
        })
        self.assertEqual(assigned_only.status_code, 200)
        self.assertEqual(self.student_client.get("/student/simulation/newton-lab").status_code, 302)

    def test_student_cannot_access_teacher_api_or_page(self):
        self.assertEqual(self.student_client.get("/teacher").status_code, 403)
        self.assertEqual(self.student_client.get("/api/v1/teacher/dashboard").status_code, 403)
        self.assertEqual(self.student_client.delete("/api/v1/teacher/classes/1").status_code, 403)

    def test_remove_member_and_delete_class(self):
        created = self.teacher_client.post("/api/v1/teacher/classes", json={"name": "Temp Class"})
        class_id = created.get_json()["item"]["id"]
        self.assertEqual(
            self.teacher_client.post(f"/api/v1/teacher/classes/{class_id}/students", json={"student_id": self.student["id"]}).status_code,
            201,
        )
        self.assertEqual(self.teacher_client.get("/api/v1/teacher/dashboard").get_json()["kpis"]["total_students"], 1)

        removed = self.teacher_client.delete(f"/api/v1/teacher/classes/{class_id}/students/{self.student['id']}")
        self.assertEqual(removed.status_code, 200)
        self.assertEqual(self.teacher_client.get("/api/v1/teacher/dashboard").get_json()["kpis"]["total_students"], 0)
        self.assertEqual(
            self.teacher_client.delete(f"/api/v1/teacher/classes/{class_id}/students/{self.student['id']}").status_code, 404
        )

        deleted = self.teacher_client.delete(f"/api/v1/teacher/classes/{class_id}")
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(self.teacher_client.get("/api/v1/teacher/classes").get_json()["items"], [])
        self.assertEqual(self.teacher_client.delete(f"/api/v1/teacher/classes/{class_id}").status_code, 404)
        self.assertEqual(self.student_client.delete(f"/api/v1/teacher/classes/{class_id}").status_code, 403)

    def test_cross_device_assignment_reaches_student_home_and_lists(self):
        created = self.teacher_client.post("/api/v1/teacher/classes", json={"name": "Class X B"})
        self.assertEqual(created.status_code, 201)
        class_id = created.get_json()["item"]["id"]
        added = self.teacher_client.post(f"/api/v1/teacher/classes/{class_id}/students", json={"student_id": self.student["id"]})
        self.assertEqual(added.status_code, 201)

        assignment = self.teacher_client.post("/api/v1/teacher/assignments", json={
            "class_id": class_id, "resource_type": "lesson", "resource_id": "photo-lab",
            "title": "XDevice Homework", "due_at": "2099-06-01 10:00:00",
        })
        self.assertEqual(assignment.status_code, 201)
        announcement = self.teacher_client.post("/api/v1/teacher/announcements", json={
            "class_id": class_id, "message": "XDevice notice for class."
        })
        self.assertEqual(announcement.status_code, 201)

        sent = self.teacher_client.get("/api/v1/teacher/assignments")
        self.assertEqual(sent.status_code, 200)
        self.assertTrue(any(item["title"] == "XDevice Homework" for item in sent.get_json()["items"]))
        sent_notes = self.teacher_client.get("/api/v1/teacher/announcements")
        self.assertEqual(sent_notes.status_code, 200)
        self.assertTrue(any(item["message"] == "XDevice notice for class." for item in sent_notes.get_json()["items"]))
        self.assertEqual(self.student_client.get("/api/v1/teacher/assignments").status_code, 403)

        home = self.student_client.get("/home")
        self.assertEqual(home.status_code, 200)
        self.assertIn("XDevice Homework", home.get_data(as_text=True))
        self.assertIn("XDevice notice for class.", home.get_data(as_text=True))
        self.assertIn('id="notifBell"', home.get_data(as_text=True))
        self.assertIn('id="todayWorkGrid"', home.get_data(as_text=True))
        self.assertIn('refreshTodayWork', home.get_data(as_text=True))

        page = self.student_client.get("/assignments")
        self.assertEqual(page.status_code, 200)
        body = page.get_data(as_text=True)
        self.assertIn("from-teacher", body)
        self.assertIn("XDevice Homework", body)
        self.assertIn('id="liveAssignList"', body)
        self.assertIn('refreshFromTeacher', body)

        preview = self.teacher_client.get("/subjects")
        self.assertIn("Back to Teacher Control Center", preview.get_data(as_text=True))
        self.assertNotIn('id="notifBell"', preview.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
