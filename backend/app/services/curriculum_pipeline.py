"""Curriculum pipeline services for versioned class packages.

Consumes ``data/curriculum/class<N>/`` packages produced by
``scripts/build_class10_package.py`` and provides:

- package loading (offline, filesystem only)
- concept graph construction and queries (prerequisites / next concepts)
- learning-roadmap generation from the concept graph
- simulation registry access (concept_id -> simulation_id)
- strict pre-import validation

The legacy ``data/curriculum/*.json`` loader in ``content_catalog`` remains
untouched; this module is the canonical path for versioned packages.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from app.schemas.curriculum import (
    CANONICAL_SCHEMA_VERSION, CurriculumPackage, Question, QuestionType,
    Difficulty, CompetencyCategory,
)

ROOT = Path(__file__).resolve().parents[2]
CURRICULUM_DIR = ROOT / "data" / "curriculum"

VALID_DIFFICULTIES = {d.value for d in Difficulty}
VALID_COMPETENCIES = {c.value for c in CompetencyCategory}
VALID_QUESTION_TYPES = {t.value for t in QuestionType}


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def available_class_dirs() -> list[Path]:
    """Return every versioned class package directory (class9, class10, ...)."""
    if not CURRICULUM_DIR.exists():
        return []
    return sorted(p for p in CURRICULUM_DIR.iterdir()
                  if p.is_dir() and p.name.startswith("class"))


def load_manifest(class_dir: Path) -> dict:
    with open(class_dir / "manifest.json", encoding="utf-8") as fh:
        return json.load(fh)


def load_class_package(class_dir: Path) -> CurriculumPackage:
    """Load one versioned class package into canonical objects."""
    return CurriculumPackage.from_dict(load_manifest(class_dir))


def load_all_packages() -> dict[str, CurriculumPackage]:
    """Load every versioned package, keyed by class level (e.g. 'Class X')."""
    packages: dict[str, CurriculumPackage] = {}
    for class_dir in available_class_dirs():
        if not (class_dir / "manifest.json").exists():
            continue
        pkg = load_class_package(class_dir)
        packages[pkg.class_level] = pkg
    return packages


def load_question_bank(class_dir: Path) -> list[Question]:
    path = class_dir / "question_bank.json"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return [Question.from_dict(q) for q in data.get("questions", [])]


def load_concept_graph(class_dir: Path) -> dict:
    path = class_dir / "concept_graph.json"
    if not path.exists():
        return {"nodes": [], "label_prerequisites": []}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_simulation_registry(class_dir: Path) -> dict:
    path = class_dir / "simulation_registry.json"
    if not path.exists():
        return {"catalog": [], "mappings": []}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_roadmap(class_dir: Path) -> dict:
    """Read the persisted roadmap for a class package (generated, never hand-written)."""
    path = class_dir / "roadmap.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


# Runtime helpers (offline): heavy JSON files are cached per (path, mtime) so the
# API can serve the question bank repeatedly without reparsing megabytes each call.

_JSON_CACHE: dict[tuple[str, float], object] = {}


def _read_json_cached(path: Path):
    key = (str(path), path.stat().st_mtime)
    cached = _JSON_CACHE.get(key)
    if cached is None:
        with open(path, encoding="utf-8") as fh:
            cached = json.load(fh)
        # Keep the cache tiny; packages are large and rarely change.
        if len(_JSON_CACHE) > 8:
            _JSON_CACHE.clear()
        _JSON_CACHE[key] = cached
    return cached


def load_question_bank_cached(class_dir: Path) -> list[Question]:
    """Cached variant of :func:`load_question_bank` for request-time use."""
    path = class_dir / "question_bank.json"
    if not path.exists():
        return []
    data = _read_json_cached(path)
    return [Question.from_dict(q) for q in data.get("questions", [])]


def resolve_class_dir(class_name: str | None = None) -> Path | None:
    """Resolve ``class10`` / ``Class X`` / ``cbse-class-x-2026-27`` to a package dir.

    Returns ``None`` when no versioned package exists. Defaults to the first
    available package so callers can omit the class selector entirely.
    """
    dirs = available_class_dirs()
    if not dirs:
        return None
    if not class_name:
        return dirs[0]
    needle = class_name.strip().lower().replace(" ", "").replace("_", "")
    for class_dir in dirs:
        manifest_path = class_dir / "manifest.json"
        candidates = {class_dir.name.lower(), class_dir.name.lower().replace("class", "class")}
        if manifest_path.exists():
            try:
                manifest = _read_json_cached(manifest_path)
            except (ValueError, OSError):
                manifest = {}
            for key in ("class_level", "package_id"):
                value = str(manifest.get(key, "")).lower().replace(" ", "").replace("-", "")
                candidates.add(value)
                candidates.add(value.replace("classx", "class10").replace("classix", "class9"))
        normalized = {c.replace("-", "") for c in candidates}
        if needle in normalized or needle.replace("-", "") in normalized:
            return class_dir
    return None




# ---------------------------------------------------------------------------
# Concept graph
# ---------------------------------------------------------------------------

@dataclass
class ConceptGraph:
    """Directed prerequisite graph over concept ids."""
    nodes: dict[str, dict] = field(default_factory=dict)
    prerequisites: dict[str, list[str]] = field(default_factory=dict)
    next_concepts: dict[str, list[str]] = field(default_factory=dict)

    @classmethod
    def from_graph_data(cls, graph_data: dict) -> ConceptGraph:
        g = cls()
        for node in graph_data.get("nodes", []):
            cid = node["concept_id"]
            g.nodes[cid] = node
            g.prerequisites[cid] = list(node.get("prerequisites", []))
            g.next_concepts[cid] = list(node.get("next_concepts", []))
        return g

    @classmethod
    def from_package(cls, pkg: CurriculumPackage) -> ConceptGraph:
        g = cls()
        for subject in pkg.subjects:
            for chapter in subject.chapters:
                for concept in chapter.concepts:
                    g.nodes[concept.concept_id] = concept.to_dict()
                    g.prerequisites[concept.concept_id] = list(concept.prerequisites)
                    g.next_concepts[concept.concept_id] = list(concept.next_concepts)
        return g

    def prerequisites_of(self, concept_id: str) -> list[str]:
        return list(self.prerequisites.get(concept_id, []))

    def next_of(self, concept_id: str) -> list[str]:
        return list(self.next_concepts.get(concept_id, []))

    def topological_order(self) -> list[str]:
        """Kahn topological sort; unknown prereqs ignored, cycles raise ValueError."""
        indegree = {cid: 0 for cid in self.nodes}
        for cid, pres in self.prerequisites.items():
            for p in pres:
                if p in indegree:
                    indegree[cid] += 1
        queue = [cid for cid in self.nodes if indegree[cid] == 0]
        order: list[str] = []
        while queue:
            cid = queue.pop(0)
            order.append(cid)
            for nxt in self.next_concepts.get(cid, []):
                if nxt in indegree:
                    indegree[nxt] -= 1
                    if indegree[nxt] == 0 and nxt not in order:
                        queue.append(nxt)
        if len(order) != len(self.nodes):
            cyclic = sorted(set(self.nodes) - set(order))
            raise ValueError(f"cycle detected in concept graph: {cyclic}")
        return order

    def ancestors_of(self, concept_id: str) -> set[str]:
        seen: set[str] = set()
        stack = list(self.prerequisites.get(concept_id, []))
        while stack:
            cid = stack.pop()
            if cid in seen or cid not in self.nodes:
                continue
            seen.add(cid)
            stack.extend(self.prerequisites.get(cid, []))
        return seen


def build_concept_graph(class_dir: Path) -> ConceptGraph:
    return ConceptGraph.from_graph_data(load_concept_graph(class_dir))


# ---------------------------------------------------------------------------
# Roadmap generation + simulation registry
# ---------------------------------------------------------------------------

def generate_roadmap(pkg: CurriculumPackage, graph: ConceptGraph) -> dict:
    """Generate the term-wise roadmap from the concept graph (never hardcoded)."""
    subjects_out = []
    for subject in pkg.subjects:
        chapters = sorted(subject.chapters, key=lambda c: c.chapter_number)
        half = (len(chapters) + 1) // 2
        terms = [chapters[:half], chapters[half:]]
        terms_out = []
        for term_index, term_chapters in enumerate(terms, start=1):
            ch_entries = []
            for ch in term_chapters:
                concepts = []
                for con in ch.concepts:
                    node = graph.nodes.get(con.concept_id, {})
                    concepts.append({
                        "concept_id": con.concept_id,
                        "title": con.title,
                        "prerequisites": graph.prerequisites_of(con.concept_id),
                        "next_concepts": graph.next_of(con.concept_id),
                        "difficulty": con.difficulty.value,
                        "estimated_minutes": node.get("estimated_minutes"),
                        "simulation_ids": [m.simulation_id for m in ch.simulation_mappings
                                           if m.concept_id == con.concept_id],
                        "question_ids": list(con.question_ids),
                        "verified": con.verified,
                    })
                ch_entries.append({
                    "chapter_id": ch.chapter_id,
                    "chapter_number": ch.chapter_number,
                    "title": ch.title,
                    "difficulty": ch.difficulty.value,
                    "lesson_ids": list(ch.lesson_ids),
                    "concepts": concepts,
                })
            terms_out.append({"term": term_index, "chapters": ch_entries})
        subjects_out.append({
            "subject_slug": subject.slug,
            "subject_id": subject.subject_id,
            "name": subject.name,
            "terms": terms_out,
        })
    return {
        "class_level": pkg.class_level,
        "academic_year": pkg.academic_year,
        "generated_from": "concept_graph.json",
        "algorithm": "concept-chain topological order (documented deterministic rule)",
        "subjects": subjects_out,
    }


def simulations_for_concept(class_dir: Path, concept_id: str) -> list[dict]:
    """Resolve concept_id -> simulation entries from the registry (offline)."""
    registry = load_simulation_registry(class_dir)
    catalog = {s["simulation_id"]: s for s in registry.get("catalog", [])}
    return [
        {**catalog.get(m["simulation_id"], {}),
         "mapping_type": m.get("mapping_type", "exploration")}
        for m in registry.get("mappings", [])
        if m.get("concept_id") == concept_id
    ]


# ---------------------------------------------------------------------------
# Strict validation
# ---------------------------------------------------------------------------

def validate_class_package(pkg: CurriculumPackage,
                           question_bank: list[Question] | None = None,
                           registry: dict | None = None) -> list[str]:
    """Strict validation of a versioned package. Returns a list of errors.

    Checks: duplicate IDs, invalid concept references, missing prerequisites,
    invalid question answers, invalid simulation references and missing
    source metadata.
    """
    errors: list[str] = []

    concept_ids: set[str] = set()
    chapter_ids: set[str] = set()
    objective_ids: set[str] = set()
    activity_ids: set[str] = set()
    mapping_ids: set[str] = set()
    question_ids: set[str] = set()

    known_simulation_ids = {s.get("simulation_id") for s in (registry or {}).get("catalog", [])}
    all_concept_ids = {c.concept_id for s in pkg.subjects for ch in s.chapters for c in ch.concepts}

    def check_source(src, label: str) -> None:
        if src is None:
            errors.append(f"missing source metadata: {label}")
        else:
            for key in ("source_id", "source_type", "title"):
                if not getattr(src, key, None):
                    errors.append(f"incomplete source metadata: {label} ({key})")

    for subject in pkg.subjects:
        for chapter in subject.chapters:
            if chapter.chapter_id in chapter_ids:
                errors.append(f"duplicate chapter ID: {chapter.chapter_id}")
            chapter_ids.add(chapter.chapter_id)
            check_source(chapter.source, f"chapter.{chapter.chapter_id}")

            for con in chapter.concepts:
                if con.concept_id in concept_ids:
                    errors.append(f"duplicate concept ID: {con.concept_id}")
                concept_ids.add(con.concept_id)
                check_source(con.source_metadata, f"concept.{con.concept_id}")
                for ref in con.prerequisites:
                    if ref not in all_concept_ids:
                        errors.append(f"invalid concept reference: {con.concept_id} "
                                      f"prerequisite {ref} not defined")
                for ref in con.next_concepts:
                    if ref not in all_concept_ids:
                        errors.append(f"invalid concept reference: {con.concept_id} "
                                      f"next_concept {ref} not defined")

            for sub in chapter.sub_concepts:
                if sub.concept_id not in all_concept_ids:
                    errors.append(f"invalid concept reference: sub_concept "
                                  f"{sub.sub_concept_id} parent {sub.concept_id} not defined")
            for obj in chapter.learning_objectives:
                if obj.objective_id in objective_ids:
                    errors.append(f"duplicate objective ID: {obj.objective_id}")
                objective_ids.add(obj.objective_id)
                if obj.concept_id and obj.concept_id not in all_concept_ids:
                    errors.append(f"invalid concept reference: objective {obj.objective_id} "
                                  f"concept {obj.concept_id} not defined")
            for act in chapter.activities:
                if act.activity_id in activity_ids:
                    errors.append(f"duplicate activity ID: {act.activity_id}")
                activity_ids.add(act.activity_id)
                if act.concept_id and act.concept_id not in all_concept_ids:
                    errors.append(f"invalid concept reference: activity {act.activity_id} "
                                  f"concept {act.concept_id} not defined")
            for mapping in chapter.simulation_mappings:
                if mapping.mapping_id in mapping_ids:
                    errors.append(f"duplicate simulation mapping ID: {mapping.mapping_id}")
                mapping_ids.add(mapping.mapping_id)
                if mapping.concept_id not in all_concept_ids:
                    errors.append(f"invalid concept reference: mapping {mapping.mapping_id} "
                                  f"concept {mapping.concept_id} not defined")
                if known_simulation_ids and mapping.simulation_id not in known_simulation_ids:
                    errors.append(f"invalid simulation reference: mapping {mapping.mapping_id} "
                                  f"simulation {mapping.simulation_id} not in registry catalog")

    for question in (question_bank or []):
        if question.question_id in question_ids:
            errors.append(f"duplicate question ID: {question.question_id}")
        question_ids.add(question.question_id)
        if not question.prompt:
            errors.append(f"invalid question: {question.question_id} has empty prompt")
        if not question.answer:
            errors.append(f"invalid question answer: {question.question_id} has empty answer")
        if question.question_type in (QuestionType.MCQ, QuestionType.MULTIPLE_CORRECT) \
                and not question.is_valid_mcq():
            errors.append(f"invalid question answer: {question.question_id} MCQ options invalid")
        if question.question_type == QuestionType.TRUE_FALSE and \
                str(question.answer).strip().lower() not in ("true", "false"):
            errors.append(f"invalid question answer: {question.question_id} TRUE_FALSE "
                          f"answer must be true/false")
        if question.difficulty.value not in VALID_DIFFICULTIES:
            errors.append(f"invalid difficulty: {question.question_id}")
        if question.competency.value not in VALID_COMPETENCIES:
            errors.append(f"invalid competency: {question.question_id}")
        if question.question_type.value not in VALID_QUESTION_TYPES:
            errors.append(f"invalid question type: {question.question_id}")
        if question.concept_id and question.concept_id not in concept_ids:
            errors.append(f"invalid concept reference: question {question.question_id} "
                          f"concept {question.concept_id} not defined")
        check_source(question.source, f"question.{question.question_id}")

    # Graph-wide integrity: a topological order must exist (no cycles).
    if concept_ids:
        graph = ConceptGraph()
        graph.nodes = {cid: {} for cid in concept_ids}
        for subject in pkg.subjects:
            for chapter in subject.chapters:
                for con in chapter.concepts:
                    graph.prerequisites[con.concept_id] = list(con.prerequisites)
                    graph.next_concepts[con.concept_id] = list(con.next_concepts)
        try:
            graph.topological_order()
        except ValueError as exc:
            errors.append(str(exc))

    return errors


def verify_question(question: Question, reviewer: str, verified_at: str) -> Question:
    """Human verification step: flips a question to verified with provenance."""
    question.verified = True
    question.verified_at = verified_at
    question.ai_generation_notes = (
        f"{question.ai_generation_notes or ''} verified_by={reviewer}").strip()
    return question


def load_roadmap(class_dir: Path) -> dict:
    path = class_dir / "roadmap.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Runtime summaries + generated roadmap
# ---------------------------------------------------------------------------

def package_summary(class_dir: Path) -> dict:
    """Compact, JSON-safe description of one class package (for API listings)."""
    pkg = load_class_package(class_dir)
    manifest_path = class_dir / "manifest.json"
    manifest = _read_json_cached(manifest_path) if manifest_path.exists() else {}
    chapters = sum(len(s.chapters) for s in pkg.subjects)
    concepts = sum(len(c.concepts) for s in pkg.subjects for c in s.chapters)
    questions = 0
    verified_questions = 0
    qb_path = class_dir / "question_bank.json"
    if qb_path.exists():
        bank = _read_json_cached(qb_path).get("questions", [])
        questions = len(bank)
        verified_questions = sum(1 for q in bank if q.get("verified"))
    return {
        "dir": class_dir.name,
        "package_id": pkg.package_id,
        "class_level": pkg.class_level,
        "board": pkg.board.value,
        "academic_year": pkg.academic_year,
        "schema_version": manifest.get("schema_version", CANONICAL_SCHEMA_VERSION),
        "version": manifest.get("version", ""),
        "generated_at": manifest.get("generated_at"),
        "verified": pkg.verified,
        "counts": {
            "subjects": len(pkg.subjects),
            "chapters": chapters,
            "concepts": concepts,
            "questions": questions,
            "questions_verified": verified_questions,
            "questions_unverified": questions - verified_questions,
        },
        "subjects": [{"slug": s.slug, "subject_id": s.subject_id, "name": s.name,
                      "chapters": len(s.chapters)} for s in pkg.subjects],
    }


def build_roadmap_for_class(class_dir: Path) -> dict:
    """Generate the roadmap from the class package + concept graph (on the fly).

    The roadmap is derived, never hardcoded: chapters come from the loaded
    package and concept order/pre-requisites come from the concept graph.
    """
    pkg = load_class_package(class_dir)
    graph = build_concept_graph(class_dir)
    return generate_roadmap(pkg, graph)


def question_bank_summary(class_dir: Path) -> dict:
    """Counts by type/difficulty/competency plus verification status."""
    questions = load_question_bank_cached(class_dir)

    def tally(field: str, getter) -> dict[str, int]:
        counts: dict[str, int] = {}
        for question in questions:
            key = getter(question)
            counts[key] = counts.get(key, 0) + 1
        return dict(sorted(counts.items()))

    return {
        "total": len(questions),
        "verified": sum(1 for q in questions if q.verified),
        "unverified": sum(1 for q in questions if not q.verified),
        "by_type": tally("question_type", lambda q: q.question_type.value),
        "by_difficulty": tally("difficulty", lambda q: q.difficulty.value),
        "by_competency": tally("competency", lambda q: q.competency.value),
    }


def filter_questions(class_dir: Path,
                     chapter_id: str | None = None,
                     concept_id: str | None = None,
                     question_type: str | None = None,
                     difficulty: str | None = None,
                     competency: str | None = None,
                     verified: bool | None = None,
                     limit: int | None = None) -> list[Question]:
    """Filter the question bank (offline, in-memory) for API consumers."""
    questions = load_question_bank_cached(class_dir)
    selected = []
    for question in questions:
        if chapter_id and question.chapter_id != chapter_id:
            continue
        if concept_id and question.concept_id != concept_id:
            continue
        if question_type and question.question_type.value != question_type:
            continue
        if difficulty and question.difficulty.value != difficulty.upper():
            continue
        if competency and question.competency.value != competency:
            continue
        if verified is not None and question.verified is not verified:
            continue
        selected.append(question)
        if limit is not None and len(selected) >= limit:
            break
    return selected