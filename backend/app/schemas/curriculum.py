"""Canonical curriculum schema definitions.

Pipeline stages: RAW -> EXTRACT -> VERIFY -> IMPORT -> RUNTIME
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class Difficulty(str, Enum):
    FOUNDATION = "FOUNDATION"
    EASY = "EASY"
    MEDIUM = "MEDIUM"
    HARD = "HARD"
    BOARD_LEVEL = "BOARD_LEVEL"
    CHALLENGE = "CHALLENGE"


class QuestionType(str, Enum):
    MCQ = "MCQ"
    MULTIPLE_CORRECT = "MULTIPLE_CORRECT"
    TRUE_FALSE = "TRUE_FALSE"
    SHORT_ANSWER = "SHORT_ANSWER"
    LONG_ANSWER = "LONG_ANSWER"
    APPLICATION = "APPLICATION"
    SCENARIO_BASED = "SCENARIO_BASED"
    COMPETENCY_BASED = "COMPETENCY_BASED"
    ASSERTION_REASON = "ASSERTION_REASON"
    FILL_BLANK = "FILL_BLANK"
    NUMERICAL = "NUMERICAL"
    CASE_BASED = "CASE_BASED"
    DIAGRAM_BASED = "DIAGRAM_BASED"


class VerificationStatus(str, Enum):
    PENDING = "PENDING"
    AI_GENERATED = "AI_GENERATED"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class CompetencyCategory(str, Enum):
    REMEMBER = "Remember"
    UNDERSTAND = "Understand"
    APPLY = "Apply"
    ANALYZE = "Analyze"
    EVALUATE = "Evaluate"
    CREATE = "Create"


class Board(str, Enum):
    CBSE = "CBSE"
    NCERT = "NCERT"


CANONICAL_SCHEMA_VERSION = "2026.09.1"
SCHEMA_DOC = Path(__file__).resolve().parent / "schema_doc.json"


@dataclass
class Concept:
    """A curriculum concept with prerequisites, competencies, and metadata."""
    concept_id: str
    title: str
    description: str = ""
    explanation: str = ""
    difficulty: Difficulty = Difficulty.EASY
    learning_objectives: list[str] = field(default_factory=list)
    prerequisites: list[str] = field(default_factory=list)  # list of concept_ids
    next_concepts: list[str] = field(default_factory=list)  # derived, list of concept_ids
    competencies: list[CompetencyCategory] = field(default_factory=list)
    activities: list[str] = field(default_factory=list)  # activity IDs
    simulation_mappings: list[str] = field(default_factory=list)  # simulation IDs
    question_ids: list[str] = field(default_factory=list)  # linked question IDs
    source_metadata: SourceMetadata | None = None
    verified: bool = False
    verified_by: str | None = None
    verified_at: str | None = None
    ai_generation_notes: str | None = None

    def to_dict(self) -> dict:
        return {
            "concept_id": self.concept_id,
            "title": self.title,
            "description": self.description,
            "explanation": self.explanation,
            "difficulty": self.difficulty.value,
            "learning_objectives": self.learning_objectives,
            "prerequisites": self.prerequisites,
            "next_concepts": self.next_concepts,
            "competencies": [c.value for c in self.competencies],
            "activities": self.activities,
            "simulation_mappings": self.simulation_mappings,
            "question_ids": self.question_ids,
            "source_metadata": self.source_metadata.to_dict() if self.source_metadata else None,
            "verified": self.verified,
            "verified_by": self.verified_by,
            "verified_at": self.verified_at,
            "ai_generation_notes": self.ai_generation_notes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Concept":
        return cls(
            concept_id=data["concept_id"],
            title=data["title"],
            description=data.get("description", ""),
            explanation=data.get("explanation", ""),
            difficulty=Difficulty(data["difficulty"]),
            learning_objectives=data.get("learning_objectives", []),
            prerequisites=data.get("prerequisites", []),
            next_concepts=data.get("next_concepts", []),
            competencies=[CompetencyCategory(c) for c in data.get("competencies", [])],
            activities=data.get("activities", []),
            simulation_mappings=data.get("simulation_mappings", []),
            question_ids=data.get("question_ids", []),
            source_metadata=SourceMetadata.from_dict(data["source_metadata"]) if data.get("source_metadata") else None,
            verified=data.get("verified", False),
            verified_by=data.get("verified_by"),
            verified_at=data.get("verified_at"),
            ai_generation_notes=data.get("ai_generation_notes"),
        )


@dataclass
class SourceMetadata:
    """Source provenance for any curriculum entity."""
    source_id: str
    source_type: str
    title: str
    publisher: str | None = None
    url: str | None = None
    version: str | None = None
    academic_year: str | None = None
    accessed_at: str | None = None
    checksum_sha256: str | None = None
    notes: str | None = None

    def to_dict(self) -> dict:
        d = {"source_id": self.source_id, "source_type": self.source_type, "title": self.title}
        for k in ("publisher", "url", "version", "academic_year",
                  "accessed_at", "checksum_sha256", "notes"):
            v = getattr(self, k, None)
            if v is not None:
                d[k] = v
        return d

    @classmethod
    def from_dict(cls, data: dict) -> SourceMetadata:
        known = {
            "source_id", "source_type", "title", "publisher", "url", "version",
            "academic_year", "accessed_at", "checksum_sha256", "notes",
        }
        return cls(**{k: v for k, v in data.items() if k in known and v is not None})
@dataclass
class SubConcept:
    """A finer-grained sub-division of a concept."""
    sub_concept_id: str
    concept_id: str  # parent concept
    title: str
    description: str = ""
    order: int = 0
    verified: bool = False

    def to_dict(self) -> dict:
        return {
            "sub_concept_id": self.sub_concept_id,
            "concept_id": self.concept_id,
            "title": self.title,
            "description": self.description,
            "order": self.order,
            "verified": self.verified,
        }

    @classmethod
    def from_dict(cls, data: dict) -> SubConcept:
        return cls(
            sub_concept_id=data["sub_concept_id"],
            concept_id=data["concept_id"],
            title=data["title"],
            description=data.get("description", ""),
            order=int(data.get("order", 0)),
            verified=data.get("verified", False),
        )


@dataclass
class LearningObjective:
    """A measurable learning objective with Bloom's taxonomy level."""
    objective_id: str
    concept_id: str | None = None
    statement: str = ""
    bloom_level: CompetencyCategory | None = None
    verified: bool = False

    def to_dict(self) -> dict:
        d = {
            "objective_id": self.objective_id,
            "statement": self.statement,
            "verified": self.verified,
        }
        if self.concept_id:
            d["concept_id"] = self.concept_id
        if self.bloom_level:
            d["bloom_level"] = self.bloom_level.value
        return d

    @classmethod
    def from_dict(cls, data: dict) -> LearningObjective:
        bloom = CompetencyCategory(data["bloom_level"]) if data.get("bloom_level") else None
        return cls(
            objective_id=data["objective_id"],
            concept_id=data.get("concept_id"),
            statement=data.get("statement", ""),
            bloom_level=bloom,
            verified=data.get("verified", False),
        )


@dataclass
class Activity:
    """A hands-on activity linked to concepts."""
    activity_id: str
    concept_id: str | None = None
    title: str = ""
    activity_type: str = "practice"  # practice | experiment | project | discussion | worksheet
    description: str = ""
    duration_minutes: int | None = None
    verified: bool = False

    def to_dict(self) -> dict:
        d = {
            "activity_id": self.activity_id,
            "title": self.title,
            "activity_type": self.activity_type,
            "description": self.description,
            "verified": self.verified,
        }
        if self.concept_id:
            d["concept_id"] = self.concept_id
        if self.duration_minutes is not None:
            d["duration_minutes"] = self.duration_minutes
        return d

    @classmethod
    def from_dict(cls, data: dict) -> Activity:
        return cls(
            activity_id=data["activity_id"],
            concept_id=data.get("concept_id"),
            title=data.get("title", ""),
            activity_type=data.get("activity_type", "practice"),
            description=data.get("description", ""),
            duration_minutes=data.get("duration_minutes"),
            verified=data.get("verified", False),
        )


@dataclass
class SimulationMapping:
    """Maps a concept to an offline-capable simulation."""
    mapping_id: str
    concept_id: str
    simulation_id: str
    title: str = ""
    mapping_type: str = "exploration"  # exploration | practice | experiment
    verified: bool = False

    def to_dict(self) -> dict:
        return {
            "mapping_id": self.mapping_id,
            "concept_id": self.concept_id,
            "simulation_id": self.simulation_id,
            "title": self.title,
            "mapping_type": self.mapping_type,
            "verified": self.verified,
        }

    @classmethod
    def from_dict(cls, data: dict) -> SimulationMapping:
        return cls(
            mapping_id=data["mapping_id"],
            concept_id=data["concept_id"],
            simulation_id=data["simulation_id"],
            title=data.get("title", ""),
            mapping_type=data.get("mapping_type", "exploration"),
            verified=data.get("verified", False),
        )


@dataclass
class Question:
    """A question-bank item with full metadata and verification status."""
    question_id: str
    concept_id: str | None = None
    chapter_id: str | None = None
    question_type: QuestionType = QuestionType.MCQ
    prompt: str = ""
    answer: str = ""
    options: list[dict[str, Any]] = field(default_factory=list)
    explanation: str = ""
    difficulty: Difficulty = Difficulty.EASY
    competency: CompetencyCategory = CompetencyCategory.UNDERSTAND
    marks: int = 1
    source: SourceMetadata | None = None
    verified: bool = False
    verified_at: str | None = None
    ai_generation_notes: str | None = None
    scenario: str | None = None
    rubric: list[str] | None = None
    linked_concepts: list[str] = field(default_factory=list)

    def is_valid_mcq(self) -> bool:
        """MCQ needs exactly one correct option; MULTIPLE_CORRECT at least one."""
        if self.question_type not in (QuestionType.MCQ, QuestionType.MULTIPLE_CORRECT):
            return True
        if not self.options:
            return False
        correct = [o for o in self.options if o.get("is_correct")]
        if self.question_type == QuestionType.MCQ and len(correct) != 1:
            return False
        if self.question_type == QuestionType.MULTIPLE_CORRECT and not correct:
            return False
        return True

    def to_dict(self) -> dict:
        d = {
            "question_id": self.question_id,
            "prompt": self.prompt,
            "answer": self.answer,
            "options": self.options,
            "explanation": self.explanation,
            "question_type": self.question_type.value,
            "difficulty": self.difficulty.value,
            "competency": self.competency.value,
            "marks": self.marks,
            "verified": self.verified,
        }
        if self.concept_id:
            d["concept_id"] = self.concept_id
        if self.chapter_id:
            d["chapter_id"] = self.chapter_id
        if self.scenario:
            d["scenario"] = self.scenario
        if self.rubric:
            d["rubric"] = self.rubric
        if self.linked_concepts:
            d["linked_concepts"] = self.linked_concepts
        if self.source:
            d["source"] = self.source.to_dict()
        if self.verified_at:
            d["verified_at"] = self.verified_at
        if self.ai_generation_notes:
            d["ai_generation_notes"] = self.ai_generation_notes
        return d

    @classmethod
    def from_dict(cls, data: dict) -> Question:
        return cls(
            question_id=data["question_id"],
            concept_id=data.get("concept_id"),
            chapter_id=data.get("chapter_id"),
            question_type=QuestionType(data.get("question_type", "MCQ")),
            prompt=data.get("prompt", ""),
            answer=data.get("answer", ""),
            options=data.get("options", []),
            explanation=data.get("explanation", ""),
            difficulty=Difficulty(data.get("difficulty", "EASY")),
            competency=CompetencyCategory(data.get("competency", "Understand")),
            marks=int(data.get("marks", 1)),
            source=SourceMetadata.from_dict(data["source"]) if data.get("source") else None,
            verified=data.get("verified", False),
            verified_at=data.get("verified_at"),
            ai_generation_notes=data.get("ai_generation_notes"),
            scenario=data.get("scenario"),
            rubric=data.get("rubric"),
            linked_concepts=data.get("linked_concepts", []),
        )


@dataclass
class Chapter:
    """A curriculum chapter containing concepts, objectives, activities and sims."""
    chapter_id: str
    class_level: str  # "Class IX" | "Class X"
    subject_slug: str
    chapter_number: int
    title: str
    summary: str = ""
    description: str = ""
    concepts: list[Concept] = field(default_factory=list)
    sub_concepts: list[SubConcept] = field(default_factory=list)
    learning_objectives: list[LearningObjective] = field(default_factory=list)
    activities: list[Activity] = field(default_factory=list)
    simulation_mappings: list[SimulationMapping] = field(default_factory=list)
    difficulty: Difficulty = Difficulty.MEDIUM
    prerequisites: list[str] = field(default_factory=list)  # chapter_ids
    competencies: list[CompetencyCategory] = field(default_factory=list)
    lesson_ids: list[str] = field(default_factory=list)  # traceability to legacy lessons
    source: SourceMetadata | None = None
    verified: bool = False
    verified_at: str | None = None
    ai_generation_notes: str | None = None

    def to_dict(self) -> dict:
        d = {
            "chapter_id": self.chapter_id,
            "class_level": self.class_level,
            "subject_slug": self.subject_slug,
            "chapter_number": self.chapter_number,
            "title": self.title,
            "summary": self.summary,
            "description": self.description,
            "difficulty": self.difficulty.value,
            "prerequisites": self.prerequisites,
            "competencies": [c.value for c in self.competencies],
            "concepts": [c.to_dict() for c in self.concepts],
            "sub_concepts": [s.to_dict() for s in self.sub_concepts],
            "learning_objectives": [o.to_dict() for o in self.learning_objectives],
            "activities": [a.to_dict() for a in self.activities],
            "simulation_mappings": [s.to_dict() for s in self.simulation_mappings],
            "lesson_ids": self.lesson_ids,
            "verified": self.verified,
        }
        if self.source:
            d["source"] = self.source.to_dict()
        if self.verified_at:
            d["verified_at"] = self.verified_at
        if self.ai_generation_notes:
            d["ai_generation_notes"] = self.ai_generation_notes
        return d

    @classmethod
    def from_dict(cls, data: dict) -> Chapter:
        return cls(
            chapter_id=data["chapter_id"],
            class_level=data.get("class_level", "Class X"),
            subject_slug=data.get("subject_slug", ""),
            chapter_number=int(data.get("chapter_number", 0)),
            title=data["title"],
            summary=data.get("summary", ""),
            description=data.get("description", ""),
            concepts=[Concept.from_dict(c) for c in data.get("concepts", [])],
            sub_concepts=[SubConcept.from_dict(s) for s in data.get("sub_concepts", [])],
            learning_objectives=[LearningObjective.from_dict(o) for o in data.get("learning_objectives", [])],
            activities=[Activity.from_dict(a) for a in data.get("activities", [])],
            simulation_mappings=[SimulationMapping.from_dict(s) for s in data.get("simulation_mappings", [])],
            difficulty=Difficulty(data.get("difficulty", "MEDIUM")),
            prerequisites=data.get("prerequisites", []),
            competencies=[CompetencyCategory(v) for v in data.get("competencies", [])],
            lesson_ids=data.get("lesson_ids", []),
            source=SourceMetadata.from_dict(data["source"]) if data.get("source") else None,
            verified=data.get("verified", False),
            verified_at=data.get("verified_at"),
            ai_generation_notes=data.get("ai_generation_notes"),
        )


@dataclass
class Subject:
    """A subject within a class level (e.g. Mathematics for Class X)."""
    subject_id: str
    class_level: str
    board: Board = Board.CBSE
    slug: str = ""
    name: str = ""
    description: str = ""
    book_id: str = ""
    book_title: str = ""
    publisher: str = "NCERT"
    chapters: list[Chapter] = field(default_factory=list)
    source: SourceMetadata | None = None
    verified: bool = False
    verified_at: str | None = None

    def to_dict(self) -> dict:
        d = {
            "subject_id": self.subject_id,
            "class_level": self.class_level,
            "board": self.board.value,
            "slug": self.slug,
            "name": self.name,
            "description": self.description,
            "book_id": self.book_id,
            "book_title": self.book_title,
            "publisher": self.publisher,
            "verified": self.verified,
            "chapters": [c.to_dict() for c in self.chapters],
        }
        if self.source:
            d["source"] = self.source.to_dict()
        if self.verified_at:
            d["verified_at"] = self.verified_at
        return d

    @classmethod
    def from_dict(cls, data: dict) -> Subject:
        return cls(
            subject_id=data["subject_id"],
            class_level=data.get("class_level", "Class X"),
            board=Board(data.get("board", "CBSE")),
            slug=data.get("slug", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            book_id=data.get("book_id", ""),
            book_title=data.get("book_title", ""),
            publisher=data.get("publisher", "NCERT"),
            chapters=[Chapter.from_dict(c) for c in data.get("chapters", [])],
            source=SourceMetadata.from_dict(data["source"]) if data.get("source") else None,
            verified=data.get("verified", False),
            verified_at=data.get("verified_at"),
        )


@dataclass
class CurriculumPackage:
    """Top-level container for a versioned curriculum package (one per class)."""
    schema_version: str = CANONICAL_SCHEMA_VERSION
    board: Board = Board.CBSE
    class_level: str = "Class X"
    academic_year: str = "2026-27"
    package_id: str = ""
    version: str = "1.0.0"
    source_version: str = ""
    generated_at: str | None = None
    generated_by: str = "human"  # human | ai_assisted | hybrid
    subjects: list[Subject] = field(default_factory=list)
    source: SourceMetadata | None = None
    verified: bool = False
    verified_at: str | None = None
    ai_generation_notes: str | None = None

    def to_dict(self) -> dict:
        d = {
            "schema_version": self.schema_version,
            "board": self.board.value,
            "class_level": self.class_level,
            "academic_year": self.academic_year,
            "package_id": self.package_id,
            "version": self.version,
            "source_version": self.source_version,
            "generated_at": self.generated_at,
            "generated_by": self.generated_by,
            "verified": self.verified,
            "subjects": [s.to_dict() for s in self.subjects],
        }
        if self.source:
            d["source"] = self.source.to_dict()
        if self.verified_at:
            d["verified_at"] = self.verified_at
        if self.ai_generation_notes:
            d["ai_generation_notes"] = self.ai_generation_notes
        return d

    @classmethod
    def from_dict(cls, data: dict) -> CurriculumPackage:
        return cls(
            schema_version=data.get("schema_version", CANONICAL_SCHEMA_VERSION),
            board=Board(data.get("board", "CBSE")),
            class_level=data.get("class_level", "Class X"),
            academic_year=data.get("academic_year", "2026-27"),
            package_id=data.get("package_id", ""),
            version=data.get("version", "1.0.0"),
            source_version=data.get("source_version", ""),
            generated_at=data.get("generated_at"),
            generated_by=data.get("generated_by", "human"),
            subjects=[Subject.from_dict(s) for s in data.get("subjects", [])],
            source=SourceMetadata.from_dict(data["source"]) if data.get("source") else None,
            verified=data.get("verified", False),
            verified_at=data.get("verified_at"),
            ai_generation_notes=data.get("ai_generation_notes"),
        )


def load_schema_doc() -> dict:
    """Return the machine-readable schema document for external consumers."""
    if SCHEMA_DOC.exists():
        return json.loads(SCHEMA_DOC.read_text(encoding="utf-8"))
    return {
        "schema_version": CANONICAL_SCHEMA_VERSION,
        "description": "Canonical CBSE/NCERT curriculum schema for LearnCraft.",
        "pipeline_stages": ["RAW", "EXTRACT", "VERIFY", "IMPORT", "RUNTIME"],
        "entities": {
            "CurriculumPackage": {
                "fields": ["schema_version", "board", "class_level", "academic_year",
                           "package_id", "version", "source_version", "generated_at",
                           "generated_by", "source", "verified", "verified_at",
                           "ai_generation_notes", "subjects"],
            },
            "Subject": {
                "fields": ["subject_id", "class_level", "board", "slug", "name",
                           "description", "book_id", "book_title", "publisher",
                           "source", "verified", "verified_at", "chapters"],
            },
            "Chapter": {
                "fields": ["chapter_id", "class_level", "subject_slug", "chapter_number",
                           "title", "summary", "description", "concepts", "sub_concepts",
                           "learning_objectives", "activities", "simulation_mappings",
                           "difficulty", "prerequisites", "competencies", "lesson_ids",
                           "source", "verified", "verified_at"],
            },
            "Concept": {
                "fields": ["concept_id", "title", "description", "explanation",
                           "difficulty", "learning_objectives", "prerequisites",
                           "next_concepts", "competencies", "activities",
                           "simulation_mappings", "question_ids", "source_metadata",
                           "verified", "verified_by", "verified_at", "ai_generation_notes"],
            },
            "SubConcept": {
                "fields": ["sub_concept_id", "concept_id", "title", "description",
                           "order", "verified"],
            },
            "LearningObjective": {
                "fields": ["objective_id", "concept_id", "statement",
                           "bloom_level", "verified"],
            },
            "Activity": {
                "fields": ["activity_id", "concept_id", "title", "activity_type",
                           "description", "duration_minutes", "verified"],
            },
            "SimulationMapping": {
                "fields": ["mapping_id", "concept_id", "simulation_id", "title",
                           "mapping_type", "verified"],
            },
            "Question": {
                "fields": ["question_id", "concept_id", "chapter_id", "question_type",
                           "prompt", "answer", "options", "explanation", "difficulty",
                           "competency", "marks", "source", "verified", "verified_at",
                           "ai_generation_notes", "scenario", "rubric", "linked_concepts"],
            },
            "SourceMetadata": {
                "fields": ["source_id", "source_type", "title", "publisher", "url",
                           "version", "academic_year", "accessed_at",
                           "checksum_sha256", "notes"],
            },
        },
    }


def generate_schema_doc(path: Path | None = None) -> dict:
    """Generate and optionally write the schema documentation file."""
    doc = load_schema_doc()
    target = path or SCHEMA_DOC
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    return doc