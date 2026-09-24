from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.services.content_catalog import (
    list_manifests,
    list_questions,
    list_subjects as catalog_subjects,
    mark_manifest_downloaded,
    subject_detail as catalog_subject_detail,
)

bp = Blueprint("subjects_v1", __name__, url_prefix="/api/v1")

# Answer keys never leave the server: grading is server-authoritative through
# /api/v1/quizzes/check, so the public question feed must not carry solutions.
_ANSWER_KEYS = {"answer", "explanation", "correct_answer", "correct_option_id", "is_correct"}
_OPTION_ANSWER_KEYS = {"is_correct"}


def _public_question(question: dict) -> dict:
    """Strip solution fields from one catalog question, keeping the rest."""
    item = {key: value for key, value in question.items() if key not in _ANSWER_KEYS}
    item["options"] = [
        {key: value for key, value in option.items() if key not in _OPTION_ANSWER_KEYS}
        for option in question.get("options", [])
    ]
    return item


@bp.get("/subjects")
def list_subjects():
    return jsonify({"items": catalog_subjects(), "academic_year": "2026-27", "board": "CBSE", "class": "Class X"})


@bp.get("/subjects/<slug>")
def get_subject(slug):
    item = catalog_subject_detail(slug)
    if not item:
        return jsonify({"success": False, "message": "Subject not found."}), 404
    return jsonify(item)


@bp.get("/questions")
def questions():
    return jsonify({"items": [_public_question(q) for q in list_questions(
        request.args.get("subject"), request.args.get("chapter_id")
    )]})


@bp.get("/content-manifest")
def content_manifest():
    return jsonify({"items": list_manifests(), "offline": True})


@bp.post("/content-manifest/<content_id>/download")
def download_content(content_id):
    if not mark_manifest_downloaded(content_id):
        return jsonify({"success": False, "message": "Content package not found."}), 404
    return jsonify({"success": True, "content_id": content_id, "downloaded": True})
