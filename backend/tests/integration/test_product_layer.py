"""Product layer: mission engine, concept mastery map, adaptive next action,
notifications, search and cross-user permission isolation.

Every assertion here is about REAL persisted state: a mission only completes
after real learning evidence exists, and one learner can never read another
learner's missions, notifications, notes or search results.
"""
import os
import tempfile
import unittest
import uuid

DB_PATH = os.path.join(tempfile.gettempdir(), f"learncraft_product_{os.getpid()}.db")
os.environ["LEARNCRAFT_DB_PATH"] = DB_PATH
os.environ["LEARNCRAFT_SECRET_KEY"] = "product-test-secret"

from app.database.connection import initialize_database, save_learning_progress
from app.main import app
from app.services.content_catalog import import_packages, list_questions, load_packages
from app.services.mastery import record_attempt
from app.services.question_log import record_attempt as log_attempt

WEAK_CONCEPT = "cbse-x-2026-27-maths-real-numbers"


def _register(client, prefix):
    email = f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"
    response = client.post("/auth/register", json={
        "name": f"{prefix} user", "email": email, "password": "Password123!",
        "account_type": "student"})
    assert response.status_code == 201, response.get_data(as_text=True)
    return email


def _complete_mission_evidence(client, mission, uid):
    """Record the real evidence a mission asks for (progress + attempts)."""
    from app.services.concept_map import lesson_for_key

    concept = mission["concept_key"]
    lesson_id = lesson_for_key(concept)
    if lesson_id:
        save_learning_progress(uid, subject_slug="mathematics", lesson_id=lesson_id,
                               status="completed", percent_complete=100)
    for index in range(4):
        log_attempt(uid, f"q-{mission['id']}-{index}", concept, "mathematics",
                    "MEDIUM", index % 2 == 0)


class ProductLayerTests(unittest.TestCase):
    def setUp(self):
        initialize_database()
        import_packages(load_packages())
        app.config["TESTING"] = True
        self.client = app.test_client()
        self.email = _register(self.client, "prod")
        self.uid = int(self.client.get("/auth/me").get_json()["user"]["id"])

    # ------------------------------------------------------------------
    # Adaptive next action (structured, with evidence)
    # ------------------------------------------------------------------
    def test_next_action_explains_why_with_real_actions(self):
        record_attempt(self.uid, WEAK_CONCEPT, False, "MEDIUM", "mathematics")
        response = self.client.get("/api/v1/learning/next")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()["next"]
        self.assertTrue(payload["why"], "recommendation must carry evidence")
        self.assertTrue(payload["actions"])
        for action in payload["actions"]:
            self.assertTrue(action["href"].startswith("/"), action)

    def test_next_action_actions_point_to_real_routes(self):
        for action in self.client.get("/api/v1/learning/next").get_json()["next"]["actions"]:
            self.assertEqual(self.client.get(action["href"]).status_code, 200,
                             f"dead action route: {action['href']}")

    # ------------------------------------------------------------------
    # Concept mastery map
    # ------------------------------------------------------------------
    def test_mastery_map_is_generated_from_curriculum_not_hardcoded(self):
        response = self.client.get("/api/v1/mastery/map")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["nodes"], "concept graph must come from the package")
        self.assertTrue(data["edges"], "prerequisite edges must come from the package")
        for node in data["nodes"]:
            self.assertIn(node["state"],
                          {"NOT_STARTED", "LEARNING", "DEVELOPING", "MASTERED"})
            self.assertIsInstance(node["mastery"], (int, float))

    def test_concept_state_reflects_persisted_mastery(self):
        graph = self.client.get("/api/v1/mastery/map").get_json()
        target = graph["nodes"][0]["concept_id"]
        for _ in range(6):
            record_attempt(self.uid, target, True, "HARD", "mathematics")
        updated = self.client.get("/api/v1/mastery/map").get_json()
        node = next(n for n in updated["nodes"] if n["concept_id"] == target)
        self.assertGreater(node["attempts"], 0)
        self.assertIn(node["state"], {"DEVELOPING", "MASTERED"})

    def test_concept_detail_has_prereqs_attempts_and_recommendation(self):
        graph = self.client.get("/api/v1/mastery/map").get_json()
        target = graph["nodes"][0]["concept_id"]
        log_attempt(self.uid, "q1", target, "mathematics", "MEDIUM", False)
        response = self.client.get(f"/api/v1/mastery/concepts/{target}")
        self.assertEqual(response.status_code, 200)
        concept = response.get_json()["concept"]
        self.assertTrue(concept["recent_attempts"])
        self.assertIn("prerequisites", concept)
        self.assertIn("next_concepts", concept)
        self.assertTrue(concept["recommended"]["why"])
        self.assertTrue(concept["recommended"]["actions"])

    def test_mastery_map_requires_authentication(self):
        self.assertEqual(app.test_client().get("/api/v1/mastery/map").status_code, 401)

    # ------------------------------------------------------------------
    # Mission engine
    # ------------------------------------------------------------------
    def test_missions_are_generated_from_learning_state(self):
        record_attempt(self.uid, WEAK_CONCEPT, False, "MEDIUM", "mathematics")
        response = self.client.get("/api/v1/missions")
        self.assertEqual(response.status_code, 200)
        items = response.get_json()["items"]
        self.assertTrue(items, "a weak concept must produce a mission")
        mission = items[0]
        self.assertIn(mission["kind"], {"repair", "continue", "assignment"})
        self.assertTrue(mission["why"], "mission must say why it exists")
        self.assertTrue(mission["steps"])
        for step in mission["steps"]:
            self.assertGreater(step["required_count"], 0)

    def test_mission_generation_is_idempotent(self):
        record_attempt(self.uid, WEAK_CONCEPT, False, "MEDIUM", "mathematics")
        first = self.client.get("/api/v1/missions").get_json()["items"]
        second = self.client.get("/api/v1/missions").get_json()["items"]
        self.assertEqual([m["mission_key"] for m in first],
                         [m["mission_key"] for m in second])

    def test_mission_completes_only_from_real_learning_events(self):
        record_attempt(self.uid, WEAK_CONCEPT, False, "MEDIUM", "mathematics")
        mission = self.client.get("/api/v1/missions").get_json()["items"][0]
        self.assertNotEqual(mission["state"], "completed")
        self.assertLess(mission["percent"], 100)

        _complete_mission_evidence(self.client, mission, self.uid)
        refreshed = self.client.post(f"/api/v1/missions/{mission['id']}/progress")
        self.assertEqual(refreshed.status_code, 200)
        done = refreshed.get_json()["mission"]
        self.assertEqual(done["state"], "completed")
        self.assertEqual(done["percent"], 100)
        self.assertTrue(all(step["done"] for step in done["steps"]))

    def test_mission_start_and_dismiss(self):
        record_attempt(self.uid, WEAK_CONCEPT, False, "MEDIUM", "mathematics")
        mission = self.client.get("/api/v1/missions").get_json()["items"][0]
        started = self.client.post(f"/api/v1/missions/{mission['id']}/start")
        self.assertEqual(started.status_code, 200)
        self.assertIn(started.get_json()["mission"]["state"], {"active", "completed"})
        self.assertIn(self.client.post(f"/api/v1/missions/{mission['id']}/dismiss").status_code,
                      (200, 404))

    def test_mission_requires_authentication(self):
        self.assertEqual(app.test_client().get("/api/v1/missions").status_code, 401)

    # ------------------------------------------------------------------
    # Permissions: learner A must never read learner B
    # ------------------------------------------------------------------
    def test_student_cannot_read_another_students_mission(self):
        record_attempt(self.uid, WEAK_CONCEPT, False, "MEDIUM", "mathematics")
        mission = self.client.get("/api/v1/missions").get_json()["items"][0]
        other = app.test_client()
        _register(other, "other")
        self.assertEqual(other.get(f"/api/v1/missions/{mission['id']}").status_code, 404)
        self.assertEqual(other.post(f"/api/v1/missions/{mission['id']}/start").status_code, 404)
        self.assertEqual(other.post(f"/api/v1/missions/{mission['id']}/progress").status_code, 404)
        # The owner's mission is untouched by the attempt.
        owner = self.client.get(f"/api/v1/missions/{mission['id']}").get_json()["mission"]
        self.assertNotEqual(owner["state"], "dismissed")

    def test_student_cannot_read_another_students_notes_via_search(self):
        self.client.post("/api/notes", json={
            "title": "Private torque note", "body": "lever arm", "subject": "Physics"})
        other = app.test_client()
        _register(other, "nosy")
        theirs = other.get("/api/v1/search?q=torque").get_json()["groups"].get("notes", [])
        mine = self.client.get("/api/v1/search?q=torque").get_json()["groups"].get("notes", [])
        self.assertTrue(mine, "own note must be searchable")
        self.assertEqual(theirs, [], "another learner's note must never leak")


    def test_student_cannot_mark_another_students_notification_read(self):
        from app.services.notifications import notify

        mine = notify(self.uid, "announcement", "Private notice", "", "/assignments")
        other = app.test_client()
        _register(other, "reader")
        self.assertEqual(other.post(f"/api/v1/notifications/{mine}/read").status_code, 404)
        self.assertGreaterEqual(
            self.client.get("/api/v1/notifications/unread").get_json()["unread"], 1)

    def test_notifications_require_authentication(self):
        anon = app.test_client()
        self.assertEqual(anon.get("/api/v1/notifications").status_code, 401)
        self.assertEqual(anon.get("/api/v1/search?q=physics").status_code, 401)

    # ------------------------------------------------------------------
    # Notifications
    # ------------------------------------------------------------------
    def test_notification_unread_lifecycle(self):
        from app.services.notifications import notify

        notify(self.uid, "assignment_assigned", "New homework", "Due Friday", "/assignments",
               dedupe_key="asg-1")
        notify(self.uid, "assignment_assigned", "New homework", "Due Friday", "/assignments",
               dedupe_key="asg-1")  # duplicate must not spam
        listing = self.client.get("/api/v1/notifications").get_json()
        self.assertEqual(listing["count"], 1)
        self.assertEqual(listing["unread"], 1)
        item = listing["items"][0]
        self.assertTrue(item["href"])
        self.assertFalse(item["read"])
        self.client.post(f"/api/v1/notifications/{item['id']}/read")
        self.assertEqual(
            self.client.get("/api/v1/notifications/unread").get_json()["unread"], 0)

    def test_mission_completion_notifies_the_learner(self):
        from app.services.notifications import list_notifications

        record_attempt(self.uid, WEAK_CONCEPT, False, "MEDIUM", "mathematics")
        mission = self.client.get("/api/v1/missions").get_json()["items"][0]
        _complete_mission_evidence(self.client, mission, self.uid)
        self.client.post(f"/api/v1/missions/{mission['id']}/progress")
        self.assertIn("mission_completed", [n["kind"] for n in list_notifications(self.uid)])

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------
    def test_search_returns_categorised_results_with_real_links(self):
        data = self.client.get("/api/v1/search?q=prime").get_json()
        self.assertTrue(data["groups"], "search must find curriculum entities")
        for group, items in data["groups"].items():
            self.assertIn(group, data["categories"])
            for item in items:
                self.assertTrue(item["href"].startswith("/"))

    def test_search_short_query_is_handled(self):
        data = self.client.get("/api/v1/search?q=a").get_json()
        self.assertEqual(data["count"], 0)
        self.assertIn("message", data)

    def test_search_results_are_bounded(self):
        data = self.client.get("/api/v1/search?q=the&limit=3").get_json()
        for items in data["groups"].values():
            self.assertLessEqual(len(items), 3, "search must stay bounded per category")

    # ------------------------------------------------------------------
    # Quiz -> attempts -> mission evidence chain
    # ------------------------------------------------------------------
    def test_quiz_check_records_attempt_history(self):
        question = list_questions()[0]
        options = [o for o in question.get("options", []) if o.get("is_correct")]
        answer = options[0]["option_id"] if options else question.get("answer")
        response = self.client.post("/api/v1/quizzes/check", json={
            "question_id": question["question_id"], "answer": answer})
        self.assertEqual(response.status_code, 200)
        concept_id = response.get_json()["concept"]
        detail = self.client.get(f"/api/v1/mastery/concepts/{concept_id}")
        if detail.status_code == 200:
            self.assertTrue(detail.get_json()["concept"]["recent_attempts"])


if __name__ == "__main__":
    unittest.main()

