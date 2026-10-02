"""Report JS syntax errors per asset using the browser's own parser."""
from playwright.sync_api import sync_playwright

BASE = "http://localhost:5000"
ASSETS = ["/static/js/mastery-map.js", "/static/js/command-palette.js",
          "/static/js/notifications.js", "/static/js/app.js",
          "/static/js/offline-store.js", "/static/js/external-links.js",
          "/static/js/sandbox-engine.js"]

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    page = b.new_page()
    page.goto(BASE + "/login", wait_until="domcontentloaded")
    for asset in ASSETS:
        src = page.evaluate(
            "async (u) => { const r = await fetch(u); return r.ok ? r.text() : '__MISSING__'; }",
            asset)
        if src == "__MISSING__":
            print(f"{asset}: 404")
            continue
        res = page.evaluate(
            "(s) => { try { new Function(s); return 'OK'; } catch (e) { return e.name + ': ' + e.message; } }",
            src)
        print(f"{asset}: {res}")
        if res != "OK":
            lines = src.split("\n")
            print("    first 3 lines:", lines[:3])
    b.close()
