from __future__ import annotations

from flask import Blueprint, jsonify, request, session

from app.services.content_catalog import list_questions

bp = Blueprint("quizzes_v1", __name__, url_prefix="/api/v1")


def _public_question(item: dict) -> dict:
    """Question payload safe for the browser (no answers leaked)."""
    return {
        "question_id": item.get("question_id"),
        "subject_slug": item.get("subject_slug"),
        "prompt": item.get("prompt"),
        "question_type": item.get("question_type"),
        "difficulty": item.get("difficulty"),
        "marks": item.get("marks"),
        "options": [
            {"option_id": opt.get("option_id"), "option_text": opt.get("option_text")}
            for opt in item.get("options", [])
        ],
    }


@bp.get("/quizzes")
def list_quizzes():
    subject = request.args.get("subject")
    chapter_id = request.args.get("chapter_id")
    limit = request.args.get("limit", type=int) or 10
    items = list_questions(subject, chapter_id)[: max(1, min(limit, 50))]
    return jsonify({"items": [_public_question(item) for item in items]})


@bp.post("/quizzes/check")
def check_quiz():
    """Grade one answer instantly (offline, server-side truth)."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "message": "Authentication required."}), 401
    payload = request.get_json(silent=True) or {}
    question_id = str(payload.get("question_id", "")).strip()
    given = payload.get("answer")
    if not question_id:
        return jsonify({"success": False, "message": "question_id is required."}), 400

    match = next((q for q in list_questions() if q.get("question_id") == question_id), None)
    if not match:
        return jsonify({"success": False, "message": "Question not found."}), 404

    correct_option_ids = [o["option_id"] for o in match.get("options", []) if o.get("is_correct")]
    explanation = match.get("explanation", "")
    expected = (match.get("answer") or "").strip()

    if correct_option_ids:
        given_ids = given if isinstance(given, list) else [given]
        given_ids = [str(g).strip() for g in given_ids if str(g).strip()]
        correct = sorted(given_ids) == sorted(correct_option_ids)
        return jsonify({
            "success": True,
            "correct": correct,
            "correct_option_ids": correct_option_ids,
            "explanation": explanation,
        })

    # Short/numerical answer: case-insensitive comparison, numeric tolerance.
    def norm(value) -> str:
        return " ".join(str(value or "").strip().lower().split())

    correct = norm(given) == norm(expected)
    if not correct:
        try:
            correct = abs(float(str(given).strip()) - float(expected)) < 1e-9
        except (ValueError, TypeError):
            correct = False
    return jsonify({"success": True, "correct": correct, "answer": expected, "explanation": explanation})
