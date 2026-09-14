# LearnCraft Offline-First Architecture

LearnCraft defaults to `OFFLINE`. Course content, lessons, sandbox state, practical work, assignments, notes, progress, and submissions work on the local machine without an Internet connection.

## Storage

- SQLite at `data/learncraft.db` stores structured content, notes, progress, submissions, and the sync queue.
- Larger media and student files belong under `data/content/` with repository-relative paths.
- Browser-side: IndexedDB (`learncraft_offline_db`, store: `sync_queue`) with `localStorage` fallback mirrors the pending sync queue in the browser for immediate durability.
- Notes use stable client IDs, timestamps, soft deletion, and `sync_status` so synchronization can be added without changing the student UI.

## Network Modes

Set `LEARNCRAFT_NETWORK_MODE` to one of:

- `OFFLINE` (default): local content and local progress only.
- `LOCAL_NETWORK`: a future Master Server may receive teacher assignments, submissions, lab status, and queued changes.
- `INTERNET`: reserved for a future optional capability and currently has no cloud implementation.

`LEARNCRAFT_MASTER_URL` is reserved for the future local Master Server address. Core routes never require it.

## Offline State Detection (Browser)

The browser-side runtime (`/static/js/offline-store.js`) uses a hybrid network state approach:

1. `navigator.onLine` to detect browser-declared network availability.
2. `window` `online`/`offline` events to react immediately when connectivity changes.
3. `/api/system/status` heartbeat probe (on page load and on `online` event) to confirm actual server reachability.
4. `document.visibilitychange` listener to retry drain when the tab becomes active.

The UI network pill reflects three states: **Offline Mode · Local**, **Server Unreachable · Local**, or **Local Network · Ready**.

## Local-First Persistence (Browser Queue)

All calls to `window.LearnCraftOffline.persist(kind, recordId, payload, state)`:

1. Immediately write an event to IndexedDB and `localStorage` (`learncraft_browser_queue`).
2. Assign a unique `event_id` (client-generated, format: `evt_{timestamp}_{random}`).
3. Store `kind`, `record_id`, `payload`, `status`, `created_at`, `seq`, `retry_count`, and `sync_status: LOCAL_BROWSER_QUEUE`.
4. Attempt a background queue drain if the server is reachable.

When offline, the action is durably persisted locally — **user work is never lost**.

## Three-Tier Queue

| Tier | Store | Meaning |
|---|---|---|
| `LOCAL_BROWSER_QUEUE` | IndexedDB + localStorage | Pending, not yet sent to server |
| `LOCAL_SERVER_QUEUE` | SQLite `sync_queue` (status=queued) | Received by server, pending future remote sync |
| `SYNCHRONIZED` | Removed from browser queue | Successfully acknowledged by `/api/local/state` |

## Sync on Reconnect

`LearnCraftOffline.drainQueue()` is triggered:
- On `window.online` event
- On `DOMContentLoaded` if server is reachable
- On `document.visibilitychange` when tab becomes active

The drain processes events sequentially (FIFO) to preserve ordering. On server acknowledgement (`HTTP 200`), the event is removed from the browser queue. On network failure, the drain halts and leaves remaining events for the next reconnect.

## Idempotency / Duplicate Prevention

- The browser assigns a stable `event_id` to each queued event.
- `/api/local/state` accepts the `event_id` and passes it to `enqueue_sync_event`.
- `enqueue_sync_event` uses `ON CONFLICT(event_id) DO UPDATE` in the `sync_queue` table.
- Retrying with the same `event_id` updates the existing row rather than inserting a duplicate.
- This prevents duplicate `sync_queue` entries when a server response is lost mid-flight.

## Boundaries

- `/api/system/status` — reports the active mode, storage backend, and local storage counts. Does not require authentication.
- `/api/content/catalog` — exposes the locally seeded subject and lesson catalog. Requires authentication.
- `/api/local/state` — records progress and submissions locally; bridges lesson progress to `learning_progress`; enqueues submissions into `sync_queue`. Requires authentication. Returns `401 JSON` (not redirect) for unauthenticated API calls.
- `/api/sync/queue` — exposes queued events for a future local-network sync worker. Requires authentication.
- `/service-worker.js` — served with `Content-Type: application/javascript` and `Service-Worker-Allowed: /` header. Registered with root scope `{ scope: '/' }` from `base.html`.
- `/offline` — navigation fallback page served by the service worker when offline.

## Service Worker

Cache name: `learncraft-shell-v2`

- **Install**: Pre-caches all shell assets and bundled sandbox files using `Promise.allSettled`-style per-asset caching — a missing asset does not break SW installation.
- **Activate**: Deletes all previous cache versions; claims clients.
- **Fetch (static assets `/static/`)**: Cache-first with background network revalidation.
- **Fetch (navigation)**: Network-first with `/offline` fallback when server is unreachable.
- **Never cached**: `/api/*` and `/auth/*` routes are explicitly excluded from SW caching.

## Bundled Sandboxes (Offline-Capable)

The following simulations are fully self-contained and work offline after a single online visit:

| Sandbox | Path | Offline Status |
|---|---|---|
| Math Adventure Lab | `/static/sandbox-games/math/index.html` | ✅ 100% Offline |
| Physics Adventure Lab | `/static/sandbox-games/physics/index.html` | ✅ 100% Offline |

Both are accessible from:
- `/sandbox` → "Bundled offline simulations" section (never disabled when offline)
- `/offline` → direct launch links

## External Simulations (Online-Only)

The following providers require an internet connection. They are correctly labelled `data-online-only` and are disabled when `navigator.onLine` is false:

- CodeCombat, Labster, GeoGebra, Desmos, PhET, NASA Interactives, NASA Aeronautics

When offline and an external simulation's runtime is open, the frame is cleared and an offline message is shown.

## Offline Learning Flows

| Flow | Offline Status | Implementation |
|---|---|---|
| Lesson progress (step through blocks) | ✅ Offline-capable | `localStorage` + `LearnCraftOffline.persist()` + IndexedDB queue |
| Practical workspace (code, save, submit) | ✅ Offline-capable | `localStorage` + `LearnCraftOffline.persist()` with submission kind |
| Assignment workspace (answers, submit) | ✅ Offline-capable | `localStorage` + `LearnCraftOffline.persist()` with submission kind |
| Notes (create, edit, pin, delete) | ⚠️ Server required | Notes use `/api/notes` which requires server; no offline notes queue yet |
| Math Adventure Lab (bundled sandbox) | ✅ Offline-capable | Self-contained; `localStorage` within sandbox |
| Physics Adventure Lab (bundled sandbox) | ✅ Offline-capable | Self-contained; `localStorage` within sandbox |
| External simulations (PhET, GeoGebra, etc.) | ❌ Online-only | Requires provider internet connectivity |

## Remote Sync

Remote/local-network synchronization is NOT implemented yet. The `sync_queue` table accumulates events for a future local-network sync worker. No remote sync is performed in any current code path.
