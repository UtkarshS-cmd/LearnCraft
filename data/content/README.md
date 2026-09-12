# LearnCraft Offline Content

This directory is the portable local content root for larger lesson media, simulation assets, and student file attachments.

- Keep asset references relative to the repository, for example `data/content/lessons/friction-43/diagram.png`.
- Structured metadata and progress live in `data/learncraft.db`.
- The local SQLite content catalog stores the relative `asset_path`; it never requires a cloud URL.
- Files can be copied with the LearnCraft workspace when moving the offline lab to another machine.
