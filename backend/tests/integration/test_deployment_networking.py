"""Deployment networking tests: CORS headers, /api/health, status fields.

Same-origin stays header-free; only allow-listed origins get CORS headers.
Cross-origin writes still 403 unless the origin is explicitly allow-listed.
"""

import os
import tempfile
import unittest

DB_PATH = os.path.join(tempfile.gettempdir(), f"learncraft_deploy_{os.getpid()}.db")
os.environ["LEARNCRAFT_DB_PATH"] = DB_PATH
os.environ["LEARNCRAFT_SECRET_KEY"] = "deploy-test-secret"

from app.database.connection import initialize_database
from app.main import app


def register_and_login(client, email):
    client.post("/auth/register", json={
        "name": "Deploy Tester", "email": email, "password": "Password123!",
    })
    return client.post("/auth/login", json={"email": email, "password": "Password123!"})


class DeploymentNetworkingTests(unittest.TestCase):
    def setUp(self):
        initialize_database()
        app.config["TESTING"] = True
        self._saved_cors = list(app.config.get("CORS_ORIGINS") or [])
        app.config["CORS_ORIGINS"] = []
        self.client = app.test_client()
        register_and_login(self.client, "deploy_student@example.com")

    def tearDown(self):
        app.config["CORS_ORIGINS"] = self._saved_cors

    def test_health_probe_unauthenticated(self):
        anon = app.test_client()
        response = anon.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "ok")

    def test_status_reports_env_fields(self):
        data = self.client.get("/api/system/status").get_json()
        self.assertIn("app_env", data)
        self.assertIn("cors_configured", data)
        self.assertIn("mode", data)

    def test_same_origin_has_no_cors_headers(self):
        response = self.client.get("/api/system/status")
        self.assertIsNone(response.headers.get("Access-Control-Allow-Origin"))

    def test_unknown_origin_gets_no_cors_headers(self):
        response = self.client.get(
            "/api/system/status", headers={"Origin": "http://evil.example"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.headers.get("Access-Control-Allow-Origin"))

    def test_allowlisted_origin_gets_cors_headers(self):
        app.config["CORS_ORIGINS"] = ["https://studio.example.com"]
        response = self.client.get(
            "/api/system/status", headers={"Origin": "https://studio.example.com"}
        )
        self.assertEqual(
            response.headers.get("Access-Control-Allow-Origin"),
            "https://studio.example.com",
        )
        # Allow-listed origins also pass the CSRF write guard.
        written = self.client.post(
            "/api/local/state",
            json={"kind": "progress", "record_id": "lesson:cors-1", "payload": {}},
            headers={"Origin": "https://studio.example.com"},
        )
        self.assertEqual(written.status_code, 200)

    def test_preflight_unknown_origin_rejected(self):
        response = self.client.open(
            "/api/local/state",
            method="OPTIONS",
            headers={"Origin": "http://evil.example"},
        )
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
