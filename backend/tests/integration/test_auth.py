import os
import tempfile
import unittest
from unittest.mock import patch

from app.core.security import hash_password

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

    def test_teacher_login_portal_requires_teacher_role(self):
        teacher = self._create_user("Teacher User", "teacher-login@example.com", "TEACHER")
        response = self.client.post("/auth/login", json={
            "email": teacher["email"], "password": "Password123!", "portal": "teacher"
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["user"]["role"], "TEACHER")

        student = self._create_user("Student User", "student-portal@example.com", "STUDENT")
        denied = self.client.post("/auth/login", json={
            "email": student["email"], "password": "Password123!", "portal": "teacher"
        })
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied.get_json()["code"], "TEACHER_ACCOUNT_REQUIRED")

    def test_teacher_registration_creates_teacher_and_redirects_to_dashboard(self):
        response = self.client.post("/auth/register", json={
            "name": "New Teacher", "email": "new-teacher@example.com",
            "password": "Password123!", "account_type": "teacher",
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["user"]["role"], "TEACHER")
        dashboard = self.client.get("/teacher")
        self.assertEqual(dashboard.status_code, 200)

    def _create_user(self, name, email, role):
        from app.database.connection import create_user

        return create_user(name, email, hash_password("Password123!"), role=role)

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

    def test_password_reset_uses_otp_and_allows_new_password(self):
        self.client.post(
            "/auth/register",
            json={
                "name": "Reset Student",
                "email": "reset@example.com",
                "password": "Password123!",
            },
        )

        captured = {}

        def capture_otp(email, otp):
            captured["otp"] = otp

        with patch("app.services.password_reset.PasswordResetService._send_otp", side_effect=capture_otp):
            response = self.client.post(
                "/auth/password-reset/request",
                json={"email": "reset@example.com"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["code"], "OTP_SENT")
        self.assertRegex(captured["otp"], r"^\d{6}$")

        reset = self.client.post(
            "/auth/password-reset/confirm",
            json={
                "email": "reset@example.com",
                "otp": captured["otp"],
                "new_password": "NewPassword123!",
            },
        )
        self.assertEqual(reset.status_code, 200)
        self.assertEqual(reset.get_json()["code"], "PASSWORD_RESET")

        login = self.client.post(
            "/auth/login",
            json={"email": "reset@example.com", "password": "NewPassword123!"},
        )
        self.assertEqual(login.status_code, 200)

    def test_password_reset_rejects_reused_otp(self):
        self.client.post(
            "/auth/register",
            json={
                "name": "Reuse Student",
                "email": "reuse@example.com",
                "password": "Password123!",
            },
        )
        captured = {}
        with patch(
            "app.services.password_reset.PasswordResetService._send_otp",
            side_effect=lambda email, otp: captured.setdefault("otp", otp),
        ):
            self.client.post("/auth/password-reset/request", json={"email": "reuse@example.com"})

        payload = {
            "email": "reuse@example.com",
            "otp": captured["otp"],
            "new_password": "NewPassword123!",
        }
        self.assertEqual(self.client.post("/auth/password-reset/confirm", json=payload).status_code, 200)
        self.assertEqual(self.client.post("/auth/password-reset/confirm", json=payload).status_code, 400)

    def test_me_requires_authentication(self):
        response = self.client.get("/auth/me")
        self.assertEqual(response.status_code, 401)

    def test_protected_routes_redirect_to_login(self):
        response = self.client.get("/home", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])


if __name__ == "__main__":
    unittest.main()
