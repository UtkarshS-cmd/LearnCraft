"""Curriculum package API (offline, read-only).

Serves the versioned ``data/curriculum/class<N>/`` packages produced by
``scripts/build_class10_package.py``:

- ``GET /api/v1/curriculum/classes``                    package summaries
- ``GET /api/v1/curriculum/<class>``                    one package summary
- ``GET /api/v1/curriculum/<class>/roadmap``            roadmap GENERATED from the concept graph
- ``GET /api/v1/curriculum/<class>/concept-graph``      concept -> prerequisites -> next concepts
- ``GET /api/v1/curriculum/<class>/simulations``        registry (catalog + mappings)
- ``GET /api/v1/curriculum/<class>/concepts/<id>/simulations``
- ``GET /api/v1/curriculum/<class>/question-bank``      filtered questions (answers gated)
- ``GET /api/v1/curriculum/<class>/question-bank/summary``
- ``GET /api/v1/curriculum/<class>/subjects/<slug>``    canonical subject document

Everything is served from local files; no network access is required.
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request, session

from app.services.curriculum_pipeline import (
    available_class_dirs,
    build_roadmap_for_class,
    filter_questions,
    load_class_package,
    load_concept_graph,
    load_simulation_registry,
    package_summary,
    question_bank_summary,
    resolve_class_dir,
    simulations_for_concept,
)

bp = Blueprint("curriculum_v1", __name__, url_prefix="/api/v1/curriculum")


def _class_dir_or_404(class_name: str):
    class_dir = resolve_class_dir(class_name)
    if class_dir is None:
        return None, (jsonify({"success": False,
                               "message": f"Unknown class package: {class_name}"}), 404)
    return class_dir, None


def _public_question(question, include_answers: bool) -> dict:
    """Question metadata; answers only for an authenticated session."""
    payload = {
        "question_id": question.question_id,
        "chapter_id": question.chapter_id,
        "concept_id": question.concept_id,
        "question_type": question.question_type.value,
        "difficulty": question.difficulty.value,
        "competency": question.competency.value,
        "marks": question.marks,
        "prompt": question.prompt,
        "verified": question.verified,
        "source": question.source.to_dict() if question.source else None,
        "scenario": question.scenario,
        "linked_concepts": question.linked_concepts,
    }
    if include_answers:
        payload["answer"] = question.answer
        payload["explanation"] = question.explanation
        payload["options"] = question.options
        payload["rubric"] = question.rubric
    else:
        # MCQ clients still need option text to render; correctness stays hidden.
        payload["options"] = [
            {"option_id": option.get("option_id"), "text": option.get("text")}
            for option in question.options
        ]
    return payload


@bp.get("/classes")
def list_classes():
    items = [package_summary(class_dir) for class_dir in available_class_dirs()
             if (class_dir / "manifest.json").exists()]
    return jsonify({"items": items, "offline": True})


@bp.get("/<class_name>")
def get_class(class_name: str):
    class_dir, error = _class_dir_or_404(class_name)
    if error:
        return error
    return jsonify(package_summary(class_dir))


@bp.get("/<class_name>/roadmap")
def get_roadmap(class_name: str):
    class_dir, error = _class_dir_or_404(class_name)
    if error:
        return error
    return jsonify(build_roadmap_for_class(class_dir))


@bp.get("/<class_name>/concept-graph")
def get_concept_graph(class_name: str):
    class_dir, error = _class_dir_or_404(class_name)
    if error:
        return error
    return jsonify(load_concept_graph(class_dir))


@bp.get("/<class_name>/simulations")
def get_simulations(class_name: str):
    class_dir, error = _class_dir_or_404(class_name)
    if error:
        return error
    concept_id = request.args.get("concept_id")
    if concept_id:
        return jsonify({"concept_id": concept_id,
                        "items": simulations_for_concept(class_dir, concept_id)})
    return jsonify(load_simulation_registry(class_dir))


@bp.get("/<class_name>/concepts/<path:concept_id>/simulations")
def get_concept_simulations(class_name: str, concept_id: str):
    class_dir, error = _class_dir_or_404(class_name)
    if error:
        return error
    return jsonify({"concept_id": concept_id,
                    "items": simulations_for_concept(class_dir, concept_id)})


@bp.get("/<class_name>/question-bank/summary")
def get_question_bank_summary(class_name: str):
    class_dir, error = _class_dir_or_404(class_name)
    if error:
        return error
    return jsonify(question_bank_summary(class_dir))


@bp.get("/<class_name>/question-bank")
def get_question_bank(class_name: str):
    class_dir, error = _class_dir_or_404(class_name)
    if error:
        return error

    verified_arg = request.args.get("verified")
    verified = None
    if verified_arg is not None:
        verified = verified_arg.strip().lower() in ("1", "true", "yes")

    limit = request.args.get("limit", type=int)
    if limit is not None:
        limit = max(1, min(limit, 200))

    questions = filter_questions(
        class_dir,
        chapter_id=request.args.get("chapter_id"),
        concept_id=request.args.get("concept_id"),
        question_type=request.args.get("question_type"),
        difficulty=request.args.get("difficulty"),
        competency=request.args.get("competency"),
        verified=verified,
        limit=limit,
    )
    include_answers = bool(session.get("user_id"))
    return jsonify({
        "items": [_public_question(q, include_answers) for q in questions],
        "count": len(questions),
        "answers_included": include_answers,
    })


@bp.get("/<class_name>/subjects/<slug>")
def get_subject(class_name: str, slug: str):
    class_dir, error = _class_dir_or_404(class_name)
    if error:
        return error
    pkg = load_class_package(class_dir)
    for subject in pkg.subjects:
        if subject.slug == slug:
            return jsonify(subject.to_dict())
    return jsonify({"success": False, "message": f"Subject not found: {slug}"}), 404
