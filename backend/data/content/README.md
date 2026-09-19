# LearnCraft Offline Content

Academic metadata is stored in `data/curriculum/*.json` and imported into the
versioned SQLite catalog. The current seed is CBSE Class X, academic year
2026-27, with one or two chapters per MVP subject. The seed is derived from
NCERT chapter structure and links back to the official NCERT textbook portal;
it is not a reproduction of textbook prose.

Validate and import:

```powershell
.venv\Scripts\python.exe scripts\validate_content.py
.venv\Scripts\python.exe scripts\import_content.py
```

Use `scripts\ingest_sources.py` only for publicly available official files.
Downloaded files are kept under `data/raw` and must be reviewed before
extraction into structured content.

This directory is the portable local content root for larger lesson media, simulation assets, and student file attachments.

- Keep asset references relative to the repository, for example `data/content/lessons/friction-43/diagram.png`.
- Structured metadata and progress live in `data/learncraft.db`.
- The local SQLite content catalog stores the relative `asset_path`; it never requires a cloud URL.
- Files can be copied with the LearnCraft workspace when moving the offline lab to another machine.
