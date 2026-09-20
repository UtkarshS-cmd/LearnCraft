"""Build the versioned Class X curriculum package from existing repo data.

Deterministic builder: reads the legacy CBSE Class X seed files under
``data/curriculum/`` and emits a canonical, schema-valid package under
``data/curriculum/class10/``:

    class10/
        manifest.json          package metadata + verification summary
        subjects/*.json        canonical subject/chapter/concept files
        concept_graph.json     concept -> prerequisites -> next concepts
        simulation_registry.json  bundled sandbox catalog + concept mappings
        question_bank.json     questions with metadata + verification status
        roadmap.json           GENERATED from concept_graph.json

Nothing is invented: every chapter, concept, objective and question is
derived from the in-repo sources; derived orderings (prerequisite chains,
term splits) follow documented deterministic rules and preserve the original
source statements for human review.

Run:  python scripts/build_class10_package.py
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CUR = ROOT / "data" / "curriculum"
OUT = CUR / "class10"

sys.path.insert(0, str(ROOT))

from app.schemas.curriculum import (  # noqa: E402
    CANONICAL_SCHEMA_VERSION, Board, CompetencyCategory, Difficulty, QuestionType,
    SourceMetadata, Concept, SubConcept, LearningObjective, Activity,
    SimulationMapping, Question, Chapter, Subject, CurriculumPackage,
)

PACKAGE_ID = "cbse-class-x-2026-27"
YEAR = "2026-27"
CLASS_LEVEL = "Class X"

SKILL_TO_COMPETENCY = {
    "remember": CompetencyCategory.REMEMBER,
    "recall": CompetencyCategory.REMEMBER,
    "understand": CompetencyCategory.UNDERSTAND,
    "compare": CompetencyCategory.UNDERSTAND,
    "apply": CompetencyCategory.APPLY,
    "analyze": CompetencyCategory.ANALYSE if hasattr(CompetencyCategory, "ANALYSE") else CompetencyCategory.ANALYZE,
    "analyse": CompetencyCategory.ANALYZE,
    "evaluate": CompetencyCategory.EVALUATE,
    "create": CompetencyCategory.CREATE,
}

DIFFICULTY_MAP = {"easy": Difficulty.EASY, "medium": Difficulty.MEDIUM, "hard": Difficulty.HARD}

# Bundled offline sandboxes shipped with the repo (never fetched at runtime).
SIMULATION_CATALOG = [
    {
        "simulation_id": "sim-sandbox-math",
        "title": "Math Adventure Lab",
        "url_fragment": "static/sandbox-games/math/index.html",
        "offline": True,
        "domains": ["mathematics"],
    },
    {
        "simulation_id": "sim-sandbox-physics",
        "title": "Physics Adventure Lab",
        "url_fragment": "static/sandbox-games/physics/index.html",
        "offline": True,
        "domains": ["science"],
    },
    {
        "simulation_id": "sim-sandbox-circuits",
        "title": "Electrical Circuits Lab",
        "url_fragment": "static/sandbox-games/circuits/index.html",
        "offline": True,
        "domains": ["science"],
    },
    {
        "simulation_id": "sim-sandbox-coding",
        "title": "Coding Adventure",
        "url_fragment": "static/sandbox-games/coding/index.html",
        "offline": True,
        "domains": [],
    },
]

# Deterministic mapping rules: (simulation_id, chapter-title regex, subject slug or None).
# Only rule that currently matches the dataset is the general math sandbox.
SIM_MAPPING_RULES = [
    ("sim-sandbox-math", None, "mathematics"),
]


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()




def convert_subject(manifest_subject: dict, legacy_path: Path):
    """Convert one legacy subject file into canonical subject + chain + questions."""
    legacy = load_json(legacy_path)
    checksum = sha256_of(legacy_path)
    source = SourceMetadata(
        source_id=f"ncert-x-{manifest_subject['slug']}-{YEAR}",
        source_type="ncert_textbook",
        title=manifest_subject.get("book_title", "NCERT Textbook"),
        publisher=manifest_subject.get("publisher", "NCERT"),
        url=manifest_subject.get("source_reference"),
        version=YEAR,
        academic_year=YEAR,
        checksum_sha256=checksum,
        notes=f"Derived from {legacy_path.name} (in-repo seed package).",
    ).to_dict()

    # Pass 1: ordered concept chain + human-readable prerequisite labels.
    chain: list[dict] = []
    label_prereq_edges: list[dict] = []
    for chapter in legacy.get("chapters", []):
        label_prereq_edges.append({"chapter_id": chapter["chapter_id"], "labels": []})
        for topic in chapter.get("topics", []):
            for lesson in topic.get("lessons", []):
                for label in lesson.get("prerequisites", []):
                    label_prereq_edges[-1]["labels"].append(
                        {"lesson_id": lesson["lesson_id"], "prerequisite_label": label}
                    )
                for con in lesson.get("concepts", []):
                    chain.append({
                        "concept_id": con["concept_id"],
                        "title": con.get("title", ""),
                        "explanation": con.get("explanation", ""),
                        "chapter_id": chapter["chapter_id"],
                        "lesson_id": lesson["lesson_id"],
                        "difficulty": lesson.get("difficulty", "MEDIUM"),
                        "estimated_minutes": lesson.get("estimated_minutes"),
                    })

    # Link the subject-wide concept chain deterministically:
    # prerequisites = direct predecessor, next_concepts = direct successor.
    for i, node in enumerate(chain):
        node["prerequisites"] = [chain[i - 1]["concept_id"]] if i > 0 else []
        node["next_concepts"] = [chain[i + 1]["concept_id"]] if i + 1 < len(chain) else []

    chapters_out: list[dict] = []
    all_questions: list[Question] = []

    for chapter in legacy.get("chapters", []):
        chapter_id = chapter["chapter_id"]
        ch_nodes = [n for n in chain if n["chapter_id"] == chapter_id]
        objectives, activities, obj_by_concept, concept_by_lesson = \
            _chapter_objectives_activities(chapter, chapter_id)
        ch_questions, ch_competencies = _chapter_questions(
            chapter, chapter_id, source, concept_by_lesson)
        all_questions.extend(ch_questions)

        ch_concepts: list[Concept] = []
        for node in ch_nodes:
            node_source = dict(source)
            node_source["notes"] = (
                f"{source.get('notes', '')} | concept '{node['title']}' "
                f"(lesson {node['lesson_id']})."
            ).strip(" |")
            ch_concepts.append(Concept(
                concept_id=node["concept_id"],
                title=node["title"],
                description=node["explanation"],
                explanation=node["explanation"],
                difficulty=Difficulty(str(node["difficulty"]).upper()),
                learning_objectives=obj_by_concept.get(node["concept_id"], []),
                prerequisites=list(node["prerequisites"]),
                next_concepts=list(node["next_concepts"]),
                question_ids=[q.question_id for q in ch_questions
                              if q.concept_id == node["concept_id"]],
                competencies=[CompetencyCategory.UNDERSTAND],
                source_metadata=SourceMetadata(**node_source),
                verified=True,
            ))

        ch_subconcepts: list[SubConcept] = []
        for topic in chapter.get("topics", []):
            for lesson in topic.get("lessons", []):
                cid = concept_by_lesson.get(lesson["lesson_id"])
                if not cid:
                    continue
                ch_subconcepts.append(SubConcept(
                    sub_concept_id=f"{lesson['lesson_id']}-sc",
                    concept_id=cid,
                    title=lesson.get("title", ""),
                    description=lesson.get("summary", ""),
                    order=len(ch_subconcepts) + 1,
                    verified=True,
                ))

        # Deterministic simulation mappings (rule-based, no scraping).
        ch_sims: list[SimulationMapping] = []
        for sim_id, _regex, subject_match in SIM_MAPPING_RULES:
            if subject_match and manifest_subject["slug"] != subject_match:
                continue
            for con in ch_concepts:
                ch_sims.append(SimulationMapping(
                    mapping_id=f"{con.concept_id}-sim",
                    concept_id=con.concept_id,
                    simulation_id=sim_id,
                    title="Math Adventure Lab",
                    mapping_type="practice",
                    verified=True,
                ))

        chapters_out.append(Chapter(
            chapter_id=chapter_id,
            class_level=CLASS_LEVEL,
            subject_slug=manifest_subject["slug"],
            chapter_number=int(chapter["chapter_number"]),
            title=chapter["title"],
            summary=chapter.get("summary", ""),
            description=chapter.get("summary", ""),
            concepts=ch_concepts,
            sub_concepts=ch_subconcepts,
            learning_objectives=objectives,
            activities=activities,
            simulation_mappings=ch_sims,
            difficulty=chapter_difficulty(chapter),
            competencies=sorted(ch_competencies, key=lambda c: c.value),
            lesson_ids=[l["lesson_id"] for t in chapter.get("topics", [])
                        for l in t.get("lessons", [])],
            source=SourceMetadata(**source),
            verified=True,
        ).to_dict())

    subject = Subject(
        subject_id=manifest_subject["subject_id"],
        class_level=CLASS_LEVEL,
        board=Board.CBSE,
        slug=manifest_subject["slug"],
        name=manifest_subject["name"],
        description=manifest_subject.get("description", ""),
        book_id=manifest_subject.get("book_id", ""),
        book_title=manifest_subject.get("book_title", ""),
        publisher=manifest_subject.get("publisher", "NCERT"),
        chapters=[Chapter.from_dict(c) for c in chapters_out],
        source=SourceMetadata(**source),
        verified=True,
    )

    return subject.to_dict(), chain, all_questions, label_prereq_edges


def convert_syllabus_questions(syllabus: dict, known_chapters: dict[str, str]):
    """Convert the extracted NCERT Class X question bank into canonical questions.

    These entries were machine-extracted from NCERT textbook question lists, so
    they are imported with ``verified=False`` (AI_GENERATED status) and carry
    full source metadata (file + checksum) for the human VERIFY stage.
    """
    syllabus_path = CUR / "ncert_class10_syllabus.json"
    checksum = sha256_of(syllabus_path)
    out: list[Question] = []
    slug_for_subject = {"Science": "science", "Social Studies": "social-science"}
    for subject_name, by_class in syllabus.items():
        slug = slug_for_subject.get(subject_name, slugify(subject_name))
        chapters = by_class.get("10") if isinstance(by_class, dict) else None
        if not chapters:
            continue
        for ch in chapters:
            ch_name = ch.get("chapter_name", "")
            # Link to a canonical chapter only when the official name matches.
            key = slugify(ch_name)
            chapter_id = known_chapters.get(key)
            for idx, q in enumerate(ch.get("questions", []), start=1):
                diff = DIFFICULTY_MAP.get(str(q.get("difficulty", "Medium")).lower(),
                                          Difficulty.MEDIUM)
                answer = str(q.get("answer", "") or "").strip()
                if not answer:
                    # Keep the extracted prompt for review but never ship an
                    # empty answer through strict validation: mark it as
                    # pending-answer so a human must fill it at VERIFY time.
                    answer = "PENDING HUMAN REVIEW - answer missing in extraction"
                out.append(Question(
                    question_id=f"cbse-x-{YEAR}-{slug}-q-syl-{ch.get('chapter_number', 0)}-{idx:03d}",
                    chapter_id=chapter_id,
                    question_type=QuestionType.SHORT_ANSWER,
                    prompt=q.get("question", ""),
                    answer=answer,
                    options=[],
                    explanation=q.get("explanation", ""),
                    difficulty=diff,
                    competency=CompetencyCategory.UNDERSTAND,
                    marks=2,
                    source=SourceMetadata(
                        source_id=f"ncert-x-syllabus-{YEAR}",
                        source_type="ncert_syllabus_extraction",
                        title=f"NCERT Class X {subject_name} question bank (extracted)",
                        publisher="NCERT",
                        version=YEAR,
                        academic_year=YEAR,
                        checksum_sha256=checksum,
                        notes=(f"Extracted from ncert_class10_syllabus.json; chapter "
                               f"'{ch_name}'; raw_type={q.get('type')}; "
                               f"student_level={q.get('student_level')}; "
                               f"estimated_time={q.get('estimated_time')}"),
                    ),
                    verified=False,
                    ai_generation_notes="Machine-extracted; awaiting human verification.",
                ))
    return out


def build_roadmap(subject_dicts: list[dict], chains: list[list[dict]]) -> dict:
    """Generate the term-wise learning roadmap from the concept chain.

    Deterministic rule: chapters are ordered by chapter_number and split into
    two terms (first half = Term 1). Concepts carry resolved prerequisites and
    estimated minutes from the source lessons.
    """
    chain_by_concept: dict[str, dict] = {}
    for chain in chains:
        for node in chain:
            chain_by_concept[node["concept_id"]] = node

    subjects_out = []
    for subject in subject_dicts:
        chapters = sorted(subject["chapters"], key=lambda c: c["chapter_number"])
        half = (len(chapters) + 1) // 2
        terms = [{"term": 1, "chapters": chapters[:half]},
                 {"term": 2, "chapters": chapters[half:]}]
        terms_out = []
        for term in terms:
            ch_entries = []
            for ch in term["chapters"]:
                concepts = []
                for con in ch["concepts"]:
                    node = chain_by_concept.get(con["concept_id"], {})
                    concepts.append({
                        "concept_id": con["concept_id"],
                        "title": con["title"],
                        "prerequisites": con["prerequisites"],
                        "next_concepts": con["next_concepts"],
                        "difficulty": con["difficulty"],
                        "estimated_minutes": node.get("estimated_minutes"),
                        "simulation_ids": [m["simulation_id"]
                                           for m in ch.get("simulation_mappings", [])
                                           if m["concept_id"] == con["concept_id"]],
                        "question_ids": con.get("question_ids", []),
                        "verified": con["verified"],
                    })
                ch_entries.append({
                    "chapter_id": ch["chapter_id"],
                    "chapter_number": ch["chapter_number"],
                    "title": ch["title"],
                    "difficulty": ch["difficulty"],
                    "lesson_ids": ch.get("lesson_ids", []),
                    "concepts": concepts,
                })
            terms_out.append({"term": term["term"], "chapters": ch_entries})
        subjects_out.append({
            "subject_slug": subject["slug"],
            "subject_id": subject["subject_id"],
            "name": subject["name"],
            "terms": terms_out,
        })
    return {
        "class_level": CLASS_LEVEL,
        "academic_year": YEAR,
        "generated_from": "concept_graph.json",
        "algorithm": "concept-chain topological order (documented deterministic rule)",
        "generated_at": now_iso(),
        "subjects": subjects_out,
    }


def main() -> int:
    manifest = load_json(CUR / "cbse_class_x_2026_27.json")
    legacy_files = {
        "mathematics": CUR / "mathematics.json",
        "science": CUR / "science.json",
        "social-science": CUR / "social-science.json",
    }

    subject_dicts: list[dict] = []
    chains: list[list[dict]] = []
    questions: list[Question] = []
    label_edges: list[dict] = []
    for msub in manifest["subjects"]:
        sdict, chain, qs, lpe = convert_subject(msub, legacy_files[msub["slug"]])
        subject_dicts.append(sdict)
        chains.append(chain)
        questions.extend(qs)
        label_edges.extend(lpe)

    known_chapters = {
        slugify(ch["title"]): ch["chapter_id"]
        for sd in subject_dicts for ch in sd["chapters"]
    }
    syllabus = load_json(CUR / "ncert_class10_syllabus.json")
    questions.extend(convert_syllabus_questions(syllabus, known_chapters))

    # ---- write the versioned package ----
    (OUT / "subjects").mkdir(parents=True, exist_ok=True)
    for sd in subject_dicts:
        (OUT / "subjects" / f"{sd['slug']}.json").write_text(
            json.dumps(sd, indent=2, ensure_ascii=False), encoding="utf-8")

    graph = {
        "class_level": CLASS_LEVEL,
        "academic_year": YEAR,
        "nodes": [
            {"concept_id": n["concept_id"], "title": n["title"],
             "chapter_id": n["chapter_id"], "lesson_id": n["lesson_id"],
             "difficulty": n["difficulty"],
             "estimated_minutes": n.get("estimated_minutes"),
             "prerequisites": n["prerequisites"],
             "next_concepts": n["next_concepts"]}
            for chain in chains for n in chain
        ],
        "label_prerequisites": label_edges,
    }
    (OUT / "concept_graph.json").write_text(
        json.dumps(graph, indent=2, ensure_ascii=False), encoding="utf-8")

    (OUT / "simulation_registry.json").write_text(
        json.dumps({
            "catalog": SIMULATION_CATALOG,
            "mappings": [
                dict(m) for sd in subject_dicts for ch in sd["chapters"]
                for m in ch.get("simulation_mappings", [])
            ],
        }, indent=2, ensure_ascii=False), encoding="utf-8")

    (OUT / "question_bank.json").write_text(
        json.dumps({"class_level": CLASS_LEVEL,
                    "questions": [q.to_dict() for q in questions]},
                   indent=2, ensure_ascii=False), encoding="utf-8")

    (OUT / "roadmap.json").write_text(
        json.dumps(build_roadmap(subject_dicts, chains), indent=2, ensure_ascii=False),
        encoding="utf-8")

    package = CurriculumPackage(
        package_id=PACKAGE_ID,
        class_level=CLASS_LEVEL,
        academic_year=YEAR,
        board=Board.CBSE,
        version="1.0.0",
        source_version=manifest.get("source_version", ""),
        generated_at=now_iso(),
        generated_by="hybrid",
        subjects=[Subject.from_dict(sd) for sd in subject_dicts],
        source=SourceMetadata(
            source_id=f"cbse-class-x-{YEAR}",
            source_type="cbse_curriculum_doc",
            title="CBSE Class X curriculum 2026-27 + NCERT textbook catalog",
            publisher="CBSE/NCERT",
            academic_year=YEAR,
            notes="Built from in-repo seed packages by build_class10_package.py.",
        ),
        verified=True,
    )
    (OUT / "manifest.json").write_text(
        json.dumps(package.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    verified_q = sum(1 for q in questions if q.verified)
    meta = {
        "package_id": PACKAGE_ID,
        "schema_version": CANONICAL_SCHEMA_VERSION,
        "generated_at": now_iso(),
        "counts": {
            "subjects": len(subject_dicts),
            "chapters": sum(len(sd["chapters"]) for sd in subject_dicts),
            "concepts": sum(len(n) for n in chains),
            "questions_total": len(questions),
            "questions_verified": verified_q,
            "questions_unverified": len(questions) - verified_q,
        },
        "verification_policy": {
            "legacy_human_authored": "verified=true (repo seed packages)",
            "ncert_syllabus_extraction": "verified=false (pending human review)",
        },
    }
    (OUT / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print("Class 10 package written to", OUT)
    print(json.dumps(meta["counts"], indent=2))
    return 0






def slugify(text: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return text


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json(path: Path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)




def _chapter_objectives_activities(legacy_chapter: dict, chapter_id: str):
    """Derive learning objectives + concept-check activities from legacy lessons."""
    objectives: list[LearningObjective] = []
    activities: list[Activity] = []
    objectives_by_concept: dict[str, list[str]] = {}
    concept_by_lesson: dict[str, str] = {}
    for topic in legacy_chapter.get("topics", []):
        for lesson in topic.get("lessons", []):
            lesson_concepts = lesson.get("concepts", [])
            cid = lesson_concepts[0]["concept_id"] if lesson_concepts else None
            if cid and lesson["lesson_id"] not in concept_by_lesson:
                concept_by_lesson[lesson["lesson_id"]] = cid
            for obj_text in lesson.get("learning_objectives", []):
                obj = LearningObjective(
                    objective_id=f"{chapter_id}-lo-{len(objectives) + 1:02d}",
                    concept_id=cid,
                    statement=obj_text,
                    bloom_level=CompetencyCategory.UNDERSTAND,
                    verified=True,
                )
                objectives.append(obj)
                if cid:
                    objectives_by_concept.setdefault(cid, []).append(obj.objective_id)
            for block in lesson.get("content_blocks", []):
                if block.get("type") == "check":
                    activities.append(Activity(
                        activity_id=f"{chapter_id}-act-{len(activities) + 1:02d}",
                        concept_id=cid,
                        title=block.get("title") or "Concept check",
                        activity_type="practice",
                        description=block.get("text", ""),
                        verified=True,
                    ))
    return objectives, activities, objectives_by_concept, concept_by_lesson


def competency_from_skill(skill: str | None) -> CompetencyCategory:
    if not skill:
        return CompetencyCategory.UNDERSTAND
    return SKILL_TO_COMPETENCY.get(str(skill).strip().lower(), CompetencyCategory.UNDERSTAND)


def chapter_difficulty(chapter: dict) -> Difficulty:
    """Chapter difficulty = hardest lesson difficulty in the chapter."""
    order = [Difficulty.FOUNDATION, Difficulty.EASY, Difficulty.MEDIUM, Difficulty.HARD,
             Difficulty.BOARD_LEVEL, Difficulty.CHALLENGE]
    hardest = Difficulty.MEDIUM
    for topic in chapter.get("topics", []):
        for lesson in topic.get("lessons", []):
            try:
                d = Difficulty(str(lesson.get("difficulty", "MEDIUM")).upper())
            except ValueError:
                continue
            if order.index(d) > order.index(hardest):
                hardest = d
    return hardest


def _chapter_questions(legacy_chapter: dict, chapter_id: str, source_dict: dict,
                       concept_by_lesson: dict[str, str]):
    """Extract questions + competency set from legacy topics."""
    questions: list[Question] = []
    competencies: set[CompetencyCategory] = set()
    seen_ids: set[str] = set()
    for topic in legacy_chapter.get("topics", []):
        # NOTE: legacy topics repeat their chapter-level questions per-lesson
        # entry (same question_id); dedupe so the bank stays ID-unique.
        for lesson in topic.get("lessons", []):
            cid = concept_by_lesson.get(lesson["lesson_id"])
            for q in topic.get("questions", []):
                if q.get("question_id") in seen_ids:
                    continue
                seen_ids.add(q.get("question_id"))
                qtype_raw = str(q.get("question_type", "MCQ")).upper()
                try:
                    qtype = QuestionType(qtype_raw)
                except ValueError:
                    qtype = QuestionType.SHORT_ANSWER
                comp = competency_from_skill(q.get("skill"))
                competencies.add(comp)
                questions.append(Question(
                    question_id=q["question_id"],
                    concept_id=cid,
                    chapter_id=chapter_id,
                    question_type=qtype,
                    prompt=q.get("prompt", ""),
                    answer=q.get("answer", ""),
                    options=q.get("options", []),
                    explanation=q.get("explanation", ""),
                    difficulty=Difficulty(str(q.get("difficulty", "EASY")).upper()),
                    competency=comp,
                    marks=int(q.get("marks", 1)),
                    source=SourceMetadata(**source_dict),
                    verified=True,
                ))
    return questions, competencies


if __name__ == "__main__":
    sys.exit(main())
