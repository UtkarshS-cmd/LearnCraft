"""Teacher product layer: early warning, class pulse, assignment intelligence.

Uses a REAL teacher/student relationship (join request -> approval -> class
assignment -> submission) so every signal and metric is backed by persisted
data, and verifies that one teacher can never read another teacher's students.
"""
import os
import tempfile
import unittest
import uuid

DB_PATH = os.path.join(tempfile.gettempdir(), f"learncraft_teacher_ops_{os.getpid()}.db")
os.environ["LEARNCRAFT_DB_PATH"] = DB_PATH
os.environ["LEARNCRAFT_SECRET_KEY"] = "teacher-ops-secret"

from app.database.connection import initialize_database, _transaction
from app.main import app
from app.services.content_catalog import import_packages, load_packages

CONCEPT = "cbse-x-2026-27-maths-real-numbers-prime-factorisation"


def _account(prefix, role):
    client = app.test_client()
    email = f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"
    response = client.post("/auth/register", json={
        "name": f"{prefix} person", "email": email, "password": "Password123!",
        "account_type": role})
    assert response.status_code == 201, response.get_data(as_text=True)
    return client, int(client.get("/auth/me").get_json()["user"]["id"])


def _seed_activity(user_id, count, days_ago_start=20, step=3):
    """Insert real activity events in the past so decay windows are meaningful."""
    from datetime import datetime, timedelta, timezone

    def work(connection):
        for index in range(count):
            when = datetime.now(timezone.utc) - timedelta(days=days_ago_start - index * step)
            connection.execute(
                "INSERT INTO activity_events (event_id, user_id, event_type, detail, score) "
                "VALUES (?, ?, 'QUIZ_SUBMITTED', ?, ?)",
                (f"seed-{user_id}-{index}", int(user_id), f"seeded {index}", 40 + index * 5))
            connection.execute("UPDATE activity_events SET created_at = ? WHERE event_id = ?",
                               (when.strftime("%Y-%m-%d %H:%M:%S"), f"seed-{user_id}-{index}"))
    _transaction(work)


def _seed_attempts(user_id, concept, correct, incorrect):
    from app.services.question_log import record_attempt

    for index in range(correct):
        record_attempt(user_id, f"ok-{user_id}-{index}", concept, "mathematics", "MEDIUM", True)
    for index in range(incorrect):
        record_attempt(user_id, f"no-{user_id}-{index}", concept, "mathematics", "MEDIUM", False)


class TeacherOpsTests(unittest.TestCase):
    def setUp(self):
        initialize_database()
        import_packages(load_packages())
        app.config["TESTING"] = True
        self.teacher, self.teacher_id = _account("ops-teacher", "teacher")
        self.student, self.student_id = _account("ops-student", "student")
        self.class_id = self.teacher.post(
            "/api/v1/teacher/classes", json={"name": "Class X A"}).get_json()["item"]["id"]
        pending = self.teacher.get("/api/v1/teacher/join-requests").get_json()["items"]
        mine = [r for r in pending if r["student_id"] == self.student_id]
        self.assertTrue(mine, "student must reach the approval queue")
        self.teacher.post(f"/api/v1/teacher/join-requests/{mine[0]['id']}/approve",
                          json={"class_id": self.class_id})
# ------------------------------------------------------------------
    # Early warning
    # ------------------------------------------------------------------
    def test_signals_expose_neutral_status_with_evidence(self):
        _seed_attempts(self.student_id, CONCEPT, 1, 4)
        _seed_activity(self.student_id, 6)
        report = self.teacher.get(f"/api/v1/teacher/students/{self.student_id}/signals")
        self.assertEqual(report.status_code, 200)
        payload = report.get_json()
        self.assertIn(payload["status"], {"NEEDS_ATTENTION", "FALLING_BEHIND", "STALLED",
                                         "IMPROVING", "STRONG_PROGRESS"})
        self.assertTrue(payload["signals"], "a struggling learner must produce a signal")
        for signal in payload["signals"]:
            self.assertTrue(signal["evidence"], "every signal needs evidence")
            self.assertTrue(signal["source"], "every signal needs a data source")

    def test_signals_use_neutral_wording(self):
        """No judgemental labels may appear anywhere in the payload."""
        _seed_attempts(self.student_id, CONCEPT, 0, 5)
        body = self.teacher.get(
            f"/api/v1/teacher/students/{self.student_id}/signals").get_data(as_text=True).lower()
        for banned in ("lazy", "bad student", "weak student", "undisciplined", "careless"):
            self.assertNotIn(banned, body)

    def test_signals_for_all_students(self):
        listing = self.teacher.get("/api/v1/teacher/signals").get_json()
        self.assertTrue(listing["success"])
        self.assertTrue(any(item["student"]["id"] == self.student_id
                            for item in listing["items"]))

    def test_teacher_cannot_read_unrelated_student_signals(self):
        _outsider, outsider_id = _account("outsider", "student")
        response = self.teacher.get(f"/api/v1/teacher/students/{outsider_id}/signals")
        self.assertEqual(response.status_code, 403)

    def test_student_cannot_access_teacher_data(self):
        for path in ("/api/v1/teacher/signals", "/api/v1/teacher/pulse"):
            self.assertEqual(self.student.get(path).status_code, 403)
            self.assertEqual(app.test_client().get(path).status_code, 403)

    # ------------------------------------------------------------------
    # Class pulse
    # ------------------------------------------------------------------
    def test_pulse_metrics_all_carry_a_source_and_drilldown(self):
        _seed_attempts(self.student_id, CONCEPT, 2, 2)
        _seed_activity(self.student_id, 5)
        pulse = self.teacher.get("/api/v1/teacher/pulse").get_json()
        self.assertTrue(pulse["success"])
        for group in (pulse["students"], pulse["assignments"], pulse["mastery"]):
            for key, metric in group.items():
                self.assertIn("value", metric, f"{key} must carry a value")
                self.assertTrue(metric["source"], f"{key} must carry its source")
                self.assertTrue(metric["href"], f"{key} must be clickable")
        self.assertEqual(pulse["students"]["total"]["value"], 1)

    def test_pulse_reflects_real_submissions(self):
        created = self.teacher.post("/api/v1/teacher/assignments", json={
            "class_id": self.class_id, "title": "Ops homework",
            "resource_type": "lesson", "resource_id": CONCEPT}).get_json()
        assignment_id = created["item"]["id"]
        before = self.teacher.get("/api/v1/teacher/pulse").get_json()
        self.assertEqual(before["assignments"]["completed"]["value"], 0)
        self.student.post(f"/api/v1/assignments/{assignment_id}/submit",
                          json={"answers": {"q1": "42"}, "score": 80})
        after = self.teacher.get("/api/v1/teacher/pulse").get_json()
        self.assertEqual(after["assignments"]["completed"]["value"], 1)
        self.assertEqual(after["assignments"]["completion_rate"]["value"], 100)
# ------------------------------------------------------------------
    # Assignment intelligence
    # ------------------------------------------------------------------
    def test_assignment_insights_report_completion_and_support(self):
        created = self.teacher.post("/api/v1/teacher/assignments", json={
            "class_id": self.class_id, "title": "Homework with struggles",
            "resource_type": "lesson", "resource_id": CONCEPT}).get_json()
        assignment_id = created["item"]["id"]
        _seed_attempts(self.student_id, CONCEPT, 1, 3)
        insights = self.teacher.get(
            f"/api/v1/teacher/assignments/{assignment_id}/insights").get_json()
        self.assertTrue(insights["success"])
        self.assertEqual(insights["completion"]["assigned"], 1)
        self.assertEqual(insights["completion"]["submitted"], 0)
        self.assertEqual(insights["completion"]["outstanding"], 1)
        support = insights["students_needing_support"]
        self.assertTrue(support, "an unsubmitted learner must appear for support")
        self.assertTrue(support[0]["reasons"])
        self.assertTrue(support[0]["source"])
        self.assertIsNotNone(insights["concepts"]["struggled"])
        self.assertTrue(insights["common_wrong_answers"])

    def test_teacher_cannot_read_another_teachers_assignment_insights(self):
        created = self.teacher.post("/api/v1/teacher/assignments", json={
            "title": "Private work", "resource_type": "lesson", "resource_id": "x"}).get_json()
        other_teacher, _ = _account("other-teacher", "teacher")
        response = other_teacher.get(
            f"/api/v1/teacher/assignments/{created['item']['id']}/insights")
        self.assertEqual(response.status_code, 404)

    def test_student_cannot_submit_an_assignment_not_assigned_to_them(self):
        created = self.teacher.post("/api/v1/teacher/assignments", json={
            "title": "Not yours", "resource_type": "lesson", "resource_id": "x"}).get_json()
        unassigned, _ = _account("unassigned", "student")
        response = unassigned.post(
            f"/api/v1/assignments/{created['item']['id']}/submit", json={"answers": {}})
        self.assertEqual(response.status_code, 404)

    def test_assignment_raises_a_persistent_notification(self):
        self.teacher.post("/api/v1/teacher/assignments", json={
            "class_id": self.class_id, "title": "Notify me",
            "resource_type": "lesson", "resource_id": CONCEPT})
        listing = self.student.get("/api/v1/notifications").get_json()
        self.assertIn("assignment_assigned", [item["kind"] for item in listing["items"]])
        self.assertIn("Notify me", [item["title"] for item in listing["items"]])

    def test_join_approval_notifies_the_student(self):
        self.assertIn("join_approved",
                      [item["kind"] for item in self.student.get(
                          "/api/v1/notifications").get_json()["items"]])


if __name__ == "__main__":
    unittest.main()