# LearnCraft

LearnCraft is an offline-first learning platform with a Flask backend, SQLite persistence, and server-rendered templates.

## Quick start

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python server.py
```

## Password reset email

On an incorrect login, users can request a six-digit OTP from the "Forgot password?" link. Configure SMTP before deploying:

```powershell
$env:LEARNCRAFT_MAIL_HOST = "smtp.example.com"
$env:LEARNCRAFT_MAIL_PORT = "587"
$env:LEARNCRAFT_MAIL_USERNAME = "smtp-user"
$env:LEARNCRAFT_MAIL_PASSWORD = "smtp-password"
$env:LEARNCRAFT_MAIL_FROM = "no-reply@example.com"
```

The OTP expires after 10 minutes and is stored only as a hash. In tests, email delivery is suppressed and the generated OTP is logged.

## Project structure

- `app/` — application package with core, API, services, repositories, models, and utilities
- `data/` — SQLite DB and seed assets
- `frontend/` — templates and static frontend assets
- `tests/` — unit, integration, and e2e tests
- `docs/` — architecture and API documentation
- `data/curriculum/` — versioned CBSE/NCERT structured seed packages
- `data/curriculum/ncert_class10_syllabus.json` — extracted Class 10 NCERT Science and Social Studies question bank used by Ask AI for exact offline answers
- `scripts/validate_content.py` — fail-fast content validation
- `scripts/import_content.py` — transactional catalog import
- `scripts/ingest_sources.py` — official-source download/checksum helper

## Notes

The project is intentionally built to stay compatible with the existing Flask application while exposing a more structured architecture for future expansion.
