import os
import tempfile
import unittest

DB_PATH = os.path.join(tempfile.gettempdir(), f"learncraft_offline_test_{os.getpid()}.db")
os.environ["LEARNCRAFT_DB_PATH"] = DB_PATH
os.environ["LEARNCRAFT_SECRET_KEY"] = "offline-test-secret-key"

from app.main import app
from app.database.connection import get_connection, initialize_database


class LearnCraftOfflineApiTests(unittest.TestCase):
    def setUp(self):
        initialize_database()
        app.config["TESTING"] = True
        self.client = app.test_client()

        # Register a test student for authenticated routes
        self.client.post(
            "/auth/register",
            json={
                "name": "Offline Tester",
                "email": "offline_student@example.com",
                "password": "Password123!",
            },
        )
        self.client.post(
            "/auth/login",
            json={"email": "offline_student@example.com", "password": "Password123!"},
        )

    def test_system_status_endpoint(self):
        response = self.client.get("/api/system/status")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("mode", data)
        self.assertEqual(data["internet_enabled"], False)
        self.assertEqual(data["core_storage"], "sqlite")
        self.assertIn("queued_sync", data)
        self.assertIn("local_progress", data)
        self.assertIn("local_submissions", data)

    def test_local_state_auth_required(self):
        # Unauthenticated client
        anon_client = app.test_client()
        response = anon_client.post(
            "/api/local/state",
            json={"kind": "progress", "record_id": "test:1", "payload": {}},
        )
        self.assertEqual(response.status_code, 401)
        data = response.get_json()
        self.assertEqual(data["success"], False)
        self.assertEqual(data["code"], "UNAUTHORIZED")

    def test_local_state_validation(self):
        # Missing record_id
        res1 = self.client.post("/api/local/state", json={"kind": "progress", "record_id": ""})
        self.assertEqual(res1.status_code, 400)
        self.assertEqual(res1.get_json()["code"], "VALIDATION_ERROR")

        # Invalid kind
        res2 = self.client.post("/api/local/state", json={"kind": "invalid_kind", "record_id": "rec_1"})
        self.assertEqual(res2.status_code, 400)
        self.assertEqual(res2.get_json()["code"], "VALIDATION_ERROR")

    def test_local_state_progress_persistence(self):
        response = self.client.post(
            "/api/local/state",
            json={
                "kind": "progress",
                "record_id": "lesson:mechanics-1",
                "payload": {"idx": 2, "visited": [0, 1, 2], "done": False},
                "status": "in_progress",
                "percent_complete": 60,
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["code"], "LOCAL_STATE_SAVED")
        self.assertEqual(data["data"]["storage"], "sqlite")

        # Verify database record in local_progress
        conn = get_connection()
        row = conn.execute("SELECT record_id, sync_status FROM local_progress WHERE record_id = 'lesson:mechanics-1'").fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["record_id"], "lesson:mechanics-1")
        self.assertEqual(row["sync_status"], "local")

        # Verify bridge to learning_progress
        prog = conn.execute("SELECT lesson_id, status, percent_complete FROM learning_progress WHERE lesson_id = 'mechanics-1'").fetchone()
        self.assertIsNotNone(prog)
        self.assertEqual(prog["percent_complete"], 60)
        conn.close()

    def test_local_state_submission_and_idempotent_retry(self):
        client_event_id = "evt_test_submission_999"
        payload = {
            "kind": "submission",
            "record_id": "assignment:newtons-laws-4",
            "payload": {"answers": {"q1": "force"}, "status": "SUBMITTED"},
            "status": "SUBMITTED",
            "event_id": client_event_id,
        }

        # First attempt
        res1 = self.client.post("/api/local/state", json=payload)
        self.assertEqual(res1.status_code, 200)
        d1 = res1.get_json()
        self.assertEqual(d1["data"]["sync_status"], "queued")
        self.assertEqual(d1["data"]["event_id"], client_event_id)

        # Verify entry in sync_queue
        conn = get_connection()
        count = conn.execute("SELECT COUNT(*) FROM sync_queue WHERE event_id = ?", (client_event_id,)).fetchone()[0]
        self.assertEqual(count, 1)

        # Retry attempt with identical event_id (simulating browser retry after network timeout)
        res2 = self.client.post("/api/local/state", json=payload)
        self.assertEqual(res2.status_code, 200)

        # Verify NO duplicate rows created in sync_queue
        count_after_retry = conn.execute("SELECT COUNT(*) FROM sync_queue WHERE event_id = ?", (client_event_id,)).fetchone()[0]
        self.assertEqual(count_after_retry, 1)
        conn.close()

    def test_sync_queue_endpoint(self):
        # Enqueue an event via local/state
        self.client.post(
            "/api/local/state",
            json={
                "kind": "submission",
                "record_id": "practical:loops",
                "payload": {"code": "for i in range(1, 6): print(i**2)", "status": "SUBMITTED"},
                "status": "SUBMITTED",
                "event_id": "evt_practical_sync_1",
            },
        )

        res = self.client.get("/api/sync/queue")
        self.assertEqual(res.status_code, 200)
        items = res.get_json()
        self.assertIsInstance(items, list)
        matching = [it for it in items if it["event_id"] == "evt_practical_sync_1"]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["entity_type"], "submission")
        self.assertEqual(matching[0]["entity_id"], "practical:loops")

    def test_service_worker_and_offline_routes(self):
        # Service worker route
        sw_res = self.client.get("/service-worker.js")
        self.assertEqual(sw_res.status_code, 200)
        self.assertEqual(sw_res.headers.get("Content-Type"), "application/javascript; charset=utf-8")
        self.assertEqual(sw_res.headers.get("Service-Worker-Allowed"), "/")
        self.assertIn(b"learncraft-shell-v2", sw_res.data)

        # Offline fallback page
        offline_res = self.client.get("/offline")
        self.assertEqual(offline_res.status_code, 200)
        self.assertIn(b"Offline mode", offline_res.data)
        self.assertIn(b"Math Adventure Lab", offline_res.data)
        self.assertIn(b"Physics Adventure Lab", offline_res.data)


if __name__ == "__main__":
    unittest.main()
