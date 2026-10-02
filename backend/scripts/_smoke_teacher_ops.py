"""Quick smoke check: teacher->class->approve->assign->submit must not deadlock."""
import os
import sys
import tempfile
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["LEARNCRAFT_DB_PATH"] = os.path.join(
    tempfile.gettempdir(), f"learncraft_smoke_{os.getpid()}.db")
os.environ["LEARNCRAFT_SECRET_KEY"] = "smoke-secret"

from app.database.connection import initialize_database
from app.main import app


def account(prefix, role):
    client = app.test_client()
    client.post("/auth/register", json={
        "name": prefix, "email": f"{prefix}-{uuid.uuid4().hex[:6]}@example.com",
        "password": "Password123!", "account_type": role})
    return client, client.get("/auth/me").get_json()["user"]["id"]


initialize_database()
app.config["TESTING"] = True
teacher, teacher_id = account("smoke-teacher", "teacher")
student, student_id = account("smoke-student", "student")
class_id = teacher.post("/api/v1/teacher/classes", json={"name": "Smoke A"}).get_json()["item"]["id"]
pending = teacher.get("/api/v1/teacher/join-requests").get_json()["items"]
mine = [r for r in pending if r["student_id"] == student_id]
print("approve:", teacher.post(f"/api/v1/teacher/join-requests/{mine[0]['id']}/approve",
                              json={"class_id": class_id}).status_code)
created = teacher.post("/api/v1/teacher/assignments", json={
    "class_id": class_id, "title": "Smoke homework", "resource_type": "lesson",
    "resource_id": "cbse-x-2026-27-maths-real-numbers"}).get_json()
assignment_id = created["item"]["id"]
print("assignment:", assignment_id)
print("submit:", student.post(f"/api/v1/assignments/{assignment_id}/submit",
                              json={"answers": {"a": 1}}).status_code)
pulse = teacher.get("/api/v1/teacher/pulse")
data = pulse.get_json()
print("pulse:", pulse.status_code, data["students"]["total"],
      "completed:", data["assignments"]["completed"]["value"])
import sqlite3
con = sqlite3.connect(os.environ["LEARNCRAFT_DB_PATH"])
print("submissions:", con.execute("select assignment_id, student_id from assignment_submissions").fetchall())
print("targets:", con.execute("select assignment_id, student_id from assignment_targets").fetchall())
print("members:", con.execute("select class_id, student_id from class_members").fetchall())
con.close()
print("signals:", teacher.get("/api/v1/teacher/signals").status_code)
print("notifications:", student.get("/api/v1/notifications").get_json()["count"])
print("OK - no deadlock")