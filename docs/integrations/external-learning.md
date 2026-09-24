# External Learning Integrations

LearnCraft is the hub. External platforms are link-outs or documented adapters — never scraped, never iframed as clones.

## Link-only today (implemented)

Notion (open workspace/notes), Obsidian (obsidian:// open/new URIs + fallback to obsidian.md), Physics Wallah (pw.live links), Khan Academy (site + India), Anki (apps.ankiweb.net), GitHub (repos), YouTube (watch links, youtube-nocookie embeds only), Google Drive (folder/doc links).
All launches: target=_blank rel=noopener, opened vs completed tracked separately, Requires Internet badge offline (Obsidian stays enabled, local-first).

## Notion (Level 1 done, Level 2 interface)

Level 1 (shipped): provider card + resource links + "Open Study Workspace". Level 2 (documented seam, not enabled): `NotionAdapter` in `app/services/provider_adapters.py` — `status()` reports level 1 vs 2 from the presence of a **server-side** `NOTION_API_TOKEN` env var; `create_study_note()`, `create_study_plan()`, `export_learncraft_notes()` raise `NotImplementedError` until a deployment opts in. Tokens must never be pasted into normal frontend fields and are never stored in the database.

## Obsidian (done, local-first)

Two layers, deliberately separated:

1. **Client-side deep links (default, no server involvement).** `frontend/static/js/external-links.js` exposes `lcObsidianUri(el)` / `lcOpenExternal(el, id)`. It reads `lc_obsidian_vault` + `lc_obsidian_template` from **localStorage only** and assembles `obsidian://open?vault=…&file=…` in the browser (path built from `{subject}/{chapter}/{topic}/{title}`, `encodeURIComponent` encoded, `//` collapsed). The vault name is never posted to LearnCraft.
2. **Server-side builder for API consumers.** `obsidian_uri(vault, note, action)` in `app/services/external_resources.py` mirrors the same encoding for scripting/automation; `GET /api/v1/resources/<id>?vault=…&note=…` returns `obsidian_uri`, and `…/open?vault=…` redirects to it. Both **refuse to fabricate a deep link without a configured vault** (`obsidian_uri=""`, `deep_link_supported=false`) and fall back to `https://obsidian.md/`.

Settings UI: `/settings` → "External learning (Obsidian)" saves vault + template to localStorage. If Obsidian is not installed (or no vault is set) the hub opens the official website and tells the user to configure a vault — LearnCraft never claims access to a local vault it cannot see.

Shared helper is precached by the service worker (`learncraft-shell-v4`), so resource cards and offline badges still work with no connection.

## PW / Khan / Anki / GitHub / YouTube / Drive

PW + Khan + YouTube: official links + teacher-verified chapter links only; no scraping/copying paid content; attribution preserved. Anki: open + deck metadata + TSV export (`POST /api/v1/resources/anki/export`, `flashcards_to_tsv()` → Anki-importable front/back/tags TSV; no private APIs). GitHub: concept repos + `POST /api/v1/resources/github/validate` which validates against the github.com allowlist and returns `{repository_url, owner, repository, full_name, language, topics, student_project}` — the seam for attaching a repo to a LearnCraft project once a project model exists (no bulk scraping). Drive: open folder/docs; OAuth deferred, never store Google credentials in DB.

Adapters visible to the client at `GET /api/v1/resources/adapters/status` (Notion level 1/2 detection via `NOTION_API_TOKEN`, Obsidian/Anki/GitHub level 1).

## API surface (18 API endpoints + `/resources` page, all additive)

| Method | Endpoint | Who | Purpose |
|---|---|---|---|
| GET | `/api/v1/resources/providers` | student | Registry of 8 providers (icon, types, flags) |
| GET | `/api/v1/resources` | student | Catalog + filters (q/provider/subject/type/chapter/difficulty/language) |
| GET | `/api/v1/resources/search` | student | Search alias used by the hub |
| GET | `/api/v1/resources/context` | student | **Context-aware layering**: chapter matches → subject/alias matches → generic provider layer |
| GET | `/api/v1/resources/<id>` | student | Single resource (+ `obsidian_uri`, `deep_link_supported`) |
| GET | `/api/v1/resources/<id>/open` | student | Records `opened`, redirects (or JSON with `format=json`) |
| POST | `/api/v1/resources/<id>/complete` | student | Records `completed` — explicitly **not** the same as `opened` |
| GET/POST/DELETE | `/api/v1/resources/<id>/bookmark` · `/bookmarks/mine` | student | Bookmarks with NOT_STARTED/IN_PROGRESS/COMPLETED |
| GET | `/api/v1/resources/activity/mine` | student | Own learning-activity log |
| POST/PUT/DELETE | `/api/v1/resources` · `/<id>` | teacher/admin | Catalog CRUD (students can never inject into the verified catalog) |
| POST | `/api/v1/resources/<id>/verify` | teacher/admin | Mark verified |
| GET | `/api/v1/resources/adapters/status` | student | Adapter levels (Notion L1/L2, Obsidian, Anki, GitHub) |
| POST | `/api/v1/resources/anki/export` | student | Anki-importable TSV deck export |
| POST | `/api/v1/resources/github/validate` | student | Validate + parse a repo link (`owner/repo`, `student_project`) |

**No existing endpoint was changed, renamed or removed.**

## Privacy / security / offline / future

Activity stores user/resource/action/timestamp/concept only. URL validator: https-only + provider domain allowlist + rejects `javascript:`/`data:`/`file:`/`blob:`, localhost and private IP ranges, IP literals, and blocks server-side fetching entirely (no SSRF surface). Obsidian vault names never leave the browser; Notion/Drive tokens would be env-only, never DB, never frontend JS. External links open with `target="_blank" rel="noopener"`.

Offline: hub, catalog metadata, bookmarks, saved notes, curriculum, local simulations and quizzes all keep working; external links are badged **Requires Internet** (Obsidian links stay local-first). Losing connectivity never blocks the app.

Future: P3 OAuth (Notion/Drive) + external progress sync where an official API allows it; P4 mastery-weighted and goal-aware resource recommendation driven by the learning engine.
