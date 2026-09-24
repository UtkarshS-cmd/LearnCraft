# Offline-First Design

LearnCraft is designed to run primarily in offline mode. Main application data is stored locally in SQLite, while the UI remains available with local content and student progress.

Key principles:

- local first
- no remote dependency for core interactions
- resilient state sync queue
- future-ready network modes

## Security-relevant behavior (2026-09-24 audit)

- `sync_queue` rows record the authenticated `user_id`; `/api/sync/queue` is scoped to the
  signed-in user and a conflicting `event_id` can never adopt another account's row.
- `POST /logout` is the only sign-out method; the service worker purges its private page cache
  (`learncraft-private-v1`) during that round-trip.
- `GET /api/v1/questions` never returns answer keys (`answer`, `explanation`, `is_correct`);
  grading stays server-side via `/api/v1/quizzes/check`.
- Details: `docs/architecture/SECURITY_AUDIT.md` and root `OFFLINE_FIRST.md`.
