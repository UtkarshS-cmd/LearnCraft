"""Live HTTP smoke test: boots the real server and checks it over a socket.

This covers what the in-process test client cannot: static file serving, the
PWA manifest, the service worker route and cookie-based sessions over HTTPS-less
HTTP (exactly how a student device talks to the teacher's laptop).

Run with::

    python scripts/live_http_test.py
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = Path(tempfile.gettempdir()) / "learncraft_live_test.db"


def free_port() -> int:
    """Pick an unused loopback port so parallel runs never collide."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


PORT = free_port()
BASE = f"http://127.0.0.1:{PORT}"

STATIC_ASSETS = [
    "/static/css/design-system.css",
    "/static/css/app.css",
    "/static/js/app.js",
    "/static/js/offline-store.js",
    "/static/js/sandbox-engine.js",
    "/static/manifest.webmanifest",
    "/service-worker.js",
]

PUBLIC_PAGES = ["/login", "/register", "/offline"]


def request(opener, path, method="GET", payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with opener.open(req) as response:
            body = response.read().decode("utf-8", "replace")
            return response.status, body
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")
    except Exception as exc:  # noqa: BLE001 - network failures are test failures
        return None, str(exc)


def main() -> int:
    if DB.exists():
        DB.unlink()
    env = dict(os.environ, LEARNCRAFT_DB_PATH=str(DB), PYTHONPATH=str(ROOT))

    proc = subprocess.Popen(
        [sys.executable, "-c",
         "from app.main import create_app; app = create_app(); "
         f"app.run(host='127.0.0.1', port={PORT}, debug=False, use_reloader=False)"],
        cwd=str(ROOT), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    problems: list[str] = []
    try:
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
        for _ in range(60):
            status, _ = request(opener, "/api/health")
            if status == 200:
                break
            time.sleep(0.5)
        else:
            print("Server did not start on", BASE)
            return 1

        for path in PUBLIC_PAGES:
            status, _ = request(opener, path)
            if status != 200:
                problems.append(f"GET {path} -> {status}")

        for path in STATIC_ASSETS:
            status, body = request(opener, path)
            if status != 200 or not body.strip():
                problems.append(f"GET {path} -> {status} (empty body: {not body.strip()})")

        status, _ = request(opener, "/service-worker.js")
        if status != 200:
            problems.append(f"GET /service-worker.js -> {status}")

        # Cookie session round-trip.
        status, body = request(opener, "/auth/register", "POST", {
            "name": "Live Student", "email": "live.student@example.com",
            "password": "LiveTest123!", "account_type": "student",
        })
        if status not in (200, 201):
            problems.append(f"POST /auth/register -> {status}: {body[:120]}")

        for path in ("/home", "/subjects", "/notes", "/ask-ai", "/api/v1/dashboard"):
            status, body = request(opener, path)
            if status != 200:
                problems.append(f"[session] GET {path} -> {status}: {body[:120]}")

        status, body = request(opener, "/api/v1/ai/chat", "POST", {"message": "What is a prime number?"})
        if status != 200 or not json.loads(body).get("answer"):
            problems.append(f"POST /api/v1/ai/chat -> {status}")

        status, body = request(opener, "/api/v1/lessons")
        if status != 200 or not json.loads(body).get("items"):
            problems.append(f"GET /api/v1/lessons -> {status} (no lessons returned)")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()

    if problems:
        print("LIVE HTTP TEST FAILURES:")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    print(f"Live HTTP test passed: {len(STATIC_ASSETS)} assets, {len(PUBLIC_PAGES)} pages, session + APIs OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())