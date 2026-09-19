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
    return jsonify({"items": list_questions(
        request.args.get("subject"), request.args.get("chapter_id")
    )})


@bp.get("/content-manifest")
def content_manifest():
    return jsonify({"items": list_manifests(), "offline": True})


@bp.post("/content-manifest/<content_id>/download")
def download_content(content_id):
    if not mark_manifest_downloaded(content_id):
        return jsonify({"success": False, "message": "Content package not found."}), 404
    return jsonify({"success": True, "content_id": content_id, "downloaded": True})
