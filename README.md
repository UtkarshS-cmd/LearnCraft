# LearnCraft

LearnCraft is an offline-first learning platform with a Flask backend, SQLite persistence, and server-rendered templates.

## Quick start

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python server.py
```

## Desktop application

Run the same local-first application in an app-style browser window:

```powershell
.venv\Scripts\python.exe desktop.py
```

The launcher selects an available loopback port, starts the Flask server
without the debug reloader, and opens Microsoft Edge or Chrome in app mode.
If neither browser is installed, it opens the default browser instead. Stop
the desktop application with `Ctrl+C`.

## Password reset (offline, no OTP needed)

On an incorrect login, users can set a new password directly from the "Forgot password?" link — email + new password, no OTP code required. The app works fully offline without SMTP. Optionally configure SMTP to also email a one-time code (best-effort); a direct reset always works as fallback:

```powershell
$env:LEARNCRAFT_MAIL_HOST = "smtp.example.com"
$env:LEARNCRAFT_MAIL_PORT = "587"
$env:LEARNCRAFT_MAIL_USERNAME = "smtp-user"
$env:LEARNCRAFT_MAIL_PASSWORD = "smtp-password"
$env:LEARNCRAFT_MAIL_FROM = "no-reply@example.com"
```

When an OTP is emailed, it expires after 10 minutes and is stored only as a hash. Direct (OTP-free) resets are always available offline.

## Project structure

- `app/` — application package with core, API, services, repositories, models, and utilities
- `data/` — SQLite DB and seed assets
- `frontend/` — templates and static frontend assets
- `frontend/static/sandbox-games/circuits/` — bundled offline electrical circuits lab integrated from the Simulations project
- `frontend/static/sandbox-games/coding/` — bundled offline Coding Adventure with guided JavaScript missions
- `tests/` — unit, integration, and e2e tests
- `docs/` — architecture and API documentation
- `data/curriculum/` — versioned CBSE/NCERT structured seed packages
- `data/curriculum/ncert_class10_syllabus.json` — extracted Class 10 NCERT Science and Social Studies question bank used by Ask AI for exact offline answers
- `scripts/validate_content.py` — fail-fast content validation
- `scripts/import_content.py` — transactional catalog import
- `scripts/ingest_sources.py` — official-source download/checksum helper
- `scripts/smoke_test.py` — boots the app and checks every page and read API
- `scripts/route_sweep.py` — hits every registered route as anonymous, student and teacher
- `scripts/functional_test.py` — exercises every write endpoint (student + teacher flows)
- `scripts/live_http_test.py` — starts a real server process and tests it over HTTP
- `scripts/check_assets.py` — flags `/static/...` references that do not exist on disk

## Verification

Run these before shipping a change. Each script exits non-zero on failure.

```powershell
.venv\Scripts\python.exe -m pytest tests -q
.venv\Scripts\python.exe scripts\validate_content.py
.venv\Scripts\python.exe scripts\smoke_test.py
.venv\Scripts\python.exe scripts\route_sweep.py
.venv\Scripts\python.exe scripts\functional_test.py
.venv\Scripts\python.exe scripts\live_http_test.py
.venv\Scripts\python.exe scripts\check_assets.py
```

## Notes

The project is intentionally built to stay compatible with the existing Flask application while exposing a more structured architecture for future expansion.
