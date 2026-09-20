"""Repair interleaved fragments in pipeline + builder scripts (one-shot)."""
from pathlib import Path

PIPE = Path("app/services/curriculum_pipeline.py")
BUILD = Path("scripts/build_class10_package.py")

text = PIPE.read_text(encoding="utf-8")
bad = '                              f"simulation {mapping.simulation_id} not in registry catalog")\n    catalog = {s["simulation_id"]: s for s in registry.get("catalog", [])}\n    return [\n        {**catalog.get(m["simulation_id"], {}),\n\n    for question in (question_bank or []):\n'
good = '                              f"simulation {mapping.simulation_id} not in registry catalog")\n\n    for question in (question_bank or []):\n'
assert bad in text, "pipeline bad block not found"
text = text.replace(bad, good)

bad2 = '''    return question
         "mapping_type": m.get("mapping_type", "exploration")}
        for m in registry.get("mappings", [])
        if m.get("concept_id") == concept_id
    ]
            if cid in seen or cid not in self.nodes:
                continue
            seen.add(cid)
            stack.extend(self.prerequisites.get(cid, []))
        return seen


def build_concept_graph(class_dir: Path) -> ConceptGraph:
    return ConceptGraph.from_graph_data(load_concept_graph(class_dir))
def load_roadmap(class_dir: Path) -> dict:
    path = class_dir / "roadmap.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


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
    path = class_dir / "roadmap.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)'''
good2 = '''    return question


def build_concept_graph(class_dir: Path) -> ConceptGraph:
    return ConceptGraph.from_graph_data(load_concept_graph(class_dir))


def load_roadmap(class_dir: Path) -> dict:
    path = class_dir / "roadmap.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)'''
assert bad2 in text, "pipeline tail block not found"
text = text.replace(bad2, good2)
PIPE.write_text(text, encoding="utf-8")
print("pipeline repaired")

btext = BUILD.read_text(encoding="utf-8")
guard = 'if __name__ == "__main__":\n    sys.exit(main())\n'
assert guard in btext, "builder guard not found"
head, tail = btext.split(guard, 1)
helpers = tail  # slugify ... _chapter_questions live after the guard
BUILD.write_text(head + helpers + "\n\n" + guard, encoding="utf-8")
print("builder reordered")
