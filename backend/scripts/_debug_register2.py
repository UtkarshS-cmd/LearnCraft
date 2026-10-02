"""Reproduce the e2e_audit.register() failure in isolation."""
import traceback
from playwright.sync_api import sync_playwright

BASE = "http://localhost:5000"


def register(page, base, email, password, account, name):
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


with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    page = b.new_page()
    try:
        url = register(page, BASE, "debug_reg_iso@learncraft.test", "Str0ngPass!42",
                       "student", "Iso Student")
        print("returned url:", repr(url))
        print("in check:", "/login" not in url)
    except Exception:
        traceback.print_exc()
    b.close()
