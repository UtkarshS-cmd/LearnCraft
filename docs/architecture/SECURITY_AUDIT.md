# LearnCraft — Security / Integration / UX Audit (Phase 1)

Date: 2026-09-24. Scope: the offline-first Flask app at `LearnCraft/` (backend `app/main.py` +
`app/api/v1/*`, services, SQLite session/queue layer, frontend Jinja shell + service worker).
Method: targeted code reading across every auth/teacher/quiz/queue route, live reproduction with
the Flask test client, then minimal fixes plus regression tests. No architectural redesign: Flask +
SQLite + session auth + IndexedDB/SW offline queue and server-authoritative grading are preserved.

## Findings

### P0 — `GET /api/v1/questions` exposed the answer key

- Files: `backend/app/api/v1/subjects.py` (route) and `backend/app/services/content_catalog.py`
  (`list_questions` → `SELECT q.*` plus `academic_question_options.is_correct`).
- Reproduction: `curl "http://localhost:5000/api/v1/questions?subject=science"` returned each item
  with `answer`, `explanation` and per-option `is_correct` — the raw `academic_questions` row.
- Expected: the public feed is for rendering/practice and must never carry solutions; grading is
  server-authoritative via `/api/v1/quizzes/check` (the quiz `question-bank` endpoint was already
  answer-gated per session, and the `/tests` page was already stripped server-side).
- Actual: any client (route requires no auth) could read every answer, defeating grading and the
  offline "practice first" flow.
- Fix: `_public_question()` projection in `subjects.py` — drops `answer`, `explanation`,
  `correct_answer`, `correct_option_id`, `is_correct` at question level and `is_correct` per option,
  keeping `question_id`, `prompt`, `options[{option_id, option_text}]`, `source_reference`, etc.
  The frontend never consumed the stripped fields (repo-wide grep for `is_correct` under
  `frontend/`: zero hits; `pages/tests.html` already rendered only `option_id`/`option_text`).
- Regression tests: `test_question_feed_strips_solution_fields`,
  `test_public_question_helper_strips_synthetic_solution`.

### P1 — Sync queue had no ownership: client-trusted `user_id` + cross-account reads

- Files: `backend/app/main.py` (`/api/local/state` record handling, `/api/sync/queue`) and
  `backend/app/database/connection.py` (`sync_queue` schema, `enqueue_sync_event`).
- Reproduction: (1) `POST /api/local/state` with `payload.user_id = 999999` stored the spoofed id
  verbatim (the code only defaulted `record["user_id"]` when absent — it never overrode a supplied
  one). (2) `GET /api/sync/queue` had no `user_id` filter, so a signed-in student received every
  other account's queued events (payloads can include submission bodies).
- Expected: identity is server-authoritative; queued events are private per account and ready for
  the future LAN sync worker.
- Actual: spoofed ownership was persisted, and queued events of all users were disclosed.
- Fix: `record["user_id"]` is forced to the session user; `sync_queue` gained a `user_id` column
  via additive `PRAGMA table_info` migration (plus `idx_sync_queue_user` index);
  `enqueue_sync_event(..., user_id=...)` records the owner and its `ON CONFLICT(event_id) DO UPDATE`
  carries `WHERE sync_queue.user_id IS NULL OR sync_queue.user_id = excluded.user_id` with
  `user_id=COALESCE(...)`, so a conflicting `event_id` from another account can neither adopt nor
  overwrite an existing row; `/api/sync/queue` filters `WHERE status='queued' AND user_id = ?`.
  Legacy rows with `NULL` owner stay hidden (documented in `OFFLINE_FIRST.md`).
- Regression tests: `test_sync_queue_is_scoped_to_the_session_user`,
  `test_queued_events_record_the_session_owner`.

### P1 — `GET /logout` was a state change and no write route checked its origin

- Files: `backend/app/main.py` (`@app.route("/logout")`), templates `base.html` (×2),
  `pages/settings.html`, `teacher_dashboard.html`.
- Reproduction: an `<img src="http://localhost:5000/logout">` on any page signed the user out
  (classic logout CSRF); write endpoints accepted requests with `Origin: http://evil.example`.
- Expected: sign-out only via an intentional same-origin POST; cross-origin writes rejected.
- Actual: GET performed the sign-out; no Origin/Referer validation existed on any POST/PUT route.
- Fix: `/logout` is `@app.post` only (GET → 405), all four sign-out links became real POST forms
  (or JS-submitted hidden forms, so styling is unchanged), and a `before_request`
  `verify_same_origin_write()` guard rejects `POST/PUT/PATCH/DELETE` whose `Origin` (else `Referer`)
  host:port differs from `request.host` with `403 CSRF_BLOCKED`. `SameSite=Lax` already withheld
  cookies cross-site; this is defense-in-depth against legacy browsers, laxity carve-outs and any
  future cookie-attribute change. Requests without either header (test client, curl, local scripts,
  the e2e harness) behave like same-origin browser traffic and stay allowed.
### P2 — Service worker stored authenticated pages and never purged them on sign-out

- File: `frontend/static/js/service-worker.js` (v3) + `frontend/templates/base.html`.
- Reproduction: browse `/home` while signed in, sign out, go offline, then open `/home` — the
  navigation fallback served the cached authenticated HTML of the previous session (including the
  user's name/avatar and last-viewed pages on a shared classroom device).
- Expected: offline replay is a core offline-first feature for *content*, but private HTML must not
  outlive the session that rendered it.
- Actual: navigation responses were written into the shared asset cache `learncraft-shell-v3`,
  which `activate` only clears on a *version bump*, never on logout.
- Fix (still offline-first): cache split — `learncraft-shell-v4` keeps only public assets, while
  visited pages go to `learncraft-private-v1`; `/login`, `/register` and `/auth/*` pages (including
  redirect targets) are never cached; the SW intercepts `POST /logout` and `POST /auth/logout`,
  forwards the request, then deletes the private cache so a signed-out device cannot replay another
  account's pages; the `/home` navigation fallback was removed (fallback chain: exact page →
  `/offline` → inline minimal shell). IndexedDB/localStorage queued work is untouched by design —
  purging it would destroy unsynced student work (accepted limitation below).
- Regression tests: `test_service_worker_purges_private_pages_on_logout`; the existing offline test
  now asserts `learncraft-shell-v4`. Docs updated: `OFFLINE_FIRST.md` (SW + queue + boundaries),
  `docs/integrations/external-learning.md`, this file.

### P2 — Werkzeug debugger was enabled on a LAN-bound server

- File: `backend/app/main.py` (`app.run(host="0.0.0.0", port=5000, debug=True)`).
- Reproduction: any unhandled exception exposed the Werkzeug interactive debugger console to every
  host on the LAN, where the PIN can be brute-forced — effectively remote code execution.
- Expected: debug mode opt-in per deployment.
- Fix: `debug=os.environ.get("FLASK_DEBUG", "0") in {1,true,yes,on}` — off by default, unchanged
  behaviour for developers who export `FLASK_DEBUG=1`. Regression test:
  `test_werkzeug_debugger_is_opt_in`.

### P3 — No CSRF token framework (accepted, documented)

Sessionless token plumbing was deliberately not added (high-risk refactor of every template/form).
Current posture: `SameSite=Lax` cookies + the new same-origin write guard + POST-only logout. If
LearnCraft is ever embedded/iframed or cookie attributes relax, add per-session CSRF tokens before
that ships.

### P4 — Repository hygiene

- Working tree contained scratch artifacts: `temp_test`, `register_dbclient_connection.{py,cmd}`,
  `_snap_cc.txt`, `_tmp_cc_snapshot.py`, `_tmp_catalog_snapshot.py`, `_mid2.txt`,
  `_state_report.txt` (root) and `backend/_snap_cc.txt`, `_tmp_cc_snapshot.py`, `_mid2.txt`,
  `_state_report.txt`, `vp.py`, etc.
- Fix: `.gitignore` now covers `temp_test`, `register_dbclient_connection.*`, `_snap_*`, `_tmp_*`,
  `_mid*.txt`, `_state_report.txt`, `backend/logs/`, `*.log`. If any of these are already tracked,
  run `git rm --cached <path>` (or delete them) — `.gitignore` alone does not untrack.
  `backend/_e2e_verify.py` is intentionally kept (live-server E2E harness).

## Verified non-findings (checked, no change needed)

- Password reset: OTP is hashed at rest, single-use, 10-minute expiry, consumed server-side.
- Teacher routes: classes/members/assignments/analytics are ownership-scoped by `teacher_id`.
- Quiz `question-bank` pipeline: answers are gated per session; `quizzes/check` grades
  server-side (MCQ exact + numeric tolerance).
- Session config: `HttpOnly` + `SameSite=Lax`; secret key is mandatory outside
  offline/testing mode (`FATAL: LEARNCRAFT_SECRET_KEY must be set…`).
- `/tests` page and `/api/v1/quizzes` already projected answer-free option payloads.

## Verification matrix (2026-09-24, after fixes)

| Check | Result |
|---|---|
| `pytest backend/tests -q` | **60 passed, 4 subtests passed** (baseline 52+4; +8 new regression tests) |
| `scripts/smoke_test.py` | passed — 17 pages, 6 APIs |
| `scripts/route_sweep.py` | passed — 180 requests, no 5xx / unexpected statuses |
| `scripts/functional_test.py` | passed (see follow-up run note below) |
| `scripts/check_assets.py` | passed — asset references resolved |
| Manual repro checks | cross-origin POST → 403 `CSRF_BLOCKED`; `GET /logout` → 405; question feed carries no `answer`/`is_correct`; second account's `/api/sync/queue` omits the first account's events |

## Accepted limitations / follow-ups

1. Shared-device IndexedDB (`learncraft_offline_db`) still holds queued work after logout — purging
   it would delete unsynced student work; scope it per user id in a future pass.
2. Legacy `sync_queue` rows with `NULL` owner remain invisible to `/api/sync/queue`; a one-off
   backfill is safe once the owner mapping exists.
3. No rate limiting on auth endpoints (unchanged from the previous audit).
4. `main.py` remains a god-module; blueprint extraction stays on the refactor roadmap.

