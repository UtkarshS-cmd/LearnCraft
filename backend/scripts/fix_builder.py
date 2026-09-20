"""One-shot fix for build_class10_package.py: unify split convert functions."""
from pathlib import Path

BUILD = Path("scripts/build_class10_package.py")
text = BUILD.read_text(encoding="utf-8")

start = text.index("def convert_subject_part1")
end = text.index("def convert_subject(manifest_subject")
new_head = '''def convert_subject(manifest_subject: dict, legacy_path: Path):
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

'''
text = text[:start] + new_head + text[end + len("def convert_subject(manifest_subject: dict, legacy_path: Path):\n"):]
print("head unified")

# convert_subject previously ended with a Subject(...) construction and no return.
anchor = '''        source=SourceMetadata(**source),
        verified=True,
    )


def convert_syllabus_questions'''
replacement = '''        source=SourceMetadata(**source),
        verified=True,
    )

    return subject.to_dict(), chain, all_questions, label_prereq_edges


def convert_syllabus_questions'''
assert anchor in text, "return anchor not found"
text = text.replace(anchor, replacement)
print("return added")

# subject_dicts hold plain dicts, so registry mappings are already dicts.
old_map = '''            "mappings": [
                m.to_dict() for sd in subject_dicts for ch in sd["chapters"]
                for m in ch.get("simulation_mappings", [])
            ],'''
new_map = '''            "mappings": [
                dict(m) for sd in subject_dicts for ch in sd["chapters"]
                for m in ch.get("simulation_mappings", [])
            ],'''
assert old_map in text, "registry anchor not found"
text = text.replace(old_map, new_map)
print("registry fixed")

BUILD.write_text(text, encoding="utf-8")
print("builder fixed")
