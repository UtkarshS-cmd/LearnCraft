# Database Overview

LearnCraft uses SQLite as the default storage backend. The database is initialized via `database.initialize_database()` in the root application and is configurable through the `LEARNCRAFT_DB_PATH` environment variable.

The main tables include:

- `users`
- `user_profiles`
- `learning_progress`
- `notes`
- `content_items`
- `local_progress`
- `local_submissions`
- `sync_queue`

This keeps the platform offline-first while allowing local synchronization hooks for future work.
