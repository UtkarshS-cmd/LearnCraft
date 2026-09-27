"""Learner APIs: profile, pathways, mastery, next action, gamification."""
from __future__ import annotations
from flask import Blueprint, jsonify, request, session
from app.services.learner_profile import get_profile, save_profile
from app.services.pathways import get_pathway, list_pathways
from app.services.mastery import list_mastery, weak_concepts
from app.services.adaptive import next_action
from app.services.gamification import award, profile as xp_profile

bp = Blueprint("learning_v1", __name__, url_prefix="/api/v1")


def _uid():
    return session.get("user_id")


def _need():
    if not _uid():
        return jsonify({"success": False, "message": "Authentication required."}), 401
    return None


@bp.get("/profile/learner")
def learner_get():
    err = _need()
    if err:
        return err
    return jsonify({"success": True, "profile": get_profile(_uid())})


@bp.put("/profile/learner")
def learner_put():
    err = _need()
    if err:
        return err
    try:
        return jsonify({"success": True, "profile": save_profile(_uid(), request.get_json(silent=True) or {})})
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 400


@bp.get("/pathways")
def pathways_list():
    err = _need()
    if err:
        return err
    mine = get_profile(_uid()).get("pathway")
    return jsonify({"items": list_pathways(), "selected": mine})


@bp.post("/pathways/select")
def pathway_select():
    err = _need()
    if err:
        return err
    pid = str((request.get_json(silent=True) or {}).get("pathway", "")).lower()
    if not get_pathway(pid):
        return jsonify({"success": False, "message": "Unknown pathway."}), 400
    prof = get_profile(_uid())
    prof["pathway"] = pid
    return jsonify({"success": True, "profile": save_profile(_uid(), prof)})
