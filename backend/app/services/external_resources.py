"""External resources: validation, CRUD, search, bookmarks, activity (part 1)."""

from __future__ import annotations

import ipaddress
import json
import uuid
from urllib.parse import quote, urlparse

from app.database.connection import _transaction, get_connection
from app.services.external_providers import DIFFICULTIES, RESOURCE_TYPES, get_provider

BOOKMARK_STATUSES = {"NOT_STARTED", "IN_PROGRESS", "COMPLETED"}
ACTIVITY_ACTIONS = {"opened", "completed", "bookmarked", "unbookmarked", "created", "verified"}

# CBSE exposes one broad "Science" subject while the provider catalog is organised
# by discipline. These aliases keep board-neutral core logic (nothing CBSE-specific
# hardcoded in the engine) while letting a Science chapter surface Physics /
# Chemistry / Biology tagged links. Extend this map per board, not per provider.
SUBJECT_ALIASES = {
    "science": ("physics", "chemistry", "biology"),
    "physics": ("science",),
    "chemistry": ("science",),
    "biology": ("science",),
    "mathematics": ("maths", "math"),
    "maths": ("mathematics", "math"),
    "math": ("mathematics", "maths"),
    "social science": ("history", "geography", "civics", "economics", "political science"),
    "computer science": ("computer", "programming", "coding", "informatics"),
    "english": ("english language",),
}


def subject_keys(subject: str) -> list[str]:
    """Lowercase subject tokens to match, including known aliases (deterministic order)."""
    name = str(subject or "").strip().lower()
    if not name:
        return []
    return sorted({name, *SUBJECT_ALIASES.get(name, ())})

_DANGEROUS = ("javascript:", "data:", "file:", "vbscript:", "blob:")
_PRIVATE = ("10.", "192.168.", "172.16.", "172.17.", "172.18.", "172.19.", "172.2", "172.30.", "172.31.", "127.", "0.0.0.0")


def validate_external_url(provider_id: str, url: str) -> str:
    provider = get_provider(provider_id)
    if not provider:
        raise ValueError(f"Unknown provider: {provider_id}")
    text = (url or "").strip()
    if not text or len(text) > 2048:
        raise ValueError("A valid resource URL is required (max 2048 chars).")
    if text.lower().startswith(_DANGEROUS):
        raise ValueError("That URL scheme is not allowed.")
    try:
        parsed = urlparse(text)
    except Exception:
        raise ValueError("That URL is malformed.")
    if parsed.scheme != "https":
        raise ValueError("External resources must use https:// URLs.")
    host = (parsed.hostname or "").lower().rstrip(".")
    if not host or host == "localhost" or host.startswith(_PRIVATE):
        raise ValueError("That URL host is not allowed.")
    try:
        ipaddress.ip_address(host)
        raise ValueError("That URL host is not allowed.")
    except ValueError as exc:
        if "not allowed" in str(exc):
            raise
    allowed = {h.lower() for h in provider.get("allowed_hosts", set())}
    if host not in allowed and not any(host.endswith("." + a) for a in allowed):
        raise ValueError(f"URL host {host} is not an official {provider['name']} domain.")
    return text


def obsidian_uri(vault: str = "", note_path: str = "", action: str = "open") -> str:
    base = "obsidian://new" if action == "new" else "obsidian://open"
    params = []
    if (vault or "").strip():
        params.append("vault=" + quote(vault.strip(), safe=""))
    if (note_path or "").strip().strip("/"):
        params.append("file=" + quote(note_path.strip().strip("/"), safe=""))
    return base + ("?" + "&".join(params) if params else "")

def create_resource(data: dict, created_by: int | None = None) -> dict:
    provider_id = _s(data.get("provider"), 60).lower()
    resource_type = _s(data.get("resource_type"), 40).lower()
    title = _s(data.get("title"), 200)
    url = validate_external_url(provider_id, str(data.get("url", "")))
    if not title:
        raise ValueError("Resource title is required.")
    if resource_type not in RESOURCE_TYPES:
        raise ValueError(f"Unknown resource_type: {resource_type}")
    difficulty = _s(data.get("difficulty"), 20).upper() or "FOUNDATION"
    if difficulty not in DIFFICULTIES:
        raise ValueError(f"Unknown difficulty: {difficulty}")
    concept_ids = data.get("concept_ids") or []
    if isinstance(concept_ids, str):
        concept_ids = [c.strip() for c in concept_ids.split(",") if c.strip()]
    concept_ids = [str(c).strip()[:180] for c in list(concept_ids)[:30] if str(c).strip()]
    resource_id = _s(data.get("id"), 80) or ("lc_res_" + uuid.uuid4().hex[:12])

    def work(connection):
        connection.execute(
            "INSERT INTO external_resources (id, provider, resource_type, title, description, url, subject, class_level, chapter, topic, concept_ids_json, language, difficulty, is_official, requires_login, embed_supported, offline_supported, verified, enabled, priority, created_by)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (resource_id, provider_id, resource_type, title, _s(data.get("description"), 2000), url,
             _s(data.get("subject"), 120), _s(data.get("class_level"), 40), _s(data.get("chapter"), 200),
             _s(data.get("topic"), 200), json.dumps(concept_ids), _s(data.get("language"), 20) or "en",
             difficulty, int(bool(data.get("is_official", True))), int(bool(data.get("requires_login", False))),
             int(bool(data.get("embed_supported", False))), int(bool(data.get("offline_supported", False))),
             int(bool(data.get("verified", False))), int(bool(data.get("enabled", True))),
             int(data.get("priority") or 0), created_by))
        return connection.execute("SELECT * FROM external_resources WHERE id = ?", (resource_id,)).fetchone()
    try:
        return _row_to_resource(_transaction(work))
    except Exception as exc:
        if "UNIQUE" in str(exc):
            raise ValueError("That resource URL is already in the catalog.")
        raise


def get_resource(resource_id: str) -> dict | None:
    connection = get_connection()
    row = connection.execute("SELECT * FROM external_resources WHERE id = ?", (resource_id,)).fetchone()
    connection.close()
    return _row_to_resource(row) if row else None


def update_resource(resource_id: str, data: dict) -> dict | None:
    existing = get_resource(resource_id)
    if not existing:
        return None
    fields: dict = {}
    if "title" in data:
        title = _s(data.get("title"), 200)
        if not title:
            raise ValueError("Resource title is required.")
        fields["title"] = title
    for key in ("description", "subject", "class_level", "chapter", "topic", "language"):
        if key in data:
            fields[key] = _s(data.get(key), 2000 if key == "description" else 200)
    if "resource_type" in data:
        rt = _s(data.get("resource_type"), 40).lower()
        if rt not in RESOURCE_TYPES:
            raise ValueError(f"Unknown resource_type: {rt}")
        fields["resource_type"] = rt
    if "difficulty" in data:
        d = _s(data.get("difficulty"), 20).upper()
        if d not in DIFFICULTIES:
            raise ValueError(f"Unknown difficulty: {d}")
        fields["difficulty"] = d
    provider_id = _s(data.get("provider"), 60).lower() or existing["provider"]
    if "provider" in data and not get_provider(provider_id):
        raise ValueError(f"Unknown provider: {provider_id}")
    fields["provider"] = provider_id
    if "url" in data or "provider" in data:
        fields["url"] = validate_external_url(provider_id, str(data.get("url", existing["url"])))
    if "concept_ids" in data:
        cids = data.get("concept_ids") or []
        if isinstance(cids, str):
            cids = [c.strip() for c in cids.split(",") if c.strip()]
        fields["concept_ids_json"] = json.dumps([str(c).strip()[:180] for c in list(cids)[:30] if str(c).strip()])
    for key in ("is_official", "requires_login", "embed_supported", "offline_supported", "verified", "enabled"):
        if key in data:
            fields[key] = int(bool(data.get(key)))
    if "priority" in data:
        fields["priority"] = int(data.get("priority") or 0)
    if not fields:
        return existing

    def work(connection):
        connection.execute(
            "UPDATE external_resources SET " + ", ".join(f"{k} = ?" for k in fields)
            + ", updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (*fields.values(), resource_id))
        return connection.execute("SELECT * FROM external_resources WHERE id = ?", (resource_id,)).fetchone()
    try:
        return _row_to_resource(_transaction(work))
    except Exception as exc:
        if "UNIQUE" in str(exc):
            raise ValueError("That resource URL is already in the catalog.")
        raise


def list_resources(filters: dict | None = None, include_disabled: bool = False) -> list[dict]:
    filters = filters or {}
    query = "SELECT * FROM external_resources WHERE 1 = 1"
    params: list = []
    if not include_disabled:
        query += " AND enabled = 1"
    if filters.get("provider"):
        query += " AND provider = ?"
        params.append(str(filters["provider"]).strip().lower())
    if filters.get("subject"):
        query += " AND LOWER(subject) LIKE ?"
        params.append("%" + str(filters["subject"]).strip().lower() + "%")
    if filters.get("subjects"):
        values = sorted({str(s).strip().lower() for s in filters["subjects"] if str(s).strip()})
        if values:
            query += " AND LOWER(subject) IN (" + ", ".join("?" * len(values)) + ")"
            params += values
    if filters.get("class_level"):
        query += " AND class_level = ?"
        params.append(str(filters["class_level"]).strip())
    if filters.get("chapter"):
        query += " AND (LOWER(chapter) LIKE ? OR LOWER(topic) LIKE ?)"
        params += ["%" + str(filters["chapter"]).strip().lower() + "%"] * 2
    if filters.get("resource_type"):
        query += " AND resource_type = ?"
        params.append(str(filters["resource_type"]).strip().lower())
    if filters.get("difficulty"):
        query += " AND difficulty = ?"
        params.append(str(filters["difficulty"]).strip().upper())
    if filters.get("language"):
        query += " AND language = ?"
        params.append(str(filters["language"]).strip().lower())
    if filters.get("verified") is not None:
        query += " AND verified = ?"
        params.append(1 if filters["verified"] else 0)
    if filters.get("concept_id"):
        query += " AND concept_ids_json LIKE ?"
        params.append("%" + str(filters["concept_id"]).strip()[:120] + "%")
    if filters.get("q"):
        query += " AND (LOWER(title) LIKE ? OR LOWER(description) LIKE ? OR LOWER(chapter) LIKE ? OR LOWER(topic) LIKE ?)"
        params += ["%" + str(filters["q"]).strip().lower() + "%"] * 4
    query += " ORDER BY priority DESC, verified DESC, title"
    connection = get_connection()
    rows = connection.execute(query, params).fetchall()
    connection.close()
    return [_row_to_resource(r) for r in rows]



def set_bookmark(user_id: int, resource_id: str, status: str = "IN_PROGRESS", pinned: bool = False) -> dict:
    if not get_resource(resource_id):
        raise ValueError("Resource not found.")
    status = str(status or "IN_PROGRESS").upper()
    if status not in BOOKMARK_STATUSES:
        raise ValueError("Invalid bookmark status.")

    def work(connection):
        connection.execute(
            "INSERT INTO resource_bookmarks (user_id, resource_id, status, pinned) VALUES (?, ?, ?, ?)"
            " ON CONFLICT(user_id, resource_id) DO UPDATE SET status=excluded.status, pinned=excluded.pinned, updated_at=CURRENT_TIMESTAMP",
            (int(user_id), resource_id, status, int(bool(pinned))))
        return connection.execute(
            "SELECT * FROM resource_bookmarks WHERE user_id = ? AND resource_id = ?",
            (int(user_id), resource_id)).fetchone()
    row = _transaction(work)
    log_activity(user_id, resource_id, "bookmarked")
    return dict(row)


def remove_bookmark(user_id: int, resource_id: str) -> bool:
    def work(connection):
        return connection.execute(
            "DELETE FROM resource_bookmarks WHERE user_id = ? AND resource_id = ?",
            (int(user_id), resource_id)).rowcount > 0
    removed = bool(_transaction(work))
    if removed:
        log_activity(user_id, resource_id, "unbookmarked")
    return removed


def user_bookmarks(user_id: int) -> list[dict]:
    connection = get_connection()
    rows = connection.execute(
        "SELECT b.*, r.title, r.provider, r.resource_type, r.url, r.subject, r.chapter"
        " FROM resource_bookmarks b JOIN external_resources r ON r.id = b.resource_id"
        " WHERE b.user_id = ? ORDER BY b.pinned DESC, b.updated_at DESC",
        (int(user_id),)).fetchall()
    connection.close()
    return [dict(r) for r in rows]


def log_activity(user_id: int, resource_id: str, action: str, concept_id: str = "") -> dict:
    action = str(action or "").strip().lower()
    if action not in ACTIVITY_ACTIONS:
        raise ValueError("Invalid activity action.")
    resource = get_resource(resource_id)
    provider = resource["provider"] if resource else ""

    def work(connection):
        cursor = connection.execute(
            "INSERT INTO resource_activity (user_id, resource_id, provider, concept_id, action) VALUES (?, ?, ?, ?, ?)",
            (int(user_id), resource_id, provider, str(concept_id or "")[:180], action))
        return connection.execute("SELECT * FROM resource_activity WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return dict(_transaction(work))


def user_activity(user_id: int, limit: int = 50) -> list[dict]:
    connection = get_connection()
    rows = connection.execute(
        "SELECT * FROM resource_activity WHERE user_id = ? ORDER BY id DESC LIMIT ?",
        (int(user_id), max(1, min(int(limit or 50), 200)))).fetchall()
    connection.close()
    return [dict(r) for r in rows]


def ensure_external_resource_seed() -> int:
    import pathlib
    seed_path = pathlib.Path(__file__).resolve().parents[2] / "data" / "external_resources" / "starter_resources.json"
    if not seed_path.exists():
        return 0
    items = json.loads(seed_path.read_text(encoding="utf-8")).get("resources", [])
    connection = get_connection()
    existing = {r[0] for r in connection.execute("SELECT url FROM external_resources").fetchall()}
    connection.close()
    for raw in items:
        if raw.get("url") in existing:
            continue
        try:
            create_resource({**raw, "verified": True, "is_official": True})
        except ValueError:
            continue
    connection = get_connection()
    count = connection.execute("SELECT COUNT(*) FROM external_resources").fetchone()[0]
    connection.close()
    return count


def resources_for_context(subject="", chapter="", topic="", concept_id="", limit=12) -> list[dict]:
    """Resources relevant to a curriculum position, in three deterministic layers.

    1. concept / chapter+topic matches (the most specific links),
    2. other subject-scoped entries (including CBSE aliases, so "Science" also
       surfaces Physics/Chemistry/Biology tagged links),
    3. the provider layer - catalog entries that are not tied to a chapter, e.g.
       "Khan Academy - Courses". These stay available on every chapter so a
       subject widget is never empty and the learner can always open a platform.
    """
    keys = subject_keys(subject)
    ordered: list[dict] = []
    seen: set[str] = set()

    def add(items) -> None:
        for item in items:
            if item["id"] not in seen:
                seen.add(item["id"])
                ordered.append(item)

    if concept_id:
        # An explicit concept filter is authoritative: only concept matches are
        # returned alongside the provider layer (no subject-wide dilution).
        add(list_resources({"concept_id": concept_id, "subjects": keys} if keys else {"concept_id": concept_id}))
        add([i for i in list_resources() if not i.get("subject") and not i.get("chapter")])
        return ordered[:max(1, min(int(limit or 12), 50))]
    scoped = list_resources({"subjects": keys} if keys else {})
    needle = (chapter or topic or "").strip().lower()
    if needle:
        add([i for i in scoped if needle[:24] in f"{i.get('chapter', '')} {i.get('topic', '')} {i.get('title', '')}".lower()])
    add(scoped)
    add([i for i in list_resources() if not i.get("subject") and not i.get("chapter")])
    return ordered[:max(1, min(int(limit or 12), 50))]


def resources_for_ai_context(subject="", chapter="", topic="", concept_id="", limit=4) -> list[dict]:
    return [{"provider": r["provider"], "title": r["title"], "url": r["url"],
             "resource_type": r["resource_type"], "verified": r["verified"]}
            for r in resources_for_context(subject, chapter, topic, concept_id, limit)]


def delete_resource(resource_id: str) -> bool:
    def work(connection):
        return connection.execute("DELETE FROM external_resources WHERE id = ?", (resource_id,)).rowcount > 0
    return bool(_transaction(work))


def _row_to_resource(row) -> dict:
    item = dict(row)
    try:
        item["concept_ids"] = json.loads(item.get("concept_ids_json") or "[]")
    except Exception:
        item["concept_ids"] = []
    item.pop("concept_ids_json", None)
    for flag in ("is_official", "requires_login", "embed_supported", "offline_supported", "verified", "enabled"):
        item[flag] = bool(item.get(flag))
    return item


def _s(value, limit: int = 200) -> str:
    return str(value or "").strip()[:limit]
