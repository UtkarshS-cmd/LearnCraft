"""Learner APIs part 2: mastery, next action, XP, adaptive quizzes."""
from __future__ import annotations
from flask import Blueprint, jsonify, request, session
from app.services.mastery import (get_concept, list_mastery, record_attempt,
                                  weak_concepts)
from app.services.adaptive import next_action
from app.services.gamification import award, profile as xp_profile
from app.services.content_catalog import list_questions

bp2 = Blueprint("learning2_v1", __name__, url_prefix="/api/v1")


def _uid():
    return session.get("user_id")


def _need():
    if not _uid():
        return jsonify({"success": False, "message": "Authentication required."}), 401
    return None


@bp2.get("/mastery")
def mastery_list():
    err = _need()
    if err:
        return err
    items = list_mastery(_uid(), request.args.get("limit", type=int) or 50)
    return jsonify({"items": items, "count": len(items)})


@bp2.get("/mastery/weak")
def mastery_weak():
    err = _need()
    if err:
        return err
    items = weak_concepts(_uid(), request.args.get("threshold", type=float) or 60.0, 10)
    return jsonify({"items": items, "count": len(items)})


@bp2.get("/learning/next")
def learning_next():
    err = _need()
    if err:
        return err
    return jsonify({"success": True, "next": next_action(_uid())})


@bp2.get("/gamification")
def xp_get():
    err = _need()
    if err:
        return err
    return jsonify({"success": True, **xp_profile(_uid())})


@bp2.post("/gamification/award")
def xp_award():
    err = _need()
    if err:
        return err
    action = str((request.get_json(silent=True) or {}).get("action", "practice"))
    return jsonify({"success": True, **award(_uid(), action)})
