"""Round-trip smoke test for the curriculum schema."""
import json
import sys

sys.path.insert(0, ".")
from app.schemas.curriculum import (  # noqa: E402
    CurriculumPackage, Question, QuestionType, Difficulty, CompetencyCategory,
    SourceMetadata, generate_schema_doc,
)

pkg = CurriculumPackage(
    class_level="Class X",
    package_id="test-pkg",
    subjects=[],
    source=SourceMetadata(
        source_id="src-1", source_type="ncert_textbook", title="NCERT X",
        publisher="NCERT", academic_year="2026-27",
    ),
)
d = pkg.to_dict()
again = CurriculumPackage.from_dict(d)
assert again == pkg, "CurriculumPackage round-trip failed"

q = Question(
    question_id="q1",
    question_type=QuestionType.MCQ,
    difficulty=Difficulty.HARD,
    competency=CompetencyCategory.APPLY,
    options=[{"option_id": "a", "text": "2", "is_correct": True},
             {"option_id": "b", "text": "3", "is_correct": False}],
    source=SourceMetadata(source_id="s", source_type="human_authored", title="t"),
    verified=True,
)
assert q.is_valid_mcq() is True
q2 = Question.from_dict(json.loads(json.dumps(q.to_dict())))
assert q2 == q, "Question round-trip failed"

# invalid MCQ: two correct answers
q3 = Question(question_id="q3", options=[
    {"option_id": "a", "text": "x", "is_correct": True},
    {"option_id": "b", "text": "y", "is_correct": True},
])
assert q3.is_valid_mcq() is False

doc = generate_schema_doc()
print("schema doc entities:", len(doc["entities"]))
print("Schema module OK: all classes importable, round-trips pass")
