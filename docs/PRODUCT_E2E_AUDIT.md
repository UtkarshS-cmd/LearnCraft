# LearnCraft — Product E2E Audit

> Real-browser + API audit performed against `http://localhost:5000` with Playwright
> (Chromium) and the backend test client. Re-run any time with:
>
> ```powershell
> cd backend
> .venv\Scripts\python.exe -m pytest tests -q            # API/regression suite
> E:\__007\Playrwright with python\venv\Scripts\python.exe scripts\e2e_audit.py
> ```
>
> Severity legend: **P0** blocks core functionality / security / data integrity ·
> **P1** major user journey broken · **P2** important product-quality issue ·
> **P3** polish.

## 1. Audit method

The audit walks the real product the way a user does:

1. Register student through the actual `/login` form (UI, not API).
2. Visit every nav route (`/home /my-learning /subjects /resources /tests
   /practical /assignments /sandbox /progress /notes /ask-ai /profile /settings /help`).
3. Open a subject → open a lesson player → verify stage rail.
4. Open `/tests`, verify quiz questions render.
5. Probe every student API used by the UI (`/api/v1/dashboard`,
   `/mastery`, `/learning/next`, `/gamification`, `/progress`, `/assignments`,
   `/announcements`, `/ai/status`).
6. Register a teacher in a **separate browser context**, open `/teacher`,
   create a class, approve join requests, create an assignment.
7. Verify the **student** receives the assignment (two-user relationship test).
8. Collect console errors and failed network requests across the session.

Current score: **40 passed, 0 failed, 0 warnings** (`backend/scripts/_audit_report.txt`).

## 2. Issues found and fixed

### P1 — Students who registered before the teacher never appeared in the approval queue

- **Files:** `backend/app/services/teacher_control.py`,
  `backend/app/main.py` (`/auth/register`), `backend/app/api/v1/auth.py`.
- **Reproduction:** register a student first (no teachers exist yet) → register a
  teacher → create a class → *Join requests* is empty → the student can never be
  added to the class except by typing their raw numeric ID. The assignment
  created for the class therefore reached **0 students** (E2E:
  `Student receives assignment — count=0`).
- **Root cause:** `enqueue_student_join_requests()` runs only when a *student*
  registers, so the join-request row is never created for teachers that come
  later. The two registration orders behaved differently.
- **Fix:**
  - `enqueue_existing_students_for_teacher(teacher_id)` backfills one PENDING
    request per existing student when a teacher/admin account is created
    (idempotent via `INSERT OR IGNORE`, skips students already connected).
  - `create_class()` binds this teacher's still-`class_id IS NULL` pending
    requests to the newly created class, so the queue shows where each student
    will land.
  - Wired into both registration endpoints (`/auth/register` and
    `/api/v1/auth/register`).
- **Verified:** E2E run approves 27/27 requests and the student receives
  `E2E Homework` (`count=1`); `125 passed` backend tests still green.

### P1 — Teacher E2E was sharing the student session (test-harness defect)

- The first audit run reused one browser context for both personas; an
  authenticated `/login` redirects to `/home`, so the teacher form never
  appeared (`#registerTab` timeout) and every teacher API answered 403.
- **Fix:** the audit now opens a second `browser.new_context()` for the teacher.

### P2 — Quiz rendering check used the wrong selector

- The quiz cards are `.quiz-card` with `data-question-id`; the audit's first
  selector (`.question`) matched nothing and falsely reported "0 questions".
  The product itself was fine — selector corrected in `scripts/e2e_audit.py`.

### P2 — Aborted requests misreported as failures

- SPA-style polling (`setInterval` in `base.html` / `home.html`) is aborted on
  navigation (`net::ERR_ABORTED`), which is normal browser behaviour, not a
  failure. The audit now excludes `ERR_ABORTED` from the failed-request score.

## 3. Known issues not yet fixed (tracked for the product layer)

| # | Sev | Issue | Where |
|---|-----|-------|-------|
| 1 | P2 | No loading/empty/error state on most async UI panels (bell notifications, today-work rail silently `catch(){}` and keep stale content). | `frontend/templates/base.html`, `pages/home.html` |
| 2 | P2 | Notification bell stores "seen" state in `localStorage` only — no persistent, server-side, per-user notification centre. | `frontend/templates/base.html` |
| 3 | P2 | Adaptive recommendation exists (`/api/v1/learning/next`) but the UI shows only one opaque line — no "why" breakdown, no action buttons. | `app/services/adaptive.py`, `pages/profile.html` |
| 4 | P2 | No application-wide search and no command palette. | frontend |
| 5 | P2 | Concept mastery has a rich backend (`concept_mastery`, `score_row`) but zero visualisation / drill-down UI. | backend + frontend |
| 6 | P2 | Teacher dashboard shows raw KPIs but no neutral early-warning signals with evidence, no class pulse drill-down. | `teacher_control.dashboard_snapshot` |
| 7 | P2 | Assignment results are not analysed (struggled concepts, common wrong answers, mastery change). | missing service |
| 8 | P3 | Hinglish copy in English product surfaces (`"Jab teacher tumhare class ko assignment bhejega..."`). | `pages/assignments.html` |
| 9 | P3 | `notes` API has no GET endpoint (listing is server-rendered only) — blocks a unified search/PA. | `app/main.py` |
| 10 | P2 | `content_manifests` exists but there is no pack lifecycle UI (downloading / outdated / partial). | `api/v1/subjects.py` |

## 4. Regression gates

- `backend/.venv/Scripts/python.exe -m pytest tests -q` → **125 passed**.
- `backend/scripts/e2e_audit.py` → **40 passed, 0 failed**.
- Both must stay green after every change in the product layer.
