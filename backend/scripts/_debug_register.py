"""Debug the /login registration flow interactively (screenshots + DOM dump)."""
from playwright.sync_api import sync_playwright

BASE = "http://localhost:5000"

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    page = b.new_page(viewport={"width": 1440, "height": 900})
    page.on("console", lambda m: print("CONSOLE:", m.type, m.text))
    page.on("response", lambda r: print("RESP:", r.status, r.url) if "/auth/" in r.url else None)
    page.goto(f"{BASE}/login", wait_until="domcontentloaded")
    page.wait_for_timeout(500)
    print("registerTab visible:", page.locator("#registerTab").is_visible())
    page.click("#registerTab")
    page.wait_for_timeout(300)
    print("registerForm active:", page.locator("#registerForm").is_visible())
    page.fill("#registerName", "Debug User")
    page.fill("#registerEmail", "debug_user_zz@learncraft.test")
    page.fill("#registerPassword", "Str0ngPass!42")
    page.screenshot(path="scripts/_debug_reg_before.png")
    page.click("#registerSubmit")
    page.wait_for_timeout(3000)
    print("URL after submit:", page.url)
    print("registerStatus:", page.locator("#registerStatus").inner_text())
    print("loginStatus:", page.locator("#loginStatus").inner_text())
    page.screenshot(path="scripts/_debug_reg_after.png", full_page=True)
    b.close()
