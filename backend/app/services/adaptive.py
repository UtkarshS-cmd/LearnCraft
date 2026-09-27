"""Adaptive next-action engine: deterministic rules first, AI for explanation."""
from __future__ import annotations
from app.database.connection import get_user_progress
from app.services.mastery import weak_concepts
from app.services.learner_profile import get_profile


def next_action(uid: int) -> dict:
    weak = weak_concepts(uid, 60.0, 5)
    if weak:
        w = weak[0]
        return {"title": f"Revise {w['concept_key']}",
                "detail": f"Mastery {w['mastery']}% across {w['attempts']} attempts",
                "reason": "Lowest-mastery concept needs targeted practice first.",
                "href": "/tests", "action": "Practice now", "kind": "revision",
                "concept": w["concept_key"]}
    rows = get_user_progress(uid)
    open_rows = [r for r in rows if r.get("status") != "completed"]
    if open_rows:
        r = sorted(open_rows, key=lambda x: x.get("percent_complete", 0))[0]
        return {"title": f"Continue {r.get('lesson_id')}",
                "detail": f"{r.get('percent_complete', 0)}% complete",
                "reason": "Unfinished lesson with the least progress.",
                "href": "/my-learning", "action": "Continue", "kind": "lesson",
                "concept": r.get("lesson_id")}
    prof = get_profile(uid)
    goals = prof.get("goals") or ["Pick a goal"]
    return {"title": goals[0], "detail": "Start a focused quiz",
            "reason": "No weak concepts or open lessons; advance the goal.",
            "href": "/tests", "action": "Start quiz", "kind": "goal",
            "concept": "general"}
