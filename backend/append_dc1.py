#!/usr/bin/env python3
"""Append dataclasses part 1 - Concept, SubConcept, LearningObjective."""
from pathlib import Path

p = Path('app/schemas/curriculum.py')

code = '''
@dataclass
class Concept:
    """A curriculum concept with prerequisites and competencies."""
    concept_id: str
    title: str
    description: str | None = None
    explanation: str | None = None
    difficulty: Difficulty = Difficulty.EASY
    learning_objectives: list[str] = field(default_factory=list)
    prerequisites: list[str] = field(default_factory=list)
    next_concepts: list[str] = field(default_factory=list)
    competencies: list[CompetencyCategory] = field(default_factory=list)
    activities: list[str] = field(default_factory=list)
    simulation_ids: list[str] = field(default_factory=list)
    source: SourceMetadata | None = None
    verified: bool = False
    verified_at: str | None = None
    ai_generation_notes: str | None = None

    def to_dict(self) -> dict:
        d = {"concept_id": self.concept_id, "title": self.title, "verified": self.verified}
        if self.description: d["description"] = self.description
        if self.explanation: d["explanation"] = self.explanation
        d["difficulty"] = self.difficulty.value
        if self.learning_objectives: d["learning_objectives"] = self.learning_objectives
        if self.prerequisites: d["prerequisites"] = self.prerequisites
        if self.next_concepts: d["next_concepts"] = self.next_concepts
        if self.competencies: d["competencies"] = [c.value for c in self.competencies]
        if self.activities: d["activities"] = self.activities
        if self.simulation_ids: d["simulation_ids"] = self.simulation_ids
        if self.source: d["source"] = self.source.to_dict()
        if self.verified_at: d["verified_at"] = self.verified_at
        if self.ai_generation_notes: d["ai_generation_notes"] = self.ai_generation_notes
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "Concept":
        comps = [CompetencyCategory(v) for v in data.get("competencies", [])]
        return cls(
            concept_id=data["concept_id"], title=data["title"],
            description=data.get("description"), explanation=data.get("explanation"),
            difficulty=Difficulty(data.get("difficulty", "EASY")),
            learning_objectives=data.get("learning_objectives", []),
            prerequisites=data.get("prerequisites", []),
            next_concepts=data.get("next_concepts", []),
            competencies=comps, activities=data.get("activities", []),
            simulation_ids=data.get("simulation_ids", []),
            source=SourceMetadata.from_dict(data["source"]) if data.get("source") else None,
            verified=data.get("verified", False), verified_at=data.get("verified_at"),
            ai_generation_notes=data.get("ai_generation_notes"),
        )


@dataclass
class SubConcept:
    """A finer-grained sub-division of a concept."""
    sub_concept_id: str
    concept_id: str
    title: str
    description: str | None = None
    verified: bool = False

    def to_dict(self) -> dict:
        d = {"sub_concept_id": self.sub_concept_id, "concept_id": self.concept_id,
             "title": self.title, "verified": self.verified}
        if self.description: d["description"] = self.description
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "SubConcept":
        return cls(sub_concept_id=data["sub_concept_id"], concept_id=data["concept_id"],
                   title=data["title"], description=data.get("description"),
                   verified=data.get("verified", False))


@dataclass
class LearningObjective:
    """A measurable learning objective with Bloom's taxonomy level."""
    code: str
    text: str
    blooms_level: CompetencyCategory | None = None
    concept_id: str | None = None

    def to_dict(self) -> dict:
        d = {"code": self.code, "text": self.text}
        if self.blooms_level: d["blooms_level"] = self.blooms_level.value
        if self.concept_id: d["concept_id"] = self.concept_id
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "LearningObjective":
        blooms = CompetencyCategory(data["blooms_level"]) if data.get("blooms_level") else None
        return cls(code=data["code"], text=data["text"], blooms_level=blooms,
                   concept_id=data.get("concept_id"))

'''

p.write_text(p.read_text(encoding='utf-8') + code, encoding='utf-8')
print(f"Added Concept, SubConcept, LearningObjective: {len(p.read_text().splitlines())} lines")
