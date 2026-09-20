"""Inspect class10 artefacts: counts + samples (offline)."""
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "data" / "curriculum" / "class10"

for name in ["meta.json", "concept_graph.json", "roadmap.json",
             "simulation_registry.json", "question_bank.json", "manifest.json"]:
    p = BASE / name
    print("=" * 60)
    print(name, "exists:", p.exists(),
          "bytes:", p.stat().st_size if p.exists() else 0)
    if p.exists():
        d = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(d, dict):
            print("  keys:", list(d.keys()))
            if "nodes" in d:
                print("  nodes:", len(d["nodes"]))
                if d["nodes"]:
                    print("  node0:", json.dumps(d["nodes"][0])[:500])
            if "subjects" in d:
                print("  subjects:", len(d["subjects"]))
            if "counts" in d:
                print("  counts:", d["counts"])
            if "questions" in d:
                print("  questions:", len(d["questions"]))
                if d["questions"]:
                    print("  q0:", json.dumps(d["questions"][0])[:500])
            if "mappings" in d:
                print("  mappings:", len(d["mappings"]),
                      "catalog:", len(d.get("catalog", [])))

for s in sorted((BASE / "subjects").glob("*.json")):
    d = json.loads(s.read_text(encoding="utf-8"))
    chs = d.get("chapters", [])
    print("=" * 60)
    print(s.name, "chapters:", len(chs))
    for c in chs[:8]:
        print("  ch", c.get("chapter_number"), c.get("title"),
              "| concepts:", len(c.get("concepts", [])),
              "| objectives:", len(c.get("learning_objectives", [])),
              "| sims:", len(c.get("simulation_mappings", [])))

