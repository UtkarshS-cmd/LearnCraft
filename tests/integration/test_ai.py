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
from app.services.ai_tutor import AIContext, AIService, ncert_questions
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

    def test_status_reports_built_in_assistant_when_providers_are_missing(self):
        response = self.client.get("/api/v1/ai/status")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["state"], "offline")
        self.assertEqual(response.get_json()["provider"], "built-in")

    def test_chat_persists_answer_and_conversation_is_user_scoped(self):
        response = self.client.post("/api/v1/ai/chat", json={
            "message": "Explain this concept simply.",
            "lesson_id": "cbse-x-2026-27-science-life-processes-photosynthesis",
            "subject": "Science",
        })
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["provider"], "offline")
        self.assertTrue(payload["answer"])
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

    def test_ncert_dataset_answers_exact_question(self):
        self.assertGreater(len(ncert_questions()), 0)
        item = ncert_questions()[0]
        response = self.client.post("/api/v1/ai/chat", json={
            "message": item["question"],
            "subject": item["subject"],
            "mode": "Explain",
        })
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["provider"], "offline")
        self.assertIn(item["answer"], payload["answer"])
        self.assertIn("ncert-class10", {source["content_version"] for source in payload["sources"]})

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

    def test_local_answer_has_multiple_guidance_sections(self):
        service = AIService()
        answer, provider = service.answer(
            "Explain resources and development.",
            AIContext(subject="Social Science", chapter="Resources and Development"),
            [],
        )
        self.assertEqual(provider, "offline")
        self.assertGreaterEqual(answer.count("\n\n"), 2)
        self.assertIn("Practice", answer)

    def test_features_curriculum_is_retrievable_offline(self):
        from app.services.ai_tutor import retrieve_context

        chunks = retrieve_context(AIContext(subject="Science"), "motion and force")
        self.assertTrue(any(chunk["content_version"] == "features-2026-27" for chunk in chunks))


if __name__ == "__main__":
    unittest.main()
