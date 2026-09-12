# LearnCraft

LearnCraft is an offline-first learning platform with a Flask backend, SQLite persistence, and server-rendered templates.

## Quick start

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python server.py
```

## Project structure

- `app/` — application package with core, API, services, repositories, models, and utilities
- `data/` — SQLite DB and seed assets
- `frontend/` — templates and static frontend assets
- `tests/` — unit, integration, and e2e tests
- `docs/` — architecture and API documentation
- `data/curriculum/` — versioned CBSE/NCERT structured seed packages
- `scripts/validate_content.py` — fail-fast content validation
- `scripts/import_content.py` — transactional catalog import
- `scripts/ingest_sources.py` — official-source download/checksum helper

## Notes

The project is intentionally built to stay compatible with the existing Flask application while exposing a more structured architecture for future expansion.
