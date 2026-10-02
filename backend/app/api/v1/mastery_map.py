"""Concept Mastery Map API (visual layer over the existing mastery graph).

- ``GET /api/v1/mastery/map``              graph + learner states (curriculum order)
- ``GET /api/v1/mastery/map/<class_name>`` same, for a specific class package
- ``GET /api/v1/mastery/concepts/<id>``    drill-down for one concept

The graph is generated from the backend curriculum package + the learner's
persisted ``concept_mastery`` rows. There is no hard-coded graph in JS.
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request, session

from app.services.concept_map import (
    STATE_DEVELOPING,
    STATE_LEARNING,
    STATE_MASTERED,
    STATE_NOT_STARTED,
    available_classes,
    concept_detail,
    list_concepts,
    mastery_state,
)

bp = Blueprint("mastery_map_v1", __name__, url_prefix="/api/v1/mastery")


@bp.get("/map")
def mastery_map_root():
    return _map_payload(request.args.get("class"))


@bp.get("/map/<class_name>")
def mastery_map(class_name: str):
    return _map_payload(class_name)


def _map_payload(class_name: str | None):
    if not session.get("user_id"):
        return jsonify({"success": False, "message": "Authentication required."}), 401
    items, graph = list_concepts(class_name, request.args.get("subject", ""))
    if not items:
        return jsonify({
            "success": True, "nodes": [], "edges": [], "items": [],
            "summary": _empty_summary(),
            "message": "No curriculum concept graph is installed for this class yet.",
        })
    counts = {STATE_NOT_STARTED: 0, STATE_LEARNING: 0, STATE_DEVELOPING: 0,
              STATE_MASTERED: 0}
    for item in items:
        counts[item["state"]] = counts.get(item["state"], 0) + 1
    return jsonify({
        "success": True,
        "class_level": graph.get("class_level", ""),
        "academic_year": graph.get("academic_year", ""),
        "classes": available_classes(),
        "subjects": graph.get("subjects", []),
        "nodes": items,
        "edges": graph.get("edges", []),
        "summary": counts,
        "legend": {
            "states": [STATE_NOT_STARTED, STATE_LEARNING, STATE_DEVELOPING, STATE_MASTERED],
            "mastered_at": 75.0, "developing_at": 45.0,
        },
    })


def _empty_summary():
    return {STATE_NOT_STARTED: 0, STATE_LEARNING: 0, STATE_DEVELOPING: 0,
            STATE_MASTERED: 0}


@bp.get("/concepts/<path:concept_id>")
def concept(concept_id: str):
    if not session.get("user_id"):
        return jsonify({"success": False, "message": "Authentication required."}), 401
    detail = concept_detail(concept_id, request.args.get("class"))
    if not detail:
        return jsonify({"success": False, "code": "NOT_FOUND",
                        "message": "Concept not found in the installed curriculum."}), 404
    return jsonify({"success": True, "concept": detail})


@bp.get("/states")
def state_reference():
    """Documented thresholds so the UI never invents its own states."""
    return jsonify({
        "success": True,
        "states": [
            {"state": STATE_NOT_STARTED, "meaning": "No attempt recorded."},
            {"state": STATE_LEARNING, "meaning": "Attempted, mastery below 45%."},
            {"state": STATE_DEVELOPING, "meaning": "Mastery between 45% and 75%."},
            {"state": STATE_MASTERED, "meaning": "Mastery 75% or above."},
        ],
        "source": "concept_mastery.mastery scored by app/services/mastery_a.score_row",
    })
