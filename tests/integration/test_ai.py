import os
import tempfile
import unittest
import uuid

DB_PATH = os.path.join(tempfile.gettempdir(), f"learncraft_ai_{os.getpid()}.db")
os.environ["LEARNCRAFT_DB_PATH"] = DB_PATH
os.environ["LEARNCRAFT_SECRET_KEY"] = "ai-test-secret"
os.environ.pop("LEARNCRAFT_AI_CLOUD_URL", None)
os.environ.pop("LEARNCRAFT_AI_CLOUD_KEY", None)
os.environ.pop("LEARNCRAFT_AI_LOCAL_COMMAND", None)

from app.database.connection import initialize_database
from app.services.ai_tutor import AIContext, AIService
from app.main import app


class AITutorTests(unittest.TestCase):
    def setUp(self):
        initialize_database()
        app.config["TESTING"] = True
        self.client = app.test_client()
        response = self.client.post("/auth/register", json={
            "name": "AI Student", "email": f"ai-{uuid.uuid4().hex}@example.com", "password": "Password123!"
        })
        self.assertEqual(response.status_code, 201)

    def test_status_is_truthful_when_providers_are_missing(self):
        response = self.client.get("/api/v1/ai/status")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["state"], "unavailable")

    def test_chat_persists_limitation_and_conversation_is_user_scoped(self):
        response = self.client.post("/api/v1/ai/chat", json={
            "message": "Explain this concept simply.",
            "lesson_id": "cbse-x-2026-27-science-life-processes-photosynthesis",
            "subject": "Science",
        })
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["provider"], "unavailable")
        conversation = self.client.get(f"/api/v1/ai/conversations/{payload['conversation_id']}")
        self.assertEqual(conversation.status_code, 200)
        self.assertEqual(len(conversation.get_json()["messages"]), 2)

        self.client.post("/auth/logout")
        other = self.client.post("/auth/register", json={
            "name": "Other Student", "email": f"other-{uuid.uuid4().hex}@example.com", "password": "Password123!"
        })
        self.assertEqual(other.status_code, 201)
        denied = self.client.get(f"/api/v1/ai/conversations/{payload['conversation_id']}")
        self.assertEqual(denied.status_code, 404)

    def test_auto_mode_uses_local_provider_when_cloud_is_unavailable(self):
        class FakeProvider:
            name = "offline"

            def available(self):
                return True

            def generate(self, messages, context):
                return "Use the evidence step by step."

        service = AIService()
        service.cloud = type("Cloud", (), {"available": lambda self: False, "name": "online"})()
        service.local = FakeProvider()
        answer, provider = service.answer("Explain photosynthesis simply.", AIContext(subject="Science"), [])
        self.assertEqual(provider, "offline")
        self.assertIn("step by step", answer)


if __name__ == "__main__":
    unittest.main()
