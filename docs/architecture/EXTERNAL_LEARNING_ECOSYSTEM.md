# External Learning Ecosystem — architecture (Phase 1 audit + Phases 2+ plan)

Status: **P0, P1 and the safe half of P2 implemented.** Registry, model, catalog, hub, context links, bookmarks, activity, teacher CRUD/verify, URL validation, Obsidian deep links, Notion adapter seam, Anki TSV export, GitHub repo validation. P3 (OAuth, Drive sync, external progress sync) and P4 (mastery-weighted recommendations, cross-platform analytics) remain documented-only.

## External resource model (built)

Tables (additive, `CREATE TABLE IF NOT EXISTS`, no migration needed): `external_resources`, `resource_bookmarks`, `resource_activity`.
Fields: id, provider, resource_type, title, description, url, subject, class_level, chapter, topic, concept_ids_json, language, difficulty, is_official, requires_login, embed_supported, offline_supported, verified, enabled, priority, created_by, created_at, updated_at.
Internal ids (`lc_res_<hex>`) are the identity — URLs are attributes, never keys. `concept_ids` links a resource to the concept graph; `topic`/`chapter` give context-aware placement.

## Status by provider

| Provider | Today | Method |
|---|---|---|
| Notion | link-only | official URL + workspace/notes links; `NotionAdapter` level 2 seam (env token, not enabled) |
| Obsidian | deep links | client-side `obsidian://open` from localStorage vault (never sent to server); official-site fallback |
| Physics Wallah | link-only | official pw.live links / teacher-added course links; no scraping |
| Khan Academy | link-only | site + India links, concept/practice resources |
| Anki | link-only + export | apps.ankiweb.net + Anki-importable TSV export (`flashcards_to_tsv`) |
| GitHub | link-only | repo links + `parse_github_repo()` validation seam for future project attach |
| YouTube | link-only | watch links, attribution preserved; no downloads |
| Google Drive | link-only | folder/doc links; OAuth deferred, credentials never stored |

## Validation runs (this pass)

- `pytest backend/tests`: **44 passed, 4 subtests passed** — includes 13 external-resource tests (registry, CRUD authz, URL/domain rejection, search/filter, context layering + subject aliases, disabled exclusion, bookmarks, activity, Obsidian gating, TSV export, GitHub validation, offline asset shipping).
- `validate_content.py`: pass (3 subjects, 6 chapters).
- `smoke_test.py`: **pass** (17 pages, 6 APIs).
- `route_sweep.py`: **pass** (180 requests, no 5xx, no unexpected statuses) — up from 177 pre-change, i.e. the 3 new integration endpoints are covered.
- `functional_test.py`: **pass** (student + teacher write flows).
- `live_http_test.py`: **pass** (7 assets, 3 pages, session + APIs over a real socket).
- `check_assets.py`: **pass — 24 references resolved** (was scanning nothing due to a ROOT bug; now fixed).

### Migration proof (additive, no data loss)

Booted the app against a byte-copy of the live dev DB (`backend/data/learncraft.db`, 20 real users, 4 notes):

```text
pre-boot  external tables : []
post-boot external tables : ['external_resources', 'resource_activity', 'resource_bookmarks']
post-boot seeded resources: 9
users preserved           : True (20)
notes preserved           : True (4)
```

No migration script is needed: `CREATE TABLE IF NOT EXISTS` + idempotent seeding runs on boot and touches nothing existing.

## Existing architecture (reused, not duplicated)

- Curriculum: content_catalog (academic_* tables) + curriculum_pipeline (class<N> packages). Subjects/chapters/topics/lessons/concepts/questions all present. No new curriculum tables.
- Notes: SQLite notes + /api/notes CRUD. Resources reference notes by subject/chapter text match only (no schema change).
- AI: ai_tutor.py hybrid (cloud/Ollama/LM Studio/built-in) + retrieve_context with provenance. New hook resources_for_ai_context() returns registry entries only.
- Progress: learning_progress + events. Resource activity is separate (resource_activity) with opened!=completed; optional bridge enqueues sync_queue progress only.
- Teacher: teacher_control classes/members/access/assignments/announcements. Resources reuse assignment flow (resource_id) + new verify/disable flags on resource rows.
- Auth: session + STUDENT/TEACHER/ADMIN. Students read + bookmark; teachers/admins write global catalog.
- Frontend: Jinja base.html + pages/*.html + design-system.css. New pages/resources.html + _resource_cards.html partial in same style.
- DB: SQLite connection.py CREATE TABLE IF NOT EXISTS. New tables follow same pattern (no migrations).


## Proposed (P0-P1 built)

Registry services/external_providers.py (8 official providers); model services/external_resources.py + 3 tables; catalog api/v1/resources.py (providers/list/search/open/bookmarks/activity/teacher CRUD); hub pages/resources.html + partial; seed data/external_resources/*.json official URLs only.

## Validation runs (this pass)

Superseded by the status table above — kept for the audit trail of what was wrong at P0/P1.
- pytest backend/tests: 37 passed, 1 failed. Only failure is pre-existing stale test_app_structure (expects backend/frontend; repo uses root/frontend). New test_external_resources: 7/7 pass.
- validate_content: pass (3 subjects, 6 chapters).
- smoke_test: 1 known script-expectation failure ([auth] GET /api/v1/users -> 403 is correct teacher-only behavior; smoke script logs in as student).
- route_sweep: pass (177 requests, no 5xx).
- functional_test / live_http_test: long-running; re-run before merge.
- check_assets: reported 0 references because script ROOT resolved to backend/ while assets live at root/frontend (pre-existing script bug; now fixed).


## DB/API/frontend/security/offline/future

See docs/integrations/external-learning.md for full detail. Summary: additive SQLite tables; new blueprint only (no existing endpoint changed); Jinja hub in design-system; validate_external_url allowlist + Obsidian quote(); no server-side fetching (no SSRF); no tokens stored; offline metadata/bookmarks stay, launches badge Requires Internet; P2 vault/adapter/export hooks, P3 OAuth, P4 mastery recommendations. AI uses registry only, never invents URLs.
