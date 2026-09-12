# LearnCraft Offline-First Architecture

LearnCraft defaults to `OFFLINE`. Course content, lessons, sandbox state, practical work, assignments, notes, progress, and submissions work on the local machine without an Internet connection.

## Storage

- SQLite at `data/learncraft.db` stores structured content, notes, progress, submissions, and the future sync queue.
- Larger media and student files belong under `data/content/` with repository-relative paths.
- Browser localStorage remains an immediate UI cache for interactive work; the shared client boundary also mirrors durable progress and submissions into SQLite.
- Notes use stable client IDs, timestamps, soft deletion, and `sync_status` so synchronization can be added without changing the student UI.

## Network modes

Set `LEARNCRAFT_NETWORK_MODE` to one of:

- `OFFLINE` (default): local content and local progress only.
- `LOCAL_NETWORK`: a future Master Server may receive teacher assignments, submissions, lab status, and queued changes.
- `INTERNET`: reserved for a future optional capability and currently has no cloud implementation.

`LEARNCRAFT_MASTER_URL` is reserved for the future local Master Server address. Core routes never require it.

## Boundaries

- `/api/system/status` reports the active mode and local storage counts.
- `/api/content/catalog` exposes the locally seeded subject and lesson catalog.
- `/api/local/state` records progress and submissions locally.
- `/api/sync/queue` exposes queued events for a future local-network sync worker; no remote sync is performed yet.

This keeps offline work usable first and makes local-network synchronization an additive transport rather than a requirement of the student experience.
