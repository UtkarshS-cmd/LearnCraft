import os
import tempfile
import unittest

DB_PATH = os.path.join(tempfile.gettempdir(), f"learncraft_content_{os.getpid()}.db")
os.environ["LEARNCRAFT_DB_PATH"] = DB_PATH
os.environ["LEARNCRAFT_SECRET_KEY"] = "content-test-secret"

from app.main import app
from app.database.connection import initialize_database
from app.services.content_catalog import (
    get_lesson,
    import_packages,
    list_questions,
    list_subject_lessons,
    list_subjects,
    load_packages,
    validate_packages,
)


class AcademicContentTests(unittest.TestCase):
    def setUp(self):
        initialize_database()
        import_packages(load_packages())
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_seed_is_valid_and_versioned(self):
        packages = load_packages()
        self.assertEqual(validate_packages(packages), [])
        self.assertEqual({item["slug"] for item in list_subjects()}, {"mathematics", "science", "social-science"})
        # Each subject ships at least two questions per chapter.
        self.assertGreaterEqual(len(list_questions()), 12)

    def test_every_subject_has_curriculum_lessons(self):
        for subject in list_subjects():
            lessons = list_subject_lessons(subject["slug"])
            self.assertTrue(lessons, f"{subject['slug']} has no lessons")
            for lesson in lessons:
                payload = get_lesson(lesson["lesson_id"])
                self.assertIsNotNone(payload, lesson["lesson_id"])
                self.assertIn("blocks", payload)
                self.assertTrue(payload["blocks"], f"{lesson['lesson_id']} has no blocks")
                for block in payload["blocks"]:
                    # The lesson player requires these keys to render correctly.
                    self.assertIn("stage", block, block)
                    self.assertIn("title", block, block)
                    self.assertIn("body", block, block)

    def test_content_api_exposes_source_mapped_questions(self):
        response = self.client.get("/api/v1/subjects")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["academic_year"], "2026-27")
        questions = self.client.get("/api/v1/questions?subject=science")
        self.assertEqual(questions.status_code, 200)
        self.assertIn("ncert.nic.in", questions.get_json()["items"][0]["source_reference"])


if __name__ == "__main__":
    unittest.main()
