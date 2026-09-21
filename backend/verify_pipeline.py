#!/usr/bin/env python3
"""Comprehensive verification of the curriculum pipeline."""
import os
import sys
import json
from pathlib import Path

os.environ.setdefault("LEARNCRAFT_SECRET_KEY", "test-key-for-verification")
os.environ.setdefault("LEARNCRAFT_DB_PATH", ":memory:")

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.schemas.curriculum import (
    CurriculumPackage, Subject, Chapter, Concept, Question,
    SourceMetadata, CANONICAL_SCHEMA_VERSION, Difficulty, QuestionType,
    CompetencyCategory, VerificationStatus, Board,
)
from app.services.curriculum_pipeline import (
    available_class_dirs, load_manifest, load_class_package,
    load_question_bank, load_concept_graph, load_simulation_registry,
    load_roadmap, build_concept_graph, generate_roadmap,

# 1. Schema completeness
print("\n[1] SCHEMA COMPLETENESS")
print("-" * 40)
errors.clear()

# Check CurriculumPackage has all required fields
pkg = CurriculumPackage(
    board=Board.CBSE, class_level="Class X", academic_year="2026-27",
    package_id="test-pkg", version="1.0.0", source_version="test",
    generated_at="2026-01-01T00:00:00Z", generated_by="test",
    source="test", verified=False, subjects=[],
)
pkg_dict = pkg.to_dict()
pkg_from_dict = CurriculumPackage.from_dict(pkg_dict)

required_fields = [
    "schema_version", "board", "class_level", "academic_year",
    "package_id", "version", "source_version", "generated_at",
    "generated_by", "source", "verified", "verified_at",
    "ai_generation_notes", "subjects",
]
for f in required_fields:
    check(f in pkg_dict, f"CurriculumPackage missing: {f}")

# Subject roundtrip
subj = Subject(
    subject_id="test-subj", class_level="Class X", board=Board.CBSE,
    slug="test", name="Test Subject", description="Test",
    book_id="test-book", book_title="Test Book", publisher="NCERT",
    source="test", verified=True, chapters=[],
)
subj_from_dict = Subject.from_dict(subj.to_dict())
check(subj_from_dict.subject_id == "test-subj", "Subject roundtrip failed")

# Concept roundtrip
concept = Concept(
    concept_id="test-concept", title="Test Concept", description="Test desc",
    explanation="Test expl", difficulty=Difficulty.MEDIUM,
    learning_objectives=["LO1", "LO2"], prerequisites=["prereq-1"],
    next_concepts=["next-1"],
    competencies=[CompetencyCategory.UNDERSTAND, CompetencyCategory.APPLY],
    activities=["act-1"], simulation_mappings=["sim-1"],
    question_ids=["q-1"],
    source_metadata=SourceMetadata(
        source_id="src-1", source_type="ncert_textbook",
        title="NCERT Book", publisher="NCERT",
        url="https://ncert.nic.in", version="2026-27", academic_year="2026-27",
    ),
    verified=False, ai_generation_notes="AI generated",
)
concept_from_dict = Concept.from_dict(concept.to_dict())
check(concept_from_dict.concept_id == "test-concept", "Concept roundtrip failed")
check(concept_from_dict.difficulty == Difficulty.MEDIUM, "Concept difficulty roundtrip")
check(len(concept_from_dict.prerequisites) == 1, "Concept prereqs roundtrip")
check(len(concept_from_dict.next_concepts) == 1, "Concept next_concepts roundtrip")
check(concept_from_dict.verified is False, "Concept verified=False preserved")
check(concept_from_dict.ai_generation_notes == "AI generated", "AI notes preserved")

# Chapter roundtrip
chapter = Chapter(
    chapter_id="test-chapter", class_level="Class X", subject_slug="maths",
    chapter_number=1, title="Test Chapter", summary="Test summary",
    description="Test desc", concepts=[concept], sub_concepts=[],
    learning_objectives=[], activities=[], simulation_mappings=[],
    difficulty=Difficulty.MEDIUM, prerequisites=[], competencies=[CompetencyCategory.UNDERSTAND],
    lesson_ids=[], source="test", verified=True,
)
chapter_from_dict = Chapter.from_dict(chapter.to_dict())
check(chapter_from_dict.chapter_id == "test-chapter", "Chapter roundtrip failed")

# Question roundtrip (all 12 types)
for qt in QuestionType:
    q = Question(
        question_id=f"test-{qt.value.lower().replace(' ', '-')}",
        concept_id="test-concept", chapter_id="test-chapter",
        question_type=qt, prompt=f"Test {qt.value}",
        answer="Test answer", options=["A", "B", "C", "D"],
        explanation="Test", difficulty=Difficulty.EASY,
        competency=CompetencyCategory.REMEMBER, marks=1,
        source="test", verified=False,
    )
    q_from_dict = Question.from_dict(q.to_dict())
    check(q_from_dict.question_id == q.question_id, f"Question {qt.value} roundtrip")
    check(q_from_dict.question_type == qt, f"Question type {qt.value} preserved")
    check(q_from_dict.verified is False, f"Question {qt.value} verified=False preserved")
    check(q_from_dict.difficulty == Difficulty.EASY, f"Question {qt.value} difficulty")
    check(q_from_dict.competency == CompetencyCategory.REMEMBER, f"Question {qt.value} competency")

# Competency categories and difficulty levels
for comp in CompetencyCategory:
    check(comp.value in ["Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create"],
          f"Competency {comp} has wrong value")
for diff in Difficulty:
    check(diff.value in ["FOUNDATION", "EASY", "MEDIUM", "HARD", "BOARD_LEVEL", "CHALLENGE"],
          f"Difficulty {diff} has wrong value")

print(f"  Schema roundtrip checks: {len(errors)} errors")
    validate_class_package, filter_questions, question_bank_summary,
    package_summary, resolve_class_dir, load_all_packages,
    build_roadmap_for_class, validate_concept_references,
)

CURRICULUM_DIR = Path(__file__).resolve().parent / "data" / "curriculum"
errors = []
warnings = []

def check(condition, msg):
    if not condition:
        errors.append(msg)

def warn(condition, msg):
    if not condition:
        warnings.append(msg)

print("=" * 70)
print("CURRICULUM PIPELINE VERIFICATION")
print("=" * 70)