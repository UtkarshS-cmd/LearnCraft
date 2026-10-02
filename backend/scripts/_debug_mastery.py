"""Debug the /mastery page: capture console errors and DOM state."""
from playwright.sync_api import sync_playwright

BASE = "http://localhost:5000"

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    page = b.new_page(viewport={"width": 1440, "height": 900})
    page.on("console", lambda m: print("CONSOLE:", m.type, m.text))
    page.on("pageerror", lambda e: print("PAGEERROR:", e))
    page.goto(f"{BASE}/login", wait_until="domcontentloaded")
    page.click("#registerTab")
    page.wait_for_timeout(300)
    import uuid
    page.fill("#registerName", "Map Debug")
    page.fill("#registerEmail", f"mapdebug{uuid.uuid4().hex[:6]}@example.com")
    page.fill("#registerPassword", "Str0ngPass!42")
    page.click("#registerSubmit")
    page.wait_for_timeout(2500)
    page.goto(f"{BASE}/mastery", wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    print("intro:", page.locator("#mapIntro").inner_text())
    print("nodes:", page.locator(".map-node").count())
    print("legend:", page.locator("#legend").inner_text()[:200])
    print("empty hidden:", page.locator("#mapEmpty").get_attribute("hidden"))
    page.screenshot(path="scripts/_debug_map.png", full_page=True)
    b.close()