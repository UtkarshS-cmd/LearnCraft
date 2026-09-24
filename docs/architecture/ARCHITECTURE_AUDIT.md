# LearnCraft — Architecture Audit (Phase 1)

Date: 2026-09-21. Scope: existing LearnCraft repo (Flask + SQLite + Jinja, offline-first).
Companions: TARGET_ARCHITECTURE.md, EXTERNAL_LEARNING_ECOSYSTEM.md.

## 1. Repository map (actual)

- backend/server.py -> app.main:app; app/main.py (~1189 lines: pages + /auth/* + /api/notes + /api/content + /api/sync + /api/local).
- backend/app/api/v1/: auth, ai, curriculum, subjects, lessons, quizzes, progress, dashboard, users (teacher-only), teacher.
- backend/app/{core,database,models,repositories,routes,schemas,services,utils}.
- services: ai_tutor.py (cloud + Ollama + LM Studio + built-in retrieval tutor), content_catalog.py (legacy curriculum JSON -> academic_* tables), curriculum_pipeline.py (versioned class<N> packages, concept graph, roadmap, question bank), teacher_control.py, auth_service.py, password_reset.py.
- backend/data/curriculum/: mathematics/science/social-science.json + class10/{manifest,concept_graph,question_bank (15MB),roadmap,simulation_registry}.json + ncert_class10_syllabus.json.
- frontend/templates + static/js (app, offline-store IndexedDB queue, sandbox-engine, service-worker learncraft-shell-v4 + learncraft-private-v1 page cache) + sandbox-games/{math,physics,circuits,coding}.
- docker/, run_server.bat/ps1, backend/scripts/* validation + tests/* (31 tests).

## 2. Per-system audit

Frontend (Jinja + vanilla JS): server-rendered shell, sidebar NAV from seed mock_data, offline pill, notifications bell. Strength: zero build, fully offline shell. Debt: all pages in main.py god-module; routes/ is a stub; DOM-only search.
Backend (Flask monolith + blueprints): simple runners, HttpOnly SameSite=Lax sessions. Debt: god-module main.py; middleware imports current_user from main (cycle risk); duplicate app/config vs app/core/config; create_app returns global (no factory isolation).
Database (SQLite, connection.py ~880 lines): WAL + FK, CREATE TABLE IF NOT EXISTS (~30 tables), _transaction helper, idempotent sync_queue ON CONFLICT(event_id). No migrations (additive guards via PRAGMA). Keep SQLite; avoid leaking SQLite SQL into services.
Auth (STUDENT/TEACHER/ADMIN): AuthService shared by HTML + JSON logins, password policy 8+upper+lower+digit+special, validate_portal, session.clear on login, OTP hashed 10-min + offline direct-reset fallback. Gaps: no rate limit; users.role free text. (GET /logout was state-changing — fixed 2026-09-24: POST-only plus a same-origin Origin/Referer guard on all write methods.)
AI tutor (ai_tutor.py ~766 lines): AIService{cloud OpenAI-compat, Ollama autodetect + embedding-model filter + thinking-strip, LM Studio, offline retrieval tutor}; env LEARNCRAFT_AI_MODE/AUTO|ONLINE|OFFLINE; retrieve_context with provenance (source_id, content_version, chapter_id, topic_id); per-user conversations. Gap: no app/ai/ package, keyword retrieval only, no learner memory.
Curriculum: dual loader (legacy content_catalog -> academic_* DB + canonical curriculum_pipeline class<N> packages). CBSE IX/X production dataset. Debt: CBSE constants hardcoded; class9 has no class9/ dir; 15MB bank loaded per filter (cached partly).
Concept graph: build_concept_graph + validate (missing refs, dupes, cycles). Gap: no mastery join, no API validation tests.
Roadmap: derived from graph (build_roadmap_for_class). Gap: no mastery/goals/WHY reasons.
Questions/quizzes: pipeline bank (verified filter, answers gated by session) + academic DB quizzes/check (MCQ exact + numeric tolerance). Gap: check() full-scans list_questions.
Progress: learning_progress + /api/v1/progress + /api/v1/events allowlist; dashboard snapshot; teacher activity_events. Gap: no mastery model / spaced repetition.
Teacher: classes/members/access_rules (ENABLED/DISABLED/LOCKED/ASSIGNED_ONLY)/assignments fan-out/announcements/analytics+CSV/notifications/audit. Strict ownership checks. Gap: no weak-concept analytics.
Notes: SQLite CRUD + pin + soft delete + seed, /notes page + /api/notes, Ask-AI Save-to-Notes. Gap: no tags/concept links, server-required (no offline queue).
Offline/sync: LEARNCRAFT_NETWORK_MODE OFFLINE default; 3-tier queue (browser IndexedDB+LS -> SQLite sync_queue -> future remote); /api/system/status, /api/content/catalog, /api/local/state, /api/sync/queue; SW precache + static cache-first + nav network-first -> /offline. Remote worker intentionally absent.
Simulations: bundled offline labs (math/physics/circuits/coding) + registry + online-only providers gated data-online-only. /sandbox + /student/simulation/<id> with access check.
Tests: pytest backend/tests (31) + validate_content + smoke + route_sweep + functional + live_http + check_assets.
Docker: py3.11-slim gunicorn 4 workers; compose persists backend/data + frontend mount; secret via env (fails fast).



## 3. Findings

Critical (fix first): (1) test_app_structure expects backend/frontend but repo uses root/frontend - fix test root. (2) smoke_test expects student GET /api/v1/users 200 but teacher-only 403 is correct - fix script. (3) main.py god-module - extract blueprints without URL changes.
Debt: duplicate config; create_app not a factory; routes stub; repos only users; 15MB bank sync load (API limit<=200 already); check_assets ROOT bug (scans backend/frontend, always passes).
Security: hashing/policy/OTP/sessions/SQL/Jinja OK. Watch: next= redirects, SSRF/embeds (new validator: HTTPS + allowlist, reject javascript/data/file/localhost), no rate limit, AI injection (registry URLs only). No secrets committed. (2026-09-24 audit pass: /logout POST-only; same-origin Origin/Referer guard on writes; /api/v1/questions answers stripped; sync queue per-user; Werkzeug debugger env opt-in — see SECURITY_AUDIT.md §9.)


## 4. CURRENT -> TRANSITION -> TARGET

CURRENT: monolith main.py, single connection.py, Jinja shell, SQLite, hybrid AI, dual curriculum loaders, static roadmap.
TRANSITION (after this pass): resources blueprint + service + registry + seed; /resources hub + context widgets + bookmarks + activity + teacher CRUD + URL validation; docs + green tests.
TARGET: routes/ blueprints, repos per aggregate, services/learning mastery, app/ai orchestrator+memory+rag, smart notes, adaptive tests, teacher analytics, sim interface, gamification, learner profile; React only after contracts freeze.

## 5. Preserve / refactor / add

Preserve: Flask/SQLite/offline-first, auth+roles, curriculum+graph+roadmap, bank+grading+gating, progress/events, teacher controls, notes, sync+SW, bundled sims, Docker, AI hybrid Ollama-first.
Refactor: [DONE] fix app_structure root, smoke assertion, check_assets/check_routes root, base.html is_teacher guards. Remaining: thin main.py, dedupe config.
Add now: [DONE] Ecosystem P0-P1 + safe P2 (Obsidian deep links, Notion adapter seam, Anki export, GitHub validate). Later: P3 OAuth/sync, P4 AI recommendations + mastery roadmap.

## 6. P0-P4 plan

P0: test/script fixes, registry, model+migration, catalog APIs, hub UI, URL validation, official seed.
P1: context linking, bookmark+status, activity (opened!=completed), teacher verify, search/filter, graph validation tests.
P2: Obsidian builder + vault settings, Notion interface, Anki hook, GitHub link, YouTube nocookie guard, registry AI suggestions.
P3: OAuth, advanced sync, adaptive weights, mastery reasons. P4: community/competitive/portfolio/projects/interview/career/college interfaces only.

## 7. Tests 2026-09-21 (final after Phase 2)

`pytest backend/tests`: **44 passed, 4 subtests passed** (was 30 passed / 1 failed — the stale path test is fixed).
`validate_content.py`: pass (3 subjects, 6 chapters). `smoke_test.py`: pass (17 pages, 6 APIs).
`route_sweep.py`: pass (180 requests, no 5xx/unexpected). `functional_test.py`: pass. `live_http_test.py`: pass (7 assets, 3 pages).
`check_assets.py`: pass (24 references resolved — ROOT bug fixed, previously scanned nothing).
Fixed during Phase 2: `tests/unit/test_app_structure.py` root path, `scripts/smoke_test.py` stale teacher-only 403 assertion,
`scripts/check_assets.py` + `scripts/check_routes.py` frontend ROOT fallback, `check_routes.py` concatenated-fetch matching,
`base.html` `is_teacher` undefined-safe guards, `shell_ctx` no longer emits `is_teacher=False`.
Additive migration verified against a copy of the live dev DB: 3 new tables + 9 seed rows, 20 users and 4 notes untouched.

## 8. Next (P2 remainder → P3)

Done in P2: Obsidian client deep links + vault settings, server `obsidian_uri` builder, Notion L1/L2 adapter seam,
Anki TSV export, GitHub repo validation seam, adapter status endpoint, offline precache of the link helper, AI registry grounding.
Next: learner profile + mastery engine (`services/learning/`), then AI orchestrator/RAG/memory so resource
recommendations become mastery- and goal-aware; OAuth (Notion/Drive) and external progress sync remain P3.

## 9. Security / integration / UX audit pass (2026-09-24)

Full report: `docs/architecture/SECURITY_AUDIT.md`. Fixed: `/api/v1/questions` answer-key leak (P0);
per-user `sync_queue` ownership incl. server-forced `user_id` and scoped `/api/sync/queue` (P1);
POST-only `/logout` + same-origin Origin/Referer guard on all write methods (P1); service worker
private page cache (`learncraft-private-v1`) purged on logout, auth pages never cached (P2);
Werkzeug debugger now `FLASK_DEBUG` opt-in instead of `debug=True` on `0.0.0.0` (P2); `.gitignore`
covers scratch probes/snapshots (P4). Verified non-findings: password-reset OTP flow, teacher-route
ownership scoping, session-scoped quiz answer gating, server-authoritative grading.

Tests: `pytest backend/tests -q` -> 60 passed + 4 subtests (was 52 + 4; +8 regression tests in
`tests/integration/test_security_fixes.py`). `smoke_test.py` -> 17 pages / 6 APIs pass.
`route_sweep.py` -> 180 requests, no 5xx/unexpected statuses.
