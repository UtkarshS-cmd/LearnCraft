import os
import tempfile
import unittest

DB_PATH = os.path.join(tempfile.gettempdir(), f"learncraft_test_{os.getpid()}.db")
os.environ["LEARNCRAFT_DB_PATH"] = DB_PATH
os.environ["LEARNCRAFT_SECRET_KEY"] = "test-secret-key"

from app.main import app
from app.database.connection import initialize_database


class LearnCraftAuthTests(unittest.TestCase):
    def setUp(self):
        initialize_database()
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_register_and_login_success(self):
        response = self.client.post(
            "/auth/register",
            json={
                "name": "Test Student",
                "email": "student@example.com",
                "password": "Password123!",
            },
        )
        self.assertEqual(response.status_code, 201)
        payload = response.get_json()
        self.assertEqual(payload["success"], True)
        self.assertEqual(payload["user"]["email"], "student@example.com")

        login = self.client.post(
            "/auth/login",
            json={"email": "student@example.com", "password": "Password123!"},
        )
        self.assertEqual(login.status_code, 200)
        self.assertTrue(login.get_json()["success"])

    def test_duplicate_email_rejected(self):
        self.client.post(
            "/auth/register",
            json={
                "name": "Test Student",
                "email": "duplicate@example.com",
                "password": "Password123!",
            },
        )

        response = self.client.post(
            "/auth/register",
            json={
                "name": "Another User",
                "email": "duplicate@example.com",
                "password": "Password123!",
            },
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["code"], "EMAIL_EXISTS")

    def test_login_failure_returns_clear_error(self):
        response = self.client.post(
            "/auth/login",
            json={"email": "missing@example.com", "password": "Password123!"},
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["code"], "INVALID_CREDENTIALS")

    def test_me_requires_authentication(self):
        response = self.client.get("/auth/me")
        self.assertEqual(response.status_code, 401)

    def test_protected_routes_redirect_to_login(self):
        response = self.client.get("/home", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])


if __name__ == "__main__":
    unittest.main()
