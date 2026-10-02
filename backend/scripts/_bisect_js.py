"""Binary-search the first line that introduces a JS syntax error."""
from playwright.sync_api import sync_playwright

PATH = r"e:\__007\Hackathon\LearnCraft\frontend\static\js\mastery-map.js"
src = open(PATH, encoding="utf-8").read()
lines = src.split("\n")

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    page = b.new_page()
    page.goto("about:blank")

    def classify(text):
        return page.evaluate(
            "(s) => { try { new Function(s); return 'OK'; }"
            " catch (e) { return /end of (input|data)/i.test(e.message)"
            " ? 'INCOMPLETE' : e.name + ': ' + e.message; } }",
            text)

    lo, hi = 1, len(lines)
    first_bad = None
    for mid in range(1, len(lines) + 1):
        verdict = classify("\n".join(lines[:mid]))
        if verdict not in ("OK", "INCOMPLETE"):
            first_bad = (mid, verdict)
            break

    print("total lines:", len(lines))
    if first_bad:
        print("first failing prefix ends at line", first_bad[0], "->", first_bad[1])
        start = max(0, first_bad[0] - 8)
        for idx in range(start, first_bad[0]):
            print(f"  {idx + 1:4d}: {lines[idx]}")
    else:
        print("full file verdict:", classify(src))
    b.close()
