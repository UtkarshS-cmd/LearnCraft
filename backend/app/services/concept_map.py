"""Concept mastery visualisation layer over the EXISTING mastery graph.

Nothing here invents a second mastery model: the canonical numbers come from
the ``concept_mastery`` table scored by :mod:`app.services.mastery_a`, and the
canonical structure comes from the curriculum concept graph produced by
:mod:`app.services.curriculum_pipeline`.

This module only adds:
  * the four product states (NOT_STARTED / LEARNING / DEVELOPING / MASTERED),
  * prerequisite / next-concept resolution against real nodes,
  * the related lesson / simulation / practice entry points for one concept,
  * an "explain why" recommendation for the concept.
"""
from __future__ import annotations

from app.database.connection import get_connection
from app.services.curriculum_pipeline import (
    available_class_dirs,
    load_class_package,
    load_concept_graph,
    resolve_class_dir,
)
from app.services.mastery_a import score_row

STATE_NOT_STARTED = "NOT_STARTED"
STATE_LEARNING = "LEARNING"
STATE_DEVELOPING = "DEVELOPING"
STATE_MASTERED = "MASTERED"

# Thresholds are derived from the existing mastery score's own meaning
# (accuracy + consistency + difficulty + recency + completion), not invented
# per-feature weights. See docs/PRODUCT_ARCHITECTURE.md.
MASTERED_AT = 75.0
DEVELOPING_AT = 45.0


def mastery_state(mastery: float, attempts: int) -> str:
    """Map the canonical mastery score to one of four product states."""
    if not attempts:
        return STATE_NOT_STARTED
    if mastery >= MASTERED_AT:
        return STATE_MASTERED
    if mastery >= DEVELOPING_AT:
        return STATE_DEVELOPING
    return STATE_LEARNING


# ---------------------------------------------------------------------------
# Curriculum graph (cached, filesystem only)
# ---------------------------------------------------------------------------

_GRAPH_CACHE: dict[str, dict] = {}


def _graph(class_name: str | None = None) -> dict:
    """nodes/edges/prereq index for a class package, cached by class name."""
    class_dir = resolve_class_dir(class_name)
    key = class_dir.name if class_dir else "__none__"
    if key in _GRAPH_CACHE:
        return _GRAPH_CACHE[key]
    if class_dir is None:
        return {"nodes": {}, "edges": [], "class_level": "", "subjects": []}
    data = load_concept_graph(class_dir)
    nodes = {n["concept_id"]: n for n in data.get("nodes", [])}
    edges = []
    for cid, node in nodes.items():
        for prereq in node.get("prerequisites", []) or []:
            edges.append({"from": prereq, "to": cid})
    subjects = []
    pkg = load_class_package(class_dir)
    for subject in pkg.subjects:
        subjects.append({
            "slug": subject.slug,
            "name": subject.name,
            "chapter_ids": [ch.chapter_id for ch in subject.chapters],
            "lesson_ids": [lid for ch in subject.chapters for lid in ch.lesson_ids],
        })
    graph = {"nodes": nodes, "edges": edges, "class_level": pkg.class_level,
             "academic_year": pkg.academic_year, "subjects": subjects,
             "class_name": class_dir.name}
    _GRAPH_CACHE[key] = graph
    return graph


def available_classes() -> list[dict]:
    out = []
    for class_dir in available_class_dirs():
        if (class_dir / "concept_graph.json").exists():
            graph = _graph(class_dir.name)
            out.append({
                "class_name": class_dir.name,
                "class_level": graph.get("class_level", ""),
                "academic_year": graph.get("academic_year", ""),
                "concept_count": len(graph.get("nodes", {})),
            })
    return out


def graph_node(concept_id: str) -> dict:
    """Look a concept up in any available class package (no session needed)."""
    for class_dir in available_class_dirs():
        node = _graph(class_dir.name)["nodes"].get(concept_id)
        if node:
            return node
    return {}


def _mastery_rows() -> dict[str, dict]:
    """concept_key -> mastery row for the signed-in learner (single query)."""
    from flask import session

    user_id = session.get("user_id")
    if not user_id:
        return {}
    connection = get_connection()
    rows = connection.execute(
        "SELECT * FROM concept_mastery WHERE user_id = ?", (int(user_id),)
    ).fetchall()
    connection.close()
    return {row["concept_key"]: dict(row) for row in rows}


def _chapter_to_subject(class_name: str | None) -> dict[str, str]:
    """chapter_id -> subject slug, so a concept can show its subject."""
    mapping: dict[str, str] = {}
    for subject in _graph(class_name).get("subjects", []):
        for chapter_id in subject.get("chapter_ids", []):
            mapping[chapter_id] = subject.get("slug", "")
    return mapping


def concept_detail(concept_id: str, class_name: str | None = None) -> dict | None:
    """Everything a learner needs when they open one concept in the map."""
    graph = _graph(class_name)
    node = graph["nodes"].get(concept_id)
    if not node:
        return None
    chapter_subject = _chapter_to_subject(class_name)
    chapter_id = node.get("chapter_id", "")
    subject_slug = chapter_subject.get(chapter_id, "")
    chapter_number = _chapter_number(class_name, chapter_id)
    row = _mastery_rows().get(concept_id)
    mastery, signals = (score_row(row) if row else (0.0, {}))
    attempts = int(row.get("attempts", 0) or 0) if row else 0

    lesson_id = node.get("lesson_id", "")
    return {
        "concept_id": concept_id,
        "title": node.get("title", concept_id),
        "chapter_id": chapter_id,
        "chapter_number": chapter_number,
        "subject_slug": subject_slug,
        "lesson_id": lesson_id,
        "difficulty": node.get("difficulty", ""),
        "state": mastery_state(mastery, attempts),
        "mastery": mastery,
        "attempts": attempts,
        "accuracy": round(float(row.get("accuracy", 0) or 0) * 100, 1) if row else 0.0,
        "signals": signals,
        "recent_attempts": recent_attempts(concept_id),
        "prerequisites": [_node_summary(graph, cid) for cid in node.get("prerequisites", []) or []],
        "next_concepts": [_node_summary(graph, cid) for cid in node.get("next_concepts", []) or []],
        "lesson": _related_lesson(class_name, concept_id, node, subject_slug),
        "simulation": _related_simulation(class_name, concept_id, subject_slug, chapter_number),
        "practice_href": f"/tests?subject={subject_slug}" if subject_slug else "/tests",
        "recommended": recommend_for_concept(concept_id, mastery, attempts, signals,
                                             subject_slug, node),
    }


def _chapter_number(class_name: str | None, chapter_id: str) -> int:
    """Chapter number for a chapter id (0 when unknown)."""
    if not chapter_id:
        return 0
    for class_dir in available_class_dirs():
        package = load_class_package(class_dir)
        for subject in package.subjects:
            for chapter in subject.chapters:
                if chapter.chapter_id == chapter_id:
                    return int(chapter.chapter_number)
    return 0


def _node_summary(graph: dict, concept_id: str) -> dict:
    node = graph["nodes"].get(concept_id, {})
    return {"concept_id": concept_id, "title": node.get("title", concept_id),
            "available": bool(node)}


def recent_attempts(concept_id: str, limit: int = 5) -> list[dict]:
    """Last real graded attempts for this concept (server-side truth)."""
    from flask import session

    user_id = session.get("user_id")
    if not user_id:
        return []
    connection = get_connection()
    rows = connection.execute(
        "SELECT question_id, correct, difficulty, created_at FROM question_attempts "
        "WHERE user_id = ? AND concept_key = ? ORDER BY id DESC LIMIT ?",
        (int(user_id), concept_id, max(1, min(int(limit), 20))),
    ).fetchall()
    connection.close()
    return [dict(row) for row in rows]


def _related_lesson(class_name, concept_id, node, subject_slug) -> dict:
    """Locate the real lesson that teaches this concept."""
    lesson_id = node.get("lesson_id", "")
    if not lesson_id or not subject_slug:
        return {}
    from app.services.content_catalog import get_lesson

    lesson = get_lesson(lesson_id)
    if not lesson:
        return {}
    return {
        "lesson_id": lesson_id,
        "title": lesson.get("title", ""),
        "href": f"/subjects/{subject_slug}/lessons/{lesson_id}",
    }


def _related_simulation(class_name, concept_id, subject_slug, chapter_number) -> dict:
    """Locate a real simulation mapped to this concept (or its chapter)."""
    from app.services.content_catalog import load_feature_simulations, simulation_covers_chapter

    node = _graph(class_name)["nodes"].get(concept_id, {})
    chapter_id = node.get("chapter_id", "")
    for sim in load_feature_simulations():
        if not sim.get("id"):
            continue
        if sim.get("concept_id") == concept_id:
            return {"simulation_id": sim["id"], "title": sim.get("name", sim["id"]),
                    "href": f"/student/simulation/{sim['id']}"}
        if subject_slug and chapter_number:
            try:
                if simulation_covers_chapter(sim, subject_slug, int(chapter_number)):
                    return {"simulation_id": sim["id"], "title": sim.get("name", sim["id"]),
                            "href": f"/student/simulation/{sim['id']}"}
            except (TypeError, ValueError):
                continue
        if chapter_id and chapter_id in (sim.get("chapter_ids") or []):
            return {"simulation_id": sim["id"], "title": sim.get("name", sim["id"]),
                    "href": f"/student/simulation/{sim['id']}"}
    return {}


def lesson_for_key(key: str, class_name: str | None = None) -> str:
    """Resolve a mastery/concept key to a real lesson id.

    Mastery keys can be a concept id (new) or a chapter id (older rows), so the
    resolver walks concept node -> chapter lesson list rather than assuming one
    shape.
    """
    node = _graph(class_name)["nodes"].get(key)
    if node and node.get("lesson_id"):
        return node["lesson_id"]
    # The key itself is a chapter id.
    for class_dir in available_class_dirs():
        package = load_class_package(class_dir)
        for subject in package.subjects:
            for chapter in subject.chapters:
                if chapter.chapter_id == key and chapter.lesson_ids:
                    return list(chapter.lesson_ids)[0]
    # A concept id in a different class package.
    for class_dir in available_class_dirs():
        node = _graph(class_dir.name)["nodes"].get(key)
        if node and node.get("lesson_id"):
            return node["lesson_id"]
    return ""


def subject_and_chapter(class_name: str | None, key: str) -> tuple[str, int]:
    """(subject slug, chapter number) for a concept id or chapter id."""
    for class_dir in available_class_dirs():
        package = load_class_package(class_dir)
        for subject in package.subjects:
            for chapter in subject.chapters:
                node = _graph(class_dir.name)["nodes"].get(key)
                node_chapter = node.get("chapter_id") if node else None
                if key == chapter.chapter_id or node_chapter == chapter.chapter_id:
                    return subject.slug, int(chapter.chapter_number)
    return ("", 0)


def recommend_for_concept(concept_id, mastery, attempts, signals, subject_slug, node) -> dict:
    """The next action for ONE concept, with the evidence behind it."""
    from app.services.adaptive import actions_for_concept

    actions = actions_for_concept(concept_id, subject_slug, node.get("lesson_id", ""))
    if attempts == 0:
        why = ["No attempt on this concept yet."]
        prereqs = node.get("prerequisites") or []
        if prereqs:
            why.append("Builds on: " + ", ".join(
                graph_title(cid) for cid in prereqs[:3]) + ".")
    else:
        correct = int(attempts * float(signals.get("accuracy", 0) or 0))
        wrong = attempts - correct
        why = [f"Mastery {mastery:.0f}% over {attempts} attempt(s)."]
        why.append(f"{wrong} of {attempts} attempts were incorrect." if wrong
                   else "All recorded attempts were correct.")
        if mastery < DEVELOPING_AT:
            why.append("Still below the 45% developing threshold.")
    return {"why": why, "actions": actions, "concept": concept_id}


def graph_title(concept_id: str) -> str:
    for class_dir in available_class_dirs():
        node = _graph(class_dir.name)["nodes"].get(concept_id)
        if node:
            return node.get("title", concept_id)
    return concept_id


def list_concepts(class_name: str | None = None, subject: str = ""):
    """Concept list joined with the learner's persisted mastery."""
    graph = _graph(class_name)
    chapter_subject = _chapter_to_subject(class_name)
    if not graph["nodes"]:
        return [], graph
    rows = _mastery_rows()
    items = []
    for cid, node in sorted(graph["nodes"].items(), key=lambda kv: kv[1].get("title", "")):
        chapter_id = node.get("chapter_id", "")
        subject_slug = chapter_subject.get(chapter_id, "")
        if subject and subject_slug != subject:
            continue
        row = rows.get(cid)
        mastery, signals = (score_row(row) if row else (0.0, {}))
        attempts = int(row.get("attempts", 0) or 0) if row else 0
        items.append({
            "concept_id": cid,
            "title": node.get("title", cid),
            "chapter_id": chapter_id,
            "lesson_id": node.get("lesson_id", ""),
            "subject_slug": subject_slug,
            "difficulty": node.get("difficulty", ""),
            "estimated_minutes": node.get("estimated_minutes"),
            "prerequisites": list(node.get("prerequisites", []) or []),
            "next_concepts": list(node.get("next_concepts", []) or []),
            "mastery": mastery,
            "attempts": attempts,
            "accuracy": round(float(row.get("accuracy", 0) or 0) * 100, 1) if row else 0.0,
            "state": mastery_state(mastery, attempts),
            "signals": signals,
            "href": f"/subjects/{subject_slug}" if subject_slug else "/subjects",
        })
    return items, graph
