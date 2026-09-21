"""External resource tests: registry, validation, CRUD, search, bookmarks."""

import os
import tempfile
import unittest
import uuid

DB_PATH = os.path.join(tempfile.gettempdir(), "learncraft_resources_pytest.db")
if os.path.exists(DB_PATH):
    os.unlink(DB_PATH)
os.environ["LEARNCRAFT_DB_PATH"] = DB_PATH
os.environ["LEARNCRAFT_SECRET_KEY"] = "resources-test-secret"

from app.database.connection import initialize_database
from app.main import app
from app.services.external_providers import PROVIDERS, get_provider
from app.services.external_resources import obsidian_uri, validate_external_url


class ExternalResourceTests(unittest.TestCase):
    def setUp(self):
        initialize_database()
        app.config["TESTING"] = True
        tag = uuid.uuid4().hex[:8]
        self.student = app.test_client()
        self.teacher = app.test_client()
        student = self.student.post("/auth/register", json={
            "name": "Res Student", "email": f"res.student.{tag}@example.com", "password": "Password123!"})
        self.assertEqual(student.status_code, 201)
        teacher = self.teacher.post("/auth/register", json={
            "name": "Res Teacher", "email": f"res.teacher.{tag}@example.com",
            "password": "Password123!", "account_type": "teacher"})
        self.assertEqual(teacher.status_code, 201)

    def test_registry_official_urls(self):
        self.assertEqual(len(PROVIDERS), 8)
        self.assertEqual(get_provider("notion")["official_url"], "https://www.notion.com/")
        self.assertEqual(get_provider("obsidian")["official_url"], "https://obsidian.md/")
        self.assertEqual(get_provider("physics_wallah")["official_url"], "https://www.pw.live/")
        self.assertEqual(get_provider("khan_academy")["official_url"], "https://www.khanacademy.org/")
        self.assertEqual(get_provider("anki")["official_url"], "https://apps.ankiweb.net/")
        self.assertEqual(get_provider("github")["official_url"], "https://github.com/")
        self.assertEqual(get_provider("youtube")["official_url"], "https://www.youtube.com/")
        self.assertEqual(get_provider("google_drive")["official_url"], "https://drive.google.com/")

    def test_providers_api_requires_auth(self):
        self.assertEqual(app.test_client().get("/api/v1/resources/providers").status_code, 401)
        response = self.student.get("/api/v1/resources/providers")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.get_json()["items"]), 8)

    def test_url_validation_rejects_malicious(self):
        for bad in ["javascript:alert(1)", "data:text/html,hi", "file:///etc/passwd",
                    "http://evil.com/x", "https://evil.com/x",
                    "https://notion.com.evil.com/", "http://localhost:5000/"]:
            with self.assertRaises(ValueError, msg=bad):
                validate_external_url("notion", bad)
        self.assertEqual(validate_external_url("notion", "https://www.notion.com/abc"),
                         "https://www.notion.com/abc")
        with self.assertRaises(ValueError):
            validate_external_url("notion", "https://www.youtube.com/watch?v=x")

    def test_obsidian_uri_encoding(self):
        uri = obsidian_uri("My Vault", "Physics/Current Electricity")
        self.assertTrue(uri.startswith("obsidian://open?"))
        self.assertIn("vault=My%20Vault", uri)
        self.assertIn("file=Physics%2FCurrent%20Electricity", uri)

    def test_teacher_crud_student_forbidden(self):
        tag = uuid.uuid4().hex[:6]
        payload = {"provider": "khan_academy", "resource_type": "lesson",
                   "title": f"T1 {tag}", "url": f"https://www.khanacademy.org/math/lc-{tag}",
                   "subject": "Mathematics", "chapter": "Quadratics"}
        self.assertEqual(self.student.post("/api/v1/resources", json=payload).status_code, 403)
        rid = self.teacher.post("/api/v1/resources", json=payload).get_json()["item"]["id"]
        self.assertEqual(self.teacher.post(
            "/api/v1/resources", json={**payload, "url": "https://evil.com/"}).status_code, 400)
        listed = self.student.get("/api/v1/resources?subject=Mathematics").get_json()["items"]
        self.assertTrue(any(i["id"] == rid for i in listed))
        searched = self.student.get("/api/v1/resources/search?q=Quadratics").get_json()["items"]
        self.assertTrue(any(i["id"] == rid for i in searched))
        self.assertEqual(
            self.student.get("/api/v1/resources/context?subject=Mathematics&chapter=Quadratics").status_code, 200)
        self.assertEqual(
            self.teacher.put(f"/api/v1/resources/{rid}", json={"priority": 9}).get_json()["item"]["priority"], 9)
        self.assertEqual(self.teacher.post(f"/api/v1/resources/{rid}/verify").status_code, 200)

    def test_bookmark_and_activity_flow(self):
        tag = uuid.uuid4().hex[:6]
        created = self.teacher.post("/api/v1/resources", json={
            "provider": "youtube", "resource_type": "video", "title": f"B1 {tag}",
            "url": f"https://www.youtube.com/watch?v=LC{tag}0000000", "subject": "Science"})
        self.assertEqual(created.status_code, 201, created.get_data(as_text=True)[:300])
        rid = created.get_json()["item"]["id"]
        self.assertEqual(
            self.student.post(f"/api/v1/resources/{rid}/bookmark", json={"status": "IN_PROGRESS"}).status_code, 200)
        mine = self.student.get("/api/v1/resources/bookmarks/mine").get_json()["items"]
        self.assertTrue(any(b["resource_id"] == rid for b in mine))
        opened = self.student.get(f"/api/v1/resources/{rid}/open?format=json")
        self.assertIn("watch?v=LC", opened.get_json()["url"])
        self.assertEqual(self.student.post(f"/api/v1/resources/{rid}/complete", json={}).status_code, 200)
        actions = [a["action"] for a in self.student.get("/api/v1/resources/activity/mine").get_json()["items"]]
        for expected in ("opened", "completed", "bookmarked"):
            self.assertIn(expected, actions)
        self.assertEqual(self.student.delete(f"/api/v1/resources/{rid}/bookmark").status_code, 200)

    def test_hub_page_renders(self):
        body = self.student.get("/resources").get_data(as_text=True)
        self.assertIn("Learning Resources", body)
        self.assertIn("Notion", body)
        self.assertEqual(app.test_client().get("/resources", follow_redirects=False).status_code, 302)

    def test_adapters_and_anki_export(self):
        status = self.student.get("/api/v1/resources/adapters/status").get_json()["items"]
        self.assertTrue(any(i["provider"] == "notion" for i in status))
        export = self.student.post("/api/v1/resources/anki/export", json={
            "cards": [{"front": "F=ma?", "back": "Force law", "tags": ["physics"]}, {"front": "", "back": "skip"}]})
        self.assertEqual(export.status_code, 200)
        self.assertIn("F=ma?", export.get_data(as_text=True))
        self.assertEqual(app.test_client().post("/api/v1/resources/anki/export", json={}).status_code, 401)

    def test_context_layers_and_subject_aliases(self):
        """A CBSE chapter must always show chapter matches first, then the provider layer."""
        created = self.teacher.post("/api/v1/resources", json={
            "provider": "khan_academy", "resource_type": "practice", "title": "Electricity practice set",
            "url": "https://www.khanacademy.org/science/class-10-physics",
            "subject": "Physics", "chapter": "Current Electricity", "topic": "Ohm's law",
            "concept_ids": ["electric-current"], "verified": True})
        self.assertEqual(created.status_code, 201, created.get_data(as_text=True)[:300])
        chapter_id = created.get_json()["item"]["id"]

        # CBSE subject name "Science" resolves the Physics-tagged chapter link via aliases.
        items = self.student.get(
            "/api/v1/resources/context?subject=Science&chapter=Current%20Electricity").get_json()["items"]
        ids = [i["id"] for i in items]
        self.assertIn(chapter_id, ids)
        self.assertEqual(ids[0], chapter_id, "chapter match must rank before generic providers")
        self.assertTrue(any(not i["subject"] for i in items), "provider layer must always be present")

        # A subject the catalog knows nothing about still gets the provider layer.
        fallback = self.student.get("/api/v1/resources/context?subject=Astrophysics").get_json()["items"]
        self.assertTrue(fallback and all(not i["subject"] for i in fallback))

        # Concept filtering narrows to the linked concept only.
        concept = self.student.get(
            "/api/v1/resources/context?subject=Science&concept_id=electric-current").get_json()["items"]
        self.assertIn(chapter_id, [i["id"] for i in concept])
        self.assertNotIn(chapter_id, [i["id"] for i in self.student.get(
            "/api/v1/resources/context?subject=Science&concept_id=magnetism").get_json()["items"]])

    def test_context_excludes_disabled_resources(self):
        created = self.teacher.post("/api/v1/resources", json={
            "provider": "youtube", "resource_type": "video", "title": "Disabled lecture",
            "url": "https://www.youtube.com/watch?v=disabled-example", "subject": "Science",
            "chapter": "Light", "verified": True})
        rid = created.get_json()["item"]["id"]
        self.assertEqual(self.teacher.put(f"/api/v1/resources/{rid}", json={"enabled": False}).status_code, 200)
        ids = [i["id"] for i in self.student.get(
            "/api/v1/resources/context?subject=Science&chapter=Light").get_json()["items"]]
        self.assertNotIn(rid, ids)
        hub_ids = [i["id"] for i in self.student.get("/api/v1/resources?q=Disabled").get_json()["items"]]
        self.assertNotIn(rid, hub_ids)

    def test_github_project_validation(self):
        ok = self.student.post("/api/v1/resources/github/validate",
                               json={"url": "https://github.com/learncraft/dsa-linked-list"})
        self.assertEqual(ok.status_code, 200)
        body = ok.get_json()
        self.assertEqual(body["full_name"], "learncraft/dsa-linked-list")
        self.assertTrue(body["student_project"])
        for bad in ("https://evil.com/owner/repo", "https://github.com/onlyowner",
                    "javascript:alert(1)", "https://github.com/"):
            with self.subTest(bad=bad):
                self.assertEqual(
                    self.student.post("/api/v1/resources/github/validate", json={"url": bad}).status_code, 400)
        self.assertEqual(app.test_client().post(
            "/api/v1/resources/github/validate", json={"url": "https://github.com/a/b"}).status_code, 401)

    def test_obsidian_deep_link_requires_configured_vault(self):
        """Vault names stay in the browser; the API never invents a vault-less deep link."""
        seeded = [r for r in self.teacher.get("/api/v1/resources?provider=obsidian").get_json()["items"]
                  if r["url"] == "https://obsidian.md/"]
        if seeded:
            rid = seeded[0]["id"]  # reuse the verified seed resource (URLs are deduplicated)
        else:
            created = self.teacher.post("/api/v1/resources", json={
                "provider": "obsidian", "resource_type": "note", "title": "Obsidian Concept Note",
                "url": "https://obsidian.md/", "subject": "Physics", "chapter": "Current Electricity"})
            self.assertEqual(created.status_code, 201, created.get_data(as_text=True)[:300])
            rid = created.get_json()["item"]["id"]
        no_vault = self.student.get(f"/api/v1/resources/{rid}").get_json()
        self.assertEqual(no_vault["obsidian_uri"], "")
        self.assertFalse(no_vault["deep_link_supported"])
        with_vault = self.student.get(
            f"/api/v1/resources/{rid}?vault=My%20Vault&note=Physics/Current%20Electricity").get_json()
        self.assertTrue(with_vault["deep_link_supported"])
        self.assertIn("obsidian://open?vault=My%20Vault&file=Physics%2FCurrent%20Electricity",
                      with_vault["obsidian_uri"])
        opened = self.student.get(f"/api/v1/resources/{rid}/open?format=json")
        self.assertEqual(opened.get_json()["deep_link"], False)
        self.assertTrue(opened.get_json()["url"].startswith("https://obsidian.md/"))
        self.assertTrue(self.student.get(
            f"/api/v1/resources/{rid}/open?format=json&vault=My%20Vault&note=Physics/Current%20Electricity"
        ).get_json()["url"].startswith("obsidian://open?vault=My%20Vault"))

    def test_shared_external_link_assets_ship_offline(self):
        """The client-side deep-link helper must be served and cached for offline use."""
        script = self.student.get("/static/js/external-links.js")
        self.assertEqual(script.status_code, 200)
        body = script.get_data(as_text=True)
        self.assertIn("obsidian://open", body)
        self.assertIn("lcOpenExternal", body)
        self.assertIn("lcMarkOfflineOnly", body)
        self.assertIn("lc_obsidian_vault", body)  # localStorage only - never posted
        for page in ("/resources", "/subjects"):
            self.assertIn("/static/js/external-links.js", self.student.get(page).get_data(as_text=True))
        sw = self.student.get("/static/js/service-worker.js").get_data(as_text=True)
        self.assertIn("/static/js/external-links.js", sw)



if __name__ == "__main__":
    unittest.main()

