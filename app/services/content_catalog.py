from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.database.connection import get_connection

ROOT = Path(__file__).resolve().parents[2]
CURRICULUM_DIR = ROOT / "data" / "curriculum"
ACADEMIC_YEAR = "2026-27"
BOARD = "CBSE"
CLASS_LEVEL = "Class X"

VALID_DIFFICULTIES = {"FOUNDATION", "EASY", "MEDIUM", "HARD", "BOARD_LEVEL", "CHALLENGE"}
VALID_QUESTION_TYPES = {"MCQ", "MULTIPLE_CORRECT", "ASSERTION_REASON", "FILL_BLANK", "TRUE_FALSE", "SHORT_ANSWER", "LONG_ANSWER", "NUMERICAL", "CASE_BASED", "DIAGRAM_BASED"}

# The lesson player progresses through an ordered set of stages. Curriculum
# content blocks do not carry a stage, so we assign one based on the block type.
STAGE_CYCLE = ["CONCEPT", "EXPLAIN", "INTERACT", "EXPERIMENT", "PRACTICE", "REFLECT", "APPLY"]

STAGE_FOR_TYPE = {
    "heading": "CONCEPT",
    "preview": "CONCEPT",
    "definition": "CONCEPT",
    "text": "CONCEPT",
    "example": "EXPLAIN",
    "formula": "EXPLAIN",
    "visual": "EXPLAIN",
    "video": "EXPLAIN",
    "procedure": "INTERACT",
    "steps": "INTERACT",
    "interactive": "INTERACT",
    "simulation": "EXPERIMENT",
    "experiment": "EXPERIMENT",
    "lab": "EXPERIMENT",
    "check": "PRACTICE",
    "question": "PRACTICE",
    "practice": "PRACTICE",
    "summary": "REFLECT",
    "key_points": "REFLECT",
    "reflect": "REFLECT",
    "apply": "APPLY",
    "task": "APPLY",
}

DEFAULT_BLOCK_TITLES = {
    "text": "Read this",
    "example": "Worked example",
    "summary": "Key takeaway",
    "heading": "Focus point",
    "formula": "Formula to remember",
    "definition": "Definition",
    "procedure": "Step-by-step",
    "steps": "Steps",
    "question": "Question",
}


def normalize_lesson_blocks(raw_blocks) -> list[dict]:
    """Convert curriculum content blocks into the lesson-player schema.

    The curriculum packages store content as ``{"type": ..., "text": ...}``
    without any player metadata. This maps them onto the schema the lesson
    page expects (``type``, ``stage``, ``title``, ``body``) so every block
    renders and the progress rail/buttons keep working.
    """
    normalized: list[dict] = []
    used_stages = set()
    for raw in raw_blocks or []:
        block = dict(raw)
        btype = str(block.get("type") or "text").lower()
        text = block.get("text") or block.get("body") or block.get("content") or ""

        stage = str(block.get("stage") or STAGE_FOR_TYPE.get(btype) or "").upper()
        if not stage or stage not in STAGE_CYCLE:
            stage = next((s for s in STAGE_CYCLE if s not in used_stages), "CONCEPT")
        used_stages.add(stage)
        block["stage"] = stage

        # Rewrite curriculum-only block types onto player-supported types.
        if btype in ("example", "summary", "heading", "formula", "definition", "procedure", "steps", "question"):
            block["type"] = "text"
            btype = "text"

        if block.get("body") is None:
            block["body"] = text
        if not block.get("title"):
            block["title"] = raw.get("title") or DEFAULT_BLOCK_TITLES.get(btype) or btype.replace("_", " ").title()

        normalized.append(block)
    return normalized


def _read_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_packages() -> list[dict]:
    curriculum = _read_json(CURRICULUM_DIR / "cbse_class_x_2026_27.json")
    packages = []
    for subject in curriculum["subjects"]:
        package = dict(subject)
        package["board"] = curriculum["board"]
        package["class_level"] = curriculum["class_level"]
        package["academic_year"] = curriculum["academic_year"]
        package["source_version"] = curriculum["source_version"]
        package["chapters"] = _read_json(CURRICULUM_DIR / f"{subject['slug']}.json")["chapters"]
        packages.append(package)
    return packages


def validate_packages(packages: list[dict]) -> list[str]:
    errors = []
    seen = set()

    def required(value, label):
        if not value:
            errors.append(f"missing {label}")

    for package in packages:
        for key in ("subject_id", "slug", "name", "book_id", "source_reference"):
            required(package.get(key), f"subject.{key}")
        for chapter in package.get("chapters", []):
            chapter_id = chapter.get("chapter_id")
            if not chapter_id:
                errors.append("missing chapter ID")
            elif chapter_id in seen:
                errors.append(f"duplicate chapter ID: {chapter_id}")
            else:
                seen.add(chapter_id)
            for key in ("chapter_id", "title", "slug", "source_reference"):
                required(chapter.get(key), f"chapter.{key}")
            for topic in chapter.get("topics", []):
                required(topic.get("topic_id"), "topic.topic_id")
                for lesson in topic.get("lessons", []):
                    for key in ("lesson_id", "title", "summary", "content_blocks", "source_reference"):
                        required(lesson.get(key), f"lesson.{key}")
                    if not lesson.get("content_blocks"):
                        errors.append(f"empty lesson: {lesson.get('lesson_id')}")
                for question in topic.get("questions", []):
                    question_id = question.get("question_id")
                    if question_id in seen:
                        errors.append(f"duplicate question ID: {question_id}")
                    seen.add(question_id)
                    required(question.get("answer"), f"question.{question_id}.answer")
                    required(question.get("explanation"), f"question.{question_id}.explanation")
                    required(question.get("source_reference") or chapter.get("source_reference"), f"question.{question_id}.source")
                    if question.get("difficulty") not in VALID_DIFFICULTIES:
                        errors.append(f"invalid difficulty: {question_id}")
                    if question.get("question_type") not in VALID_QUESTION_TYPES:
                        errors.append(f"invalid question type: {question_id}")
                    if not isinstance(question.get("marks"), int) or question["marks"] <= 0:
                        errors.append(f"invalid marks: {question_id}")
    return errors


def import_packages(packages: list[dict]) -> dict:
    errors = validate_packages(packages)
    if errors:
        raise ValueError("Content validation failed:\n" + "\n".join(errors))
    connection = get_connection()
    counts = {"subjects": 0, "chapters": 0, "topics": 0, "lessons": 0, "questions": 0}
    try:
        for package in packages:
            subject_bytes = json.dumps(package, sort_keys=True).encode("utf-8")
            connection.execute(
                """INSERT INTO content_manifests
                (content_id, version, size_bytes, checksum, downloaded)
                VALUES (?, ?, ?, ?, 0) ON CONFLICT(content_id) DO UPDATE SET
                version=excluded.version, size_bytes=excluded.size_bytes, checksum=excluded.checksum,
                updated_at=CURRENT_TIMESTAMP""",
                (package["subject_id"], ACADEMIC_YEAR, len(subject_bytes), hashlib.sha256(subject_bytes).hexdigest()),
            )
            connection.execute(
                """INSERT INTO academic_subjects
                (subject_id, board, class_level, academic_year, slug, name, description, source_version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(subject_id) DO UPDATE SET name=excluded.name, description=excluded.description,
                source_version=excluded.source_version""",
                (package["subject_id"], BOARD, CLASS_LEVEL, ACADEMIC_YEAR, package["slug"], package["name"],
                 package["description"], package["source_version"]),
            )
            connection.execute(
                """INSERT INTO academic_books (book_id, subject_id, title, publisher, source_reference)
                VALUES (?, ?, ?, ?, ?) ON CONFLICT(book_id) DO UPDATE SET title=excluded.title,
                publisher=excluded.publisher, source_reference=excluded.source_reference""",
                (package["book_id"], package["subject_id"], package["book_title"], package["publisher"], package["source_reference"]),
            )
            counts["subjects"] += 1
            for chapter in package["chapters"]:
                chapter_bytes = json.dumps(chapter, sort_keys=True).encode("utf-8")
                connection.execute(
                    """INSERT INTO content_manifests
                    (content_id, version, size_bytes, checksum, downloaded)
                    VALUES (?, ?, ?, ?, 0) ON CONFLICT(content_id) DO UPDATE SET
                    version=excluded.version, size_bytes=excluded.size_bytes, checksum=excluded.checksum,
                    updated_at=CURRENT_TIMESTAMP""",
                    (chapter["chapter_id"], ACADEMIC_YEAR, len(chapter_bytes), hashlib.sha256(chapter_bytes).hexdigest()),
                )
                connection.execute(
                    """INSERT INTO academic_chapters
                    (chapter_id, book_id, chapter_number, title, slug, summary, source_reference)
                    VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(chapter_id) DO UPDATE SET title=excluded.title,
                    summary=excluded.summary, source_reference=excluded.source_reference""",
                    (chapter["chapter_id"], package["book_id"], chapter["chapter_number"], chapter["title"],
                     chapter["slug"], chapter["summary"], chapter["source_reference"]),
                )
                counts["chapters"] += 1
                for topic in chapter["topics"]:
                    connection.execute(
                        """INSERT INTO academic_topics (topic_id, chapter_id, title, slug)
                        VALUES (?, ?, ?, ?) ON CONFLICT(topic_id) DO UPDATE SET title=excluded.title""",
                        (topic["topic_id"], chapter["chapter_id"], topic["title"], topic["slug"]),
                    )
                    counts["topics"] += 1
                    for lesson in topic["lessons"]:
                        connection.execute(
                            """INSERT INTO academic_lessons
                            (lesson_id, topic_id, title, slug, summary, learning_objectives_json,
                            prerequisites_json, estimated_minutes, difficulty, content_blocks_json, source_reference)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(lesson_id) DO UPDATE SET title=excluded.title, summary=excluded.summary,
                            learning_objectives_json=excluded.learning_objectives_json, content_blocks_json=excluded.content_blocks_json""",
                            (lesson["lesson_id"], topic["topic_id"], lesson["title"], lesson["slug"], lesson["summary"],
                             json.dumps(lesson["learning_objectives"]), json.dumps(lesson["prerequisites"]),
                             lesson["estimated_minutes"], lesson["difficulty"], json.dumps(lesson["content_blocks"]),
                             lesson["source_reference"]),
                        )
                        counts["lessons"] += 1
                        for concept in lesson.get("concepts", []):
                            connection.execute(
                                """INSERT INTO academic_concepts (concept_id, lesson_id, title, explanation)
                                VALUES (?, ?, ?, ?) ON CONFLICT(concept_id) DO UPDATE SET title=excluded.title,
                                explanation=excluded.explanation""",
                                (concept["concept_id"], lesson["lesson_id"], concept["title"], concept["explanation"]),
                            )
                    for question in topic.get("questions", []):
                        connection.execute(
                            """INSERT INTO academic_questions
                            (question_id, subject_id, chapter_id, topic_id, difficulty, question_type, marks,
                            source_reference, skill, prompt, answer, explanation)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(question_id) DO UPDATE SET prompt=excluded.prompt, answer=excluded.answer,
                            explanation=excluded.explanation""",
                            (question["question_id"], package["subject_id"], chapter["chapter_id"], topic["topic_id"],
                             question["difficulty"], question["question_type"], question["marks"],
                             question["source_reference"] if question.get("source_reference") else chapter["source_reference"],
                             question["skill"], question["prompt"], question["answer"], question["explanation"]),
                        )
                        connection.execute("DELETE FROM academic_question_options WHERE question_id = ?", (question["question_id"],))
                        for option in question.get("options", []):
                            connection.execute(
                                """INSERT INTO academic_question_options
                                (question_id, option_id, option_text, is_correct) VALUES (?, ?, ?, ?)""",
                                (question["question_id"], option["option_id"], option["text"], int(option["is_correct"])),
                            )
                        counts["questions"] += 1
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return counts


def list_subjects() -> list[dict]:
    connection = get_connection()
    rows = connection.execute("SELECT * FROM academic_subjects ORDER BY name").fetchall()
    connection.close()
    return [dict(row) for row in rows]


def subject_detail(slug: str) -> dict | None:
    connection = get_connection()
    subject = connection.execute("SELECT * FROM academic_subjects WHERE slug = ?", (slug,)).fetchone()
    if not subject:
        connection.close()
        return None
    chapters = connection.execute(
        """SELECT c.*, b.subject_id FROM academic_chapters c
        JOIN academic_books b ON b.book_id = c.book_id WHERE b.subject_id = ? ORDER BY c.chapter_number""",
        (subject["subject_id"],),
    ).fetchall()
    connection.close()
    return {"subject": dict(subject), "chapters": [dict(row) for row in chapters]}


def get_lesson(lesson_id: str) -> dict | None:
    connection = get_connection()
    row = connection.execute(
        """SELECT l.*, t.title AS topic_title, c.chapter_id, c.title AS chapter_title,
        s.slug AS subject_slug, s.name AS subject_name
        FROM academic_lessons l JOIN academic_topics t ON t.topic_id = l.topic_id
        JOIN academic_chapters c ON c.chapter_id = t.chapter_id
        JOIN academic_books b ON b.book_id = c.book_id
        JOIN academic_subjects s ON s.subject_id = b.subject_id WHERE l.lesson_id = ?""",
        (lesson_id,),
    ).fetchone()
    connection.close()
    if not row:
        return None
    payload = dict(row)
    payload["blocks"] = normalize_lesson_blocks(json.loads(payload.pop("content_blocks_json")))
    objectives = json.loads(payload.pop("learning_objectives_json"))
    payload["objective"] = objectives[0] if objectives else "Continue learning"
    payload["est"] = f"{payload.pop('estimated_minutes')} min"
    payload["chapter_label"] = f"Chapter · {payload.pop('chapter_title')}"
    payload["next_label"] = "Next lesson"
    payload["id"] = payload.get("lesson_id")
    return payload


def list_subject_lessons(subject_slug: str) -> list[dict]:
    """Return every lesson of a subject, ordered by chapter number."""
    connection = get_connection()
    rows = connection.execute(
        """SELECT l.lesson_id, l.title, l.slug, l.summary, l.estimated_minutes, l.difficulty,
        c.chapter_id, c.chapter_number, c.title AS chapter_title
        FROM academic_lessons l JOIN academic_topics t ON t.topic_id = l.topic_id
        JOIN academic_chapters c ON c.chapter_id = t.chapter_id
        JOIN academic_books b ON b.book_id = c.book_id
        JOIN academic_subjects s ON s.subject_id = b.subject_id
        WHERE s.slug = ? ORDER BY c.chapter_number, t.topic_id, l.lesson_id""",
        (subject_slug,),
    ).fetchall()
    connection.close()
    return [dict(row) for row in rows]


def list_subject_questions(subject_slug: str) -> list[dict]:
    """Return every question of a subject, ordered by chapter number."""
    connection = get_connection()
    rows = connection.execute(
        """SELECT q.question_id, q.prompt, q.question_type, q.difficulty, q.marks,
        c.chapter_id, c.chapter_number, c.title AS chapter_title
        FROM academic_questions q JOIN academic_subjects s ON s.subject_id = q.subject_id
        JOIN academic_chapters c ON c.chapter_id = q.chapter_id
        WHERE s.slug = ? ORDER BY c.chapter_number, q.question_id""",
        (subject_slug,),
    ).fetchall()
    connection.close()
    return [dict(row) for row in rows]


def first_lesson_for_chapter(chapter_id: str) -> dict | None:
    connection = get_connection()
    row = connection.execute(
        """SELECT l.lesson_id, l.title FROM academic_lessons l
        JOIN academic_topics t ON t.topic_id = l.topic_id
        WHERE t.chapter_id = ? ORDER BY l.lesson_id LIMIT 1""",
        (chapter_id,),
    ).fetchone()
    connection.close()
    return dict(row) if row else None


def list_questions(subject_slug: str | None = None, chapter_id: str | None = None) -> list[dict]:
    connection = get_connection()
    clauses, params = [], []
    if subject_slug:
        clauses.append("s.slug = ?")
        params.append(subject_slug)
    if chapter_id:
        clauses.append("q.chapter_id = ?")
        params.append(chapter_id)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = connection.execute(
        f"""SELECT q.*, s.slug AS subject_slug FROM academic_questions q
        JOIN academic_subjects s ON s.subject_id = q.subject_id {where} ORDER BY q.question_id""", params
    ).fetchall()
    questions = []
    for row in rows:
        item = dict(row)
        item["options"] = [dict(option) for option in connection.execute(
            "SELECT option_id, option_text, is_correct FROM academic_question_options WHERE question_id = ?",
            (item["question_id"],),
        ).fetchall()]
        questions.append(item)
    connection.close()
    return questions


def build_manifest(content_id: str, version: str, payload: bytes) -> dict:
    return {"content_id": content_id, "version": version, "size": len(payload),
            "checksum": hashlib.sha256(payload).hexdigest(), "downloaded": False}


def list_manifests() -> list[dict]:
    connection = get_connection()
    rows = connection.execute("SELECT * FROM content_manifests ORDER BY content_id").fetchall()
    connection.close()
    return [dict(row) for row in rows]


def mark_manifest_downloaded(content_id: str, downloaded: bool = True) -> bool:
    connection = get_connection()
    cursor = connection.execute(
        "UPDATE content_manifests SET downloaded = ?, updated_at = CURRENT_TIMESTAMP WHERE content_id = ?",
        (int(downloaded), content_id),
    )
    connection.commit()
    connection.close()
    return cursor.rowcount > 0
