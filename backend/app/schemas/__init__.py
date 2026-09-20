"""Schema package for API validation and curriculum definitions."""

from .auth import LoginRequest, RegisterRequest
from .user import ProfileUpdateRequest, UserOut
from .curriculum import (
    Difficulty,
    QuestionType,
    CompetencyCategory,
    Board,
    VerificationStatus,
    CANONICAL_SCHEMA_VERSION,
    SourceMetadata,
    Concept,
    SubConcept,
    LearningObjective,
    Activity,
    SimulationMapping,
    Question,
    Chapter,
    Subject,
    CurriculumPackage,
    load_schema_doc,
    generate_schema_doc,
)

__all__ = [
    "LoginRequest",
    "RegisterRequest",
    "ProfileUpdateRequest",
    "UserOut",
    "Difficulty",
    "QuestionType",
    "CompetencyCategory",
    "Board",
    "VerificationStatus",
    "CANONICAL_SCHEMA_VERSION",
    "SourceMetadata",
    "Concept",
    "SubConcept",
    "LearningObjective",
    "Activity",
    "SimulationMapping",
    "Question",
    "Chapter",
    "Subject",
    "CurriculumPackage",
    "load_schema_doc",
    "generate_schema_doc",
]
