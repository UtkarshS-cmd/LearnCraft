"""Probe the generated class-10 package and how the catalog would consume it."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "_class10_probe.txt"
sys.path.insert(0, str(ROOT))

lines: list[str] = []


def add(text: str = "") -> None:
    lines.append(text)


CLASS_DIR = ROOT / "data" / "curriculum" / "class10"

add("=== meta.json ===")
add((CLASS_DIR / "meta.json").read_text(encoding="utf-8"))

add("=== manifest.json (head) ===")
manifest = json.loads((CLASS_DIR / "manifest.json").read_text(encoding="utf-8"))
add(json.dumps({k: v for k, v in manifest.items() if k != "subjects"}, indent=2)[:2000])
add("subject keys inside manifest:")
for s in manifest["subjects"]:
    add(f"  {s['subject_id']} slug={s['slug']} name={s['name']} chapters={len(s['chapters'])}")
    for ch in s["chapters"][:3]:
        add(f"     ch{ch['chapter_number']} {ch['chapter_id']} concepts={len(ch['concepts'])} "
            f"subs={len(ch['sub_concepts'])} objectives={len(ch['learning_objectives'])} "
            f"acts={len(ch['activities'])} sims={len(ch['simulation_mappings'])} "
            f"lessons={len(ch.get('lesson_ids', []))}")
    add(f"     TOTAL chapters: {len(s['chapters'])}")

add("=== concept_graph.json ===")
graph = json.loads((CLASS_DIR / "concept_graph.json").read_text(encoding="utf-8"))
add("keys: " + str(list(graph.keys())))
add("nodes: " + str(len(graph.get("nodes", []))))
add("sample node: " + json.dumps(graph["nodes"][0], indent=2))
add("label_prerequisites sample: " + json.dumps(
    (graph.get("label_prerequisites") or [])[:2], indent=2))

add("=== simulation_registry.json ===")
reg = json.loads((CLASS_DIR / "simulation_registry.json").read_text(encoding="utf-8"))
add("keys: " + str(list(reg.keys())))
add(json.dumps(reg, indent=2)[:4000])

add("=== roadmap.json ===")
road = json.loads((CLASS_DIR / "roadmap.json").read_text(encoding="utf-8"))
add("keys: " + str(list(road.keys())))
add("subjects: " + str([(s["subject_slug"], [len(t["chapters"]) for t in s["terms"]])
                        for s in road["subjects"]]))

add("=== question_bank.json ===")
qb = json.loads((CLASS_DIR / "question_bank.json").read_text(encoding="utf-8"))
add("type: " + type(qb).__name__)
if isinstance(qb, dict):
    add("keys: " + str(list(qb.keys())))
    for k, v in qb.items():
        if isinstance(v, list):
            add(f"  {k}: list len={len(v)}")
            add("   sample: " + json.dumps(v[0], indent=2)[:1200] if v else "   (empty)")
        elif isinstance(v, dict):
            add(f"  {k}: dict keys={list(v.keys())[:20]}")
        else:
            add(f"  {k}: {v}")

OUT.write_text("\n".join(lines), encoding="utf-8")
print("wrote", OUT)
