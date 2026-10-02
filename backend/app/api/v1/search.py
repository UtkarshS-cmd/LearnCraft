"""Application-wide search over canonical entities (FTS5, offline, indexed).

- ``GET /api/v1/search?q=<term>``  categorized results with real hrefs

Entities indexed: subjects, chapters, lessons, concepts, questions, simulations,
resources and the caller's own notes. Curriculum rows are (re)built into the
``search_index`` FTS5 table at boot; note rows are kept in sync by the note
write paths. When FTS5 is unavailable the service degrades to bounded LIKE
queries, so search never becomes a full unbounded table scan.
"""
from __future__ import annotations

import json
import re
import uuid

from flask import Blueprint, jsonify, request, session

from app.database.connection import _transaction, get_connection

bp = Blueprint("search_v1", __name__, url_prefix="/api/v1/search")

CATEGORIES = ["concepts", "lessons", "subjects", "questions", "simulations",
              "resources", "notes"]


def _fts_available() -> bool:
    connection = get_connection()
    try:
        connection.execute("SELECT 1 FROM search_index LIMIT 1").fetchall()
        return True
    except Exception:
        return False
    finally:
        connection.close()


_INDEX_READY = False


def ensure_index() -> None:
    """Build the curriculum index once per process if it is missing.

    The boot-time seed covers the normal server start; this keeps search
    working for a fresh/empty database (tests, a wiped data dir) instead of
    silently returning zero results.
    """
    global _INDEX_READY
    if _INDEX_READY:
        return
    try:
        connection = get_connection()
        try:
            empty = not connection.execute(
                "SELECT 1 FROM search_index LIMIT 1").fetchall()
        finally:
            connection.close()
        if empty:
            rebuild_curriculum_index()
        _INDEX_READY = True
    except Exception:
        pass


def index_row(entity_type: str, entity_id: str, title: str, body: str,
              href: str, owner_id: str = "") -> None:
    """Insert/replace one row in the search index (idempotent)."""
    def work(connection):
        connection.execute("DELETE FROM search_index WHERE entity_id = ? AND owner_id = ?",
                           (entity_id, owner_id))
        connection.execute(
            "INSERT INTO search_index (entity_type, entity_id, title, body, href, owner_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (entity_type, entity_id, str(title)[:200], str(body)[:1000], href, owner_id))
    try:
        _transaction(work)
    except Exception:
        pass  # index is a cache; search still works without it


def remove_index_row(entity_id: str, owner_id: str = "") -> None:
    def work(connection):
        connection.execute("DELETE FROM search_index WHERE entity_id = ? AND owner_id = ?",
                           (entity_id, owner_id))
    try:
        _transaction(work)
    except Exception:
        pass


def rebuild_curriculum_index() -> int:
    """(Re)build the curriculum half of the index from the installed packages.

    Runs at boot: it is idempotent and bounded (a few thousand small rows).
    """
    from app.services.concept_map import _graph, available_class_dirs

    def work(connection):
        connection.execute("DELETE FROM search_index WHERE owner_id = ''")
        count = 0
        for class_dir in available_class_dirs():
            graph = _graph(class_dir.name)
            for subject in graph.get("subjects", []):
                count += _put(connection, "subjects", subject["slug"],
                              subject["name"], f"Curriculum subject: {subject['name']}",
                              f"/subjects/{subject['slug']}")
            for cid, node in graph.get("nodes", {}).items():
                count += _put(connection, "concepts", cid, node.get("title", cid),
                              f"{node.get('difficulty','')} {node.get('chapter_id','')}",
                              f"/mastery?concept={cid}")
                lesson_id = node.get("lesson_id", "")
                if lesson_id:
                    count += _put(connection, "lessons", lesson_id,
                                  lesson_id.replace("-", " ").title(),
                                  f"Lesson for concept {node.get('title','')}",
                                  f"/subjects/{_subject_for(graph, node.get('chapter_id',''))}/lessons/{lesson_id}")
            for sim in _simulations():
                count += _put(connection, "simulations", sim["id"], sim.get("name", sim["id"]),
                              sim.get("description", "") or "Interactive simulation",
                              f"/student/simulation/{sim['id']}")
            for res in _resources():
                count += _put(connection, "resources", res["id"], res.get("title", ""),
                              res.get("description", ""), f"/resources?q={res.get('title','')}")
        for question in _questions():
            count += _put(connection, "questions", question["id"],
                          question["prompt"][:120], question.get("skill", ""),
                          f"/tests?question={question['id']}")
        return count
    return int(_transaction(work) or 0)


def _put(connection, entity_type, entity_id, title, body, href) -> int:
    connection.execute(
        "INSERT INTO search_index (entity_type, entity_id, title, body, href, owner_id) "
        "VALUES (?, ?, ?, ?, ?, '')",
        (entity_type, entity_id, str(title)[:200], str(body)[:1000], href))
    return 1


def _subject_for(graph, chapter_id):
    for subject in graph.get("subjects", []):
        if chapter_id in subject.get("chapter_ids", []):
            return subject.get("slug", "")
    return ""


def _simulations():
    from app.services.content_catalog import load_feature_simulations

    return load_feature_simulations()


def _resources():
    from app.services.external_resources import list_resources

    return list_resources({}) or []


def _questions(limit: int = 400):
    """A bounded slice of the question bank for the index (never the full 9k)."""
    from app.services.content_catalog import list_questions

    try:
        rows = list_questions()
    except Exception:
        rows = []
    out = []
    for q in rows[:limit]:
        out.append({"id": q.get("question_id", ""), "prompt": q.get("prompt", ""),
                    "skill": q.get("skill", "")})
    return [q for q in out if q["id"] and q["prompt"]]


def _clean_query(raw: str) -> str:
    """Turn user input into a safe FTS5 prefix query."""
    tokens = re.findall(r"[A-Za-z0-9_]+", raw or "")
    if not tokens:
        return ""
    return " ".join(f'"{t}"*' for t in tokens[:6])


@bp.get("")
@bp.get("/")
def search():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "code": "AUTH_REQUIRED",
                        "message": "Authentication required."}), 401
    raw = str(request.args.get("q", "")).strip()
    if len(raw) < 2:
        return jsonify({"success": True, "query": raw, "groups": {}, "count": 0,
                        "message": "Type at least 2 characters to search."})
    limit = max(1, min(request.args.get("limit", type=int) or 8, 25))
    groups: dict[str, list[dict]] = {}

    match = _clean_query(raw)
    ensure_index()
    if match and _fts_available():
        groups = _fts_search(int(user_id), match, limit)
    else:
        groups = _like_search(int(user_id), raw, limit)

    count = sum(len(items) for items in groups.values())
    return jsonify({"success": True, "query": raw, "groups": groups, "count": count,
                    "categories": CATEGORIES})


def _fts_search(user_id: int, match: str, limit: int) -> dict[str, list[dict]]:
    connection = get_connection()
    try:
        rows = connection.execute(
            "SELECT entity_type, entity_id, title, snippet(search_index, 3, '', '', '…', 12) AS snippet, href "
            "FROM search_index WHERE search_index MATCH ? "
            "AND (owner_id = '' OR owner_id = ?) "
            "ORDER BY rank LIMIT ?",
            (match, str(user_id), limit * 4),
        ).fetchall()
    except Exception:
        connection.close()
        return _like_search(user_id, match.strip('"*'), limit)
    connection.close()
    groups: dict[str, list[dict]] = {}
    for row in rows:
        bucket = groups.setdefault(row["entity_type"], [])
        if len(bucket) >= limit:
            continue
        bucket.append({"id": row["entity_id"], "title": row["title"],
                       "snippet": row["snippet"], "href": row["href"]})
    return groups


def _like_search(user_id: int, term: str, limit: int) -> dict[str, list[dict]]:
    """Bounded LIKE fallback (still indexed columns, never a full dump)."""
    term = term.replace("*", "").strip()
    if not term:
        return {}
    like = f"%{term}%"
    groups: dict[str, list[dict]] = {}
    connection = get_connection()
    try:
        rows = connection.execute(
            "SELECT entity_type, entity_id, title, body, href FROM search_index "
            "WHERE (title LIKE ? OR body LIKE ?) AND (owner_id = '' OR owner_id = ?) "
            "ORDER BY length(title) LIMIT ?",
            (like, like, str(user_id), limit * 4),
        ).fetchall()
    except Exception:
        rows = []
    connection.close()
    for row in rows:
        bucket = groups.setdefault(row["entity_type"], [])
        if len(bucket) < limit:
            bucket.append({"id": row["entity_id"], "title": row["title"],
                           "snippet": (row["body"] or "")[:90], "href": row["href"]})
    return groups


def index_note(note: dict) -> None:
    """Keep the signed-in learner's own notes searchable (private, owner-scoped)."""
    try:
        client_id = note.get("client_id", "")
        title = note.get("title", "")
        body = " ".join(str(note.get(key) or "") for key in ("body", "chapter", "source_title"))
        tags = note.get("tags") or []
        if isinstance(tags, str):
            try:
                tags = json.loads(tags)
            except (TypeError, ValueError):
                tags = []
        text = " ".join([body] + [str(t) for t in tags])
        index_row("notes", client_id, title, text, f"/notes?open={client_id}",
                  owner_id=str(note.get("user_id", "")))
    except Exception:
        pass


def unindex_note(client_id: str, user_id: int) -> None:
    remove_index_row(client_id, owner_id=str(user_id))

