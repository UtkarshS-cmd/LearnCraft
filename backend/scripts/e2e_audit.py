"""Real-browser E2E audit for LearnCraft.

Runs a student + teacher journey against a live http://localhost:5000 server,
capturing console errors, failed requests, dead routes and workflow results.

Usage:
    python scripts/e2e_audit.py [--base http://localhost:5000] [--headed]
"""
from __future__ import annotations

import argparse
import sys
import uuid

from playwright.sync_api import sync_playwright

PASS, FAIL, WARN = "PASS", "FAIL", "WARN"
results: list[tuple[str, str, str]] = []


def record(status: str, name: str, detail: str = "") -> None:
    results.append((status, name, detail))
    print(f"[{status}] {name}" + (f" — {detail}" if detail else ""))


class Browser:
    def __init__(self, page, label):
        self.page = page
        self.label = label
        self.console_errors: list[str] = []
        self.failed_requests: list[str] = []
        page.on("console", lambda m: self.console_errors.append(f"{m.type}: {m.text}")
                if m.type == "error" else None)
        page.on("requestfailed", lambda r: self.failed_requests.append(
            f"{r.method} {r.url} :: {r.failure}"))
        page.on("response", lambda r: self.failed_requests.append(
            f"HTTP {r.status} {r.url}") if r.status >= 500 else None)

    def goto(self, url, expect_status=200):
        resp = self.page.goto(url, wait_until="domcontentloaded")
        ok = resp is not None and resp.status == expect_status
        return ok, (resp.status if resp else "no-response")


def register(page, base, email, password, account, name):
    """Complete the real registration form on /login."""
    page.goto(f"{base}/login", wait_until="domcontentloaded")
    portal_sel = "#portalTeacherTab" if account == "teacher" else "#portalStudentTab"
    try:
        page.click(portal_sel, timeout=2000)
    except Exception:
        pass
    page.click("#registerTab", timeout=3000)
    page.wait_for_timeout(300)
    page.fill("#registerName", name)
    page.fill("#registerEmail", email)
    page.fill("#registerPassword", password)
    page.click("#registerSubmit")
    page.wait_for_timeout(2500)
    return page.url


def run(base: str, headed: bool) -> int:
    suffix = uuid.uuid4().hex[:6]
    student_email = f"e2e_student_{suffix}@learncraft.test"
    teacher_email = f"e2e_teacher_{suffix}@learncraft.test"
    password = "Str0ngPass!42"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        sb = Browser(page, "student")

        # 1. Landing / login page
        ok, status = sb.goto(f"{base}/login")
        record(PASS if ok else FAIL, "GET /login", f"status={status}")
        page.screenshot(path="scripts/_audit_01_login.png")

        # 2. Register a student through the real UI form
        try:
            url = register(page, base, student_email, password, "student", "E2E Student")
            record(PASS if "/login" not in url else FAIL,
                   "Student register via UI", f"landed={url}")
        except Exception as exc:
            record(FAIL, "Student register via UI", str(exc)[:200])
        page.screenshot(path="scripts/_audit_02_after_register.png")

        # 3. Student home
        ok, status = sb.goto(f"{base}/home")
        record(PASS if ok else FAIL, "GET /home", f"status={status}")
        try:
            has_greet = page.locator(".hub-greet, h1").first.is_visible(timeout=3000)
        except Exception:
            has_greet = False
        record(PASS if has_greet else FAIL, "Home renders greeting")
        page.screenshot(path="scripts/_audit_03_home.png", full_page=True)

        # 4. Walk every nav item (dead-route sweep)
        nav_routes = ["/my-learning", "/subjects", "/resources", "/tests",
                      "/practical", "/assignments", "/sandbox", "/progress",
                      "/notes", "/ask-ai", "/profile", "/settings", "/help"]
        for route in nav_routes:
            ok, status = sb.goto(f"{base}{route}")
            state = PASS if ok else FAIL
            try:
                body_text = page.locator("body").inner_text(timeout=3000)
            except Exception:
                body_text = ""
            if len(body_text.strip()) < 40:
                state = FAIL
            record(state, f"GET {route}", f"status={status}, textlen={len(body_text)}")

        # 5. Subjects -> subject detail -> lesson player
        ok, status = sb.goto(f"{base}/subjects")
        record(PASS if ok else FAIL, "GET /subjects", f"status={status}")
        page.screenshot(path="scripts/_audit_05_subjects.png", full_page=True)
        first_card = page.locator("a[href^='/subjects/']").first
        if first_card.count():
            try:
                href = first_card.get_attribute("href")
                page.goto(base + href, wait_until="domcontentloaded")
                page.wait_for_timeout(800)
                record(PASS, "Open subject detail", f"url={page.url}")
            except Exception as exc:
                record(FAIL, "Open subject detail", str(exc)[:200])
        else:
            record(FAIL, "Open subject detail", "no subject card link found")
        page.screenshot(path="scripts/_audit_06_subject_detail.png", full_page=True)

        lesson_link = page.locator("a[href*='/lessons/']").first
        if lesson_link.count():
            try:
                href = lesson_link.get_attribute("href")
                page.goto(href if href.startswith("http") else base + href,
                          wait_until="domcontentloaded")
                page.wait_for_timeout(800)
                record(PASS, "Open lesson player", f"url={page.url}")
            except Exception as exc:
                record(FAIL, "Open lesson player", str(exc)[:200])
        else:
            record(WARN, "Open lesson player", "no lesson link on subject page")
        page.screenshot(path="scripts/_audit_07_lesson.png", full_page=True)

        # 6. Quiz flow on /tests
        ok, status = sb.goto(f"{base}/tests")
        record(PASS if ok else FAIL, "GET /tests", f"status={status}")
        page.wait_for_timeout(1200)
        try:
            q_count = page.locator(".quiz-card, .question, [data-question-id]").count()
        except Exception:
            q_count = 0
        record(PASS if q_count > 0 else WARN, "Quiz questions rendered",
               f"count={q_count}")
        page.screenshot(path="scripts/_audit_08_quiz.png", full_page=True)

        # 7. API sanity for the student session
        for api in ["/api/v1/dashboard", "/api/v1/mastery", "/api/v1/learning/next",
                    "/api/v1/gamification", "/api/v1/progress", "/api/v1/assignments",
                    "/api/v1/announcements", "/api/v1/ai/status"]:
            resp = page.request.get(base + api)
            record(PASS if resp.status < 400 else FAIL, f"API {api}",
                   f"status={resp.status}")

        page.screenshot(path="scripts/_audit_04_tests.png", full_page=True)

        # 8. Teacher registration + journey (fresh context = no student session)
        tctx = browser.new_context(viewport={"width": 1440, "height": 900})
        tpage = tctx.new_page()
        tb = Browser(tpage, "teacher")
        try:
            url = register(tpage, base, teacher_email, password, "teacher", "E2E Teacher")
            record(PASS if "/login" not in url else FAIL,
                   "Teacher register via UI", f"landed={url}")
        except Exception as exc:
            record(FAIL, "Teacher register via UI", str(exc)[:200])

        ok, status = tb.goto(f"{base}/teacher")
        record(PASS if ok else FAIL, "GET /teacher", f"status={status}")
        tpage.screenshot(path="scripts/_audit_09_teacher.png", full_page=True)

        resp = tpage.request.get(base + "/api/v1/teacher/dashboard")
        record(PASS if resp.status < 400 else FAIL,
               "API /api/v1/teacher/dashboard", f"status={resp.status}")

        # Create class (API mirrors the UI POST)
        resp = tpage.request.post(base + "/api/v1/teacher/classes",
                                  data={"name": f"E2E Class {suffix}"})
        record(PASS if resp.status in (200, 201) else FAIL,
               "POST /api/v1/teacher/classes", f"status={resp.status}")
        class_id = (resp.json().get("item", {}).get("id")
                    if resp.status in (200, 201) else None)

        resp = tpage.request.get(base + "/api/v1/teacher/join-requests")
        record(PASS if resp.status < 400 else FAIL,
               "GET /api/v1/teacher/join-requests", f"status={resp.status}")
        pending = resp.json().get("items", []) if resp.status < 400 else []
        approved = 0
        for req in pending:
            body = {"class_id": class_id} if class_id else {}
            r = tpage.request.post(
                base + f"/api/v1/teacher/join-requests/{req['id']}/approve", data=body)
            if r.status < 400:
                approved += 1
        record(PASS if approved else WARN, "Approve student join requests",
               f"approved={approved}/{len(pending)}")

        # Create assignment
        resp = tpage.request.post(
            base + "/api/v1/teacher/assignments",
            data={"title": "E2E Homework", "class_id": class_id or "",
                  "resource_type": "lesson", "resource_id": "friction-43"})
        record(PASS if resp.status in (200, 201) else FAIL,
               "POST /api/v1/teacher/assignments", f"status={resp.status}")

        # Student receives the assignment
        resp = page.request.get(base + "/api/v1/assignments")
        items = resp.json().get("items", []) if resp.status < 400 else []
        record(PASS if any(i.get("title") == "E2E Homework" for i in items) else FAIL,
               "Student receives assignment", f"count={len(items)}")

        # 9. Console / network error sweep
        for route in ["/home", "/subjects", "/progress", "/notes", "/ask-ai"]:
            try:
                sb.goto(f"{base}{route}")
            except Exception:
                pass
        try:
            tb.goto(f"{base}/teacher")
        except Exception:
            pass
        real_console = [e for e in sb.console_errors + tb.console_errors
                        if "favicon" not in e and "manifest" not in e]
        real_failed = [f for f in sb.failed_requests + tb.failed_requests
                       if "favicon" not in f and ".webmanifest" not in f
                       and "ERR_ABORTED" not in f]
        record(PASS if not real_console else WARN, "Console errors",
               f"{len(real_console)}: {real_console[:3]}")
        record(PASS if not real_failed else WARN, "Failed requests",
               f"{len(real_failed)}: {real_failed[:3]}")

        # 10. Product-layer verification (real API data drives the UI)
        product = Browser(ctx.new_page(), "product")
        product.page = product.page  # keep the helper but expose the page directly
        page_p = product.page
        ok, status = product.goto(f"{base}/missions")
        record(PASS if ok else FAIL, "GET /missions", f"status={status}")
        product.page.screenshot(path="scripts/_audit_10_missions.png", full_page=True)

        missions = page.request.get(f"{base}/api/v1/missions").json()
        record(PASS if missions.get("success") and missions.get("count") is not None else FAIL,
               "API /api/v1/missions", f"count={missions.get('count')}")

        ok, status = product.goto(f"{base}/mastery")
        record(PASS if ok else FAIL, "GET /mastery", f"status={status}")
        product.page.wait_for_timeout(1800)
        nodes = product.page.locator(".map-node").count()
        record(PASS if nodes > 0 else FAIL, "Mastery map renders nodes from API",
               f"nodes={nodes}")
        if nodes:
            product.page.locator(".map-node").first.click()
            product.page.wait_for_timeout(1200)
            detail = product.page.locator("#detailPanel").inner_text()
            record(PASS if "Mastery" in detail else FAIL, "Concept drill-down panel",
                   detail[:60].replace("\n", " "))
        product.page.screenshot(path="scripts/_audit_11_mastery.png", full_page=True)

        master_map = page.request.get(f"{base}/api/v1/mastery/map").json()
        record(PASS if master_map.get("nodes") else FAIL, "API /api/v1/mastery/map",
               f"nodes={len(master_map.get('nodes', []))}")

        search = page.request.get(f"{base}/api/v1/search?q=prime")
        search_data = search.json()
        record(PASS if search.status == 200 and search_data.get("count", 0) > 0 else FAIL,
               "API /api/v1/search", f"count={search_data.get('count')}")

        notif = page.request.get(f"{base}/api/v1/notifications").json()
        record(PASS if notif.get("success") else FAIL, "API /api/v1/notifications",
               f"unread={notif.get('unread')}")

        ai_ctx = page.request.get(f"{base}/api/v1/ai/context")
        record(PASS if ai_ctx.status == 200 else FAIL, "API /api/v1/ai/context",
               f"status={ai_ctx.status}")

        sessions = page.request.get(f"{base}/api/v1/sessions/stages")
        stage_data = sessions.json()
        record(PASS if sessions.status == 200 and stage_data.get("stages")
               else FAIL, "API /api/v1/sessions/stages",
               f"stages={stage_data.get('stages') if sessions.status == 200 else 0}")

        # Command palette (real keyboard interaction)
        product.page.goto(f"{base}/home", wait_until="domcontentloaded")
        product.page.keyboard.press("Control+k")
        product.page.wait_for_timeout(500)
        palette_open = product.page.locator("#lcPalette.open").count() > 0
        record(PASS if palette_open else FAIL, "Command palette opens with Ctrl+K")
        if palette_open:
            product.page.keyboard.type("mastery")
            product.page.wait_for_timeout(900)
            items = product.page.locator(".lc-palette-item").count()
            record(PASS if items > 0 else FAIL, "Command palette lists results",
                   f"items={items}")
            product.page.screenshot(path="scripts/_audit_12_palette.png")
            product.page.keyboard.press("Escape")

        # Teacher pulse / signals
        pulse = tpage.request.get(f"{base}/api/v1/teacher/pulse")
        record(PASS if pulse.status == 200 else FAIL, "API /api/v1/teacher/pulse",
               f"status={pulse.status}")
        signals = tpage.request.get(f"{base}/api/v1/teacher/signals")
        record(PASS if signals.status == 200 else FAIL, "API /api/v1/teacher/signals",
               f"status={signals.status}")

        browser.close()

    counts = {PASS: 0, FAIL: 0, WARN: 0}
    for status, _, _ in results:
        counts[status] += 1
    print("\n" + "=" * 70)
    print(f"E2E AUDIT SUMMARY: {counts[PASS]} passed, "
          f"{counts[FAIL]} failed, {counts[WARN]} warnings")
    print("=" * 70)
    for status, name, detail in results:
        if status == FAIL:
            print(f"  FAIL  {name} — {detail}")
    return 1 if counts[FAIL] else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://localhost:5000")
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args()
    sys.exit(run(args.base, args.headed))



