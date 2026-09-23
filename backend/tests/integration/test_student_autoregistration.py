import os
import tempfile
import unittest
import uuid

DB_PATH = os.path.join(tempfile.gettempdir(), f"learncraft_autoreg_{os.getpid()}.db")
os.environ["LEARNCRAFT_DB_PATH"] = DB_PATH
os.environ["LEARNCRAFT_SECRET_KEY"] = "autoreg-test-secret"

from app.core.security import hash_password
from app.database.connection import create_user, get_connection, initialize_database
from app.main import app


class StudentAutoRegistrationTests(unittest.TestCase):
    def setUp(self):
        initialize_database()
        app.config["TESTING"] = True
        suffix = uuid.uuid4().hex[:8]
        self.teacher = create_user(f"Teacher {suffix}", f"teacher-{suffix}@example.com", hash_password("Password123!"), role="TEACHER")
        self.teacher_client = app.test_client()
        self.teacher_client.post("/auth/login", json={"email": self.teacher["email"], "password": "Password123!"})

    def _create_class(self, name="Class X A"):
        created = self.teacher_client.post("/api/v1/teacher/classes", json={"name": name})
        self.assertEqual(created.status_code, 201)
        return created.get_json()["item"]["id"]

    def _register_student(self, prefix="auto"):
        email = f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"
        client = app.test_client()
        response = client.post("/auth/register", json={
            "name": f"{prefix} Student", "email": email, "password": "Password123!",
        })
        self.assertEqual(response.status_code, 201)
        return email, client

    def _approve_student_into_class(self, class_id, email):
        pending = self.teacher_client.get("/api/v1/teacher/join-requests").get_json()["items"]
        mine = [r for r in pending if r["email"] == email]
        self.assertEqual(len(mine), 1)
        self.assertEqual(mine[0]["class_id"], class_id)
        approved = self.teacher_client.post(f"/api/v1/teacher/join-requests/{mine[0]['id']}/approve", json={})
        self.assertEqual(approved.status_code, 200)
        members = self.teacher_client.get(f"/api/v1/teacher/classes/{class_id}/students").get_json()["items"]
        self.assertTrue(any(m["email"] == email for m in members))
        still_pending = [r for r in self.teacher_client.get("/api/v1/teacher/join-requests").get_json()["items"] if r["email"] == email]
        self.assertEqual(still_pending, [])

    def test_corrupt_password_hash_logs_in_with_clean_401(self):
        # Old builds wrote placeholder hashes (e.g. 'x'); these must not crash
        # the login route with a 500 and must answer with invalid credentials.
        email = f"broken-{uuid.uuid4().hex}@example.com"
        create_user("Broken User", email, "x", role="STUDENT")
        response = app.test_client().post("/auth/login", json={"email": email, "password": "Whatever@1"})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["code"], "INVALID_CREDENTIALS")

    def test_student_registration_creates_join_request_and_approval_connects_class(self):
        class_id = self._create_class()
        email, student_client = self._register_student()

        pending = self.teacher_client.get("/api/v1/teacher/join-requests").get_json()["items"]
        mine = [r for r in pending if r["email"] == email]
        self.assertEqual(len(mine), 1)
        self.assertEqual(mine[0]["class_id"], class_id)

        approved = self.teacher_client.post(f"/api/v1/teacher/join-requests/{mine[0]['id']}/approve", json={})
        self.assertEqual(approved.status_code, 200)

        members = self.teacher_client.get(f"/api/v1/teacher/classes/{class_id}/students").get_json()["items"]
        self.assertTrue(any(m["email"] == email for m in members))

        # Already-decided requests disappear from the pending queue.
        still_pending = [r for r in self.teacher_client.get("/api/v1/teacher/join-requests").get_json()["items"] if r["email"] == email]
        self.assertEqual(still_pending, [])

    def test_approved_student_receives_announcements_and_assignments(self):
        class_id = self._create_class()
        email, student_client = self._register_student()
        self._approve_student_into_class(class_id, email)

        announcement = self.teacher_client.post("/api/v1/teacher/announcements", json={
            "class_id": class_id, "message": "AutoReg notice for class.",
        })
        self.assertEqual(announcement.status_code, 201)
        assignment = self.teacher_client.post("/api/v1/teacher/assignments", json={
            "class_id": class_id, "resource_type": "lesson", "resource_id": "photo-lab",
            "title": "AutoReg Homework", "due_at": "2099-06-01 10:00:00",
        })
        self.assertEqual(assignment.status_code, 201)

        assignments = student_client.get("/api/v1/assignments").get_json()["items"]
        self.assertTrue(any(item["title"] == "AutoReg Homework" for item in assignments))
        announcements = student_client.get("/api/v1/announcements").get_json()["items"]
        self.assertTrue(any(item["message"] == "AutoReg notice for class." for item in announcements))

        home = student_client.get("/home")
        body = home.get_data(as_text=True)
        self.assertIn("AutoReg Homework", body)
        self.assertIn("AutoReg notice for class.", body)

    def test_rejected_join_request_does_not_add_student(self):
        class_id = self._create_class()
        email, _ = self._register_student("reject")
        pending = self.teacher_client.get("/api/v1/teacher/join-requests").get_json()["items"]
        request_id = next(r["id"] for r in pending if r["email"] == email)
        rejected = self.teacher_client.post(f"/api/v1/teacher/join-requests/{request_id}/reject", json={})
        self.assertEqual(rejected.status_code, 200)
        members = self.teacher_client.get(f"/api/v1/teacher/classes/{class_id}/students").get_json()["items"]
        self.assertFalse(any(m["email"] == email for m in members))

    def test_dashboard_kpi_counts_pending_requests(self):
        self._create_class()
        self._register_student("kpi")
        kpis = self.teacher_client.get("/api/v1/teacher/dashboard").get_json()["kpis"]
        self.assertGreaterEqual(kpis.get("pending_requests", 0), 1)

    def test_add_student_by_email_without_numeric_id(self):
        class_id = self._create_class()
        email = f"byemail-{uuid.uuid4().hex[:8]}@example.com"
        create_user("By Email Student", email, hash_password("Password123!"), role="STUDENT")
        response = self.teacher_client.post(f"/api/v1/teacher/classes/{class_id}/students", json={"email": email})
        self.assertEqual(response.status_code, 201)
        members = self.teacher_client.get(f"/api/v1/teacher/classes/{class_id}/students").get_json()["items"]
        self.assertTrue(any(m["email"] == email for m in members))

    def test_add_student_by_unknown_email_returns_clear_error(self):
        class_id = self._create_class()
        response = self.teacher_client.post(f"/api/v1/teacher/classes/{class_id}/students", json={"email": "nobody@example.com"})
        self.assertEqual(response.status_code, 404)
        self.assertIn("No student account found", response.get_json()["message"])

    def test_join_requests_endpoint_requires_teacher(self):
        response = app.test_client().get("/api/v1/teacher/join-requests")
        self.assertEqual(response.status_code, 403)

    def tearDown(self):
        conn = get_connection()
        conn.execute("DELETE FROM student_join_requests WHERE teacher_id = ?", (self.teacher["id"],))
        conn.execute("DELETE FROM teacher_classes WHERE teacher_id = ?", (self.teacher["id"],))
        conn.commit()
        conn.close()


if __name__ == "__main__":
    unittest.main()
