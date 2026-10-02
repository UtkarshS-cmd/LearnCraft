"""Adaptive next-action engine: deterministic rules first, AI for explanation.

``next_action`` is the canonical entry point behind ``/api/v1/learning/next``.
It now returns a STRUCTURED recommendation: ``title``/``detail``/``reason`` stay
for backward compatibility, plus ``why`` (evidence bullets) and ``actions``
(real routes) so the UI can explain *why* something is recommended instead of
showing one opaque line.
"""
from __future__ import annotations

from app.database.connection import get_user_progress
from app.services.mastery import weak_concepts
from app.services.learner_profile import get_profile


def actions_for_concept(concept_key: str, subject_slug: str = "", lesson_id: str = "") -> list[dict]:
    """Concrete routes a learner can take for one concept.

    Every action points at an existing LearnCraft page - no dead links.
    """
    actions: list[dict] = []
    if lesson_id and subject_slug:
        actions.append({"label": "Review concept", "kind": "lesson",
                        "href": f"/subjects/{subject_slug}/lessons/{lesson_id}"})
    elif subject_slug:
        actions.append({"label": "Review concept", "kind": "lesson",
                        "href": f"/subjects/{subject_slug}"})
    actions.append({"label": "Run simulation", "kind": "simulation",
                    "href": f"/sandbox?concept={concept_key}" if concept_key else "/sandbox"})
    actions.append({"label": "Practice", "kind": "practice",
                    "href": f"/tests?subject={subject_slug}" if subject_slug else "/tests"})
    actions.append({"label": "Take quiz", "kind": "quiz", "href": "/tests"})
    return actions


def weak_concept_reason(concept: dict) -> list[str]:
    """Evidence bullets derived from the persisted mastery row itself."""
    why: list[str] = []
    mastery = float(concept.get("mastery") or 0)
    attempts = int(concept.get("attempts") or 0)
    wrong = attempts - int(concept.get("correct", 0) or 0)
    if attempts:
        why.append(f"Mastery is {mastery:.0f}% across {attempts} attempt(s).")
        if wrong:
            why.append(f"You missed {wrong} question(s) on {concept['concept_key']}.")
        if int(concept.get("streak", 0) or 0) == 0 and attempts >= 2:
            why.append("The most recent attempt was incorrect.")
        if mastery < 45:
            why.append("Still below the 45% developing threshold for this concept.")
    else:
        why.append("No attempts recorded for this concept yet.")
    return why


def _lesson_for_concept(concept_key: str) -> str:
    """Resolve the curriculum lesson that teaches a concept (graph lookup)."""
    from app.services.concept_map import graph_node

    return graph_node(concept_key).get("lesson_id", "")


def next_action(uid: int) -> dict:
    """Structured, explainable next action for a learner."""
    weak = weak_concepts(uid, 60.0, 5)
    if weak:
        w = weak[0]
        subject = w.get("subject_slug", "") or ""
        return {
            "title": f"Revise {w['concept_key']}",
            "detail": f"Mastery {w['mastery']}% across {w['attempts']} attempts",
            "reason": "Lowest-mastery concept needs targeted practice first.",
            "why": weak_concept_reason(w),
            "actions": actions_for_concept(w["concept_key"], subject,
                                           _lesson_for_concept(w["concept_key"])),
            "href": "/tests", "action": "Practice now", "kind": "revision",
            "concept": w["concept_key"],
        }
    rows = get_user_progress(uid)
    open_rows = [r for r in rows if r.get("status") != "completed"]
    if open_rows:
        r = sorted(open_rows, key=lambda x: x.get("percent_complete", 0))[0]
        pct = int(r.get("percent_complete", 0) or 0)
        why = [f"{r.get('lesson_id')} is {pct}% complete."]
        if r.get("last_activity"):
            why.append(f"Last activity: {r['last_activity']}.")
        resume = ("/my-learning")
        if r.get("subject_slug") and r.get("lesson_id"):
            resume = f"/subjects/{r['subject_slug']}/lessons/{r['lesson_id']}"
        return {
            "title": f"Continue {r.get('lesson_id')}",
            "detail": f"{pct}% complete",
            "reason": "Unfinished lesson with the least progress.",
            "why": why,
            "actions": [
                {"label": "Continue lesson", "kind": "lesson", "href": resume},
                {"label": "View my learning", "kind": "progress", "href": "/my-learning"},
            ],
            "href": "/my-learning", "action": "Continue", "kind": "lesson",
            "concept": r.get("lesson_id"),
        }
    prof = get_profile(uid)
    goals = prof.get("goals") or ["Pick a goal"]
    return {
        "title": goals[0], "detail": "Start a focused quiz",
        "reason": "No weak concepts or open lessons; advance the goal.",
        "why": ["No weak concepts and no unfinished lessons right now."],
        "actions": [{"label": "Start quiz", "kind": "quiz", "href": "/tests"},
                    {"label": "Browse subjects", "kind": "subject", "href": "/subjects"}],
        "href": "/tests", "action": "Start quiz", "kind": "goal",
        "concept": "general",
    }


def next_action_for_session(uid: int, lesson_id: str = "", concept: str = "") -> dict:
    """Context-aware recommendation used inside a learning session / AI panel."""
    if concept:
        return {
            "title": f"Work on {concept}",
            "detail": "Recommended for the concept you are studying",
            "reason": "You are in a focused session on this concept.",
            "why": ["Selected from the concept currently open in your session."],
            "actions": actions_for_concept(concept, "", lesson_id),
            "href": "/tests", "action": "Practice", "kind": "revision",
            "concept": concept,
        }
    return next_action(uid)
