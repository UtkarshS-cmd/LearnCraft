"""Temporary state report (dev only)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CUR = ROOT / "data" / "curriculum"
out = []


def log(*parts):
    out.append(" ".join(str(p) for p in parts))


log("== curriculum dir ==")
for p in sorted(CUR.rglob("*")):
    if p.is_file():
        log(f"{p.relative_to(ROOT)} :: {p.stat().st_size}")

for name in ("class10/manifest.json", "class10/meta.json",
             "class10/concept_graph.json", "class10/roadmap.json",
             "class10/simulation_registry.json", "class10/question_bank.json"):
    p = CUR / name
    if not p.exists():
        log(f"-- {name} MISSING")
        continue
    data = json.loads(p.read_text(encoding="utf-8"))
    log(f"-- {name}")
    if isinstance(data, dict):
        log("   keys:", list(data.keys()))
        if name.endswith("manifest.json"):
            log("   subjects:", [s.get("slug") for s in data.get("subjects", [])])
            log("   chapters:", sum(len(s.get("chapters", [])) for s in data.get("subjects", [])))
            log("   concepts:", sum(len(c.get("concepts", []))
                                   for s in data.get("subjects", [])
                                   for c in s.get("chapters", [])))
        if name.endswith("question_bank.json"):
            log("   questions:", len(data.get("questions", [])))
        if name.endswith("concept_graph.json"):
            log("   nodes:", len(data.get("nodes", [])))
        if name.endswith("roadmap.json"):
            log("   subjects:", [s.get("subject_slug") for s in data.get("subjects", [])])
        if name.endswith("simulation_registry.json"):
            log("   catalog:", len(data.get("catalog", [])), "mappings:", len(data.get("mappings", [])))
    elif isinstance(data, list):
        log("   list len:", len(data))

log("== scripts ==")
for p in sorted((ROOT / "scripts").glob("*.py")):
    log(f"{p.name} :: {p.stat().st_size}")

log("== tests ==")
for p in sorted((ROOT / "tests").rglob("test_*.py")):
    log(str(p.relative_to(ROOT)))

log("== root scratch files ==")
for p in sorted(ROOT.glob("*.py")):
    log(f"{p.name} :: {p.stat().st_size}")

log("== docs ==")
for p in sorted(ROOT.parent.glob("*.md")):
    log(f"{p.name} :: {p.stat().st_size}")

(ROOT / "_state_report.txt").write_text("\n".join(out), encoding="utf-8")
print("\n".join(out))
