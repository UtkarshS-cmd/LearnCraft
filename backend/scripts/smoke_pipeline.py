#!/usr/bin/env python3
"""Smoke-test the curriculum pipeline with the class-10 package."""
import os
import sys
import json
from pathlib import Path

os.environ.setdefault("LEARNCRAFT_SECRET_KEY", "test")
os.environ.setdefault("LEARNCRAFT_DB_PATH", ":memory:")

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.services.curriculum_pipeline import (
    load_all_packages,
    available_class_dirs,
    load_concept_graph,
    load_simulation_registry,
    build_roadmap_for_class,
    package_summary,
    question_bank_summary,
    validate_class_package,
    verify_question,
    resolve_class_dir,
    load_question_bank_cached,
    load_class_package,
)

print("=" * 60)
print("PIPELINE SMOKE TEST")
print("=" * 60)

# 1. Available class dirs
print("\n--- Available class dirs ---")
for d in available_class_dirs():
    print(f"  {d.name}")

# 2. Load all packages
print("\n--- Loaded packages ---")
packages = load_all_packages()
for name, pkg in packages.items():
    print(f"  {name}: {pkg.package_id} ({len(pkg.subjects)} subjects)")

# 3. Package summary
print("\n--- Package summary (class10) ---")
class10 = resolve_class_dir("class10")
if class10:
    summary = package_summary(class10)
    print(json.dumps(summary, indent=2)[:1500])

# 4. Question bank summary
print("\n--- Question bank summary ---")
qs = question_bank_summary(class10)
print(json.dumps(qs, indent=2))

# 5. Concept graph
print("\n--- Concept graph ---")
g = load_concept_graph(class10)
print(f"  nodes: {len(g['nodes'])}, edges: {len(g.get('edges', []))}")
for n in g["nodes"][:3]:
    print(f"  {n['concept_id']}: prereqs={n.get('prerequisites', [])} next={n.get('next_concepts', [])}")

# 6. Roadmap
print("\n--- Roadmap ---")
rm = build_roadmap_for_class(class10)
print(f"  subjects: {len(rm.get('subjects', []))}")
for s in rm.get("subjects", []):
    print(f"  {s['subject_slug']}: {len(s.get('terms', []))} terms")

# 7. Simulation registry
print("\n--- Simulation registry ---")
sr = load_simulation_registry(class10)
print(f"  catalog: {len(sr['catalog'])}, mappings: {len(sr['mappings'])}")
for m in sr["mappings"]:
    print(f"  {m['concept_id']} -> {m['simulation_id']}")

# 8. Validate package
print("\n--- Validation ---")
errors = validate_package(class10)
if errors:
    print(f"  ERRORS ({len(errors)}):")
    for e in errors[:10]:
        print(f"    - {e}")
else:
    print("  No validation errors")

# 9. Validate questions
print("\n--- Question validation samples ---")
bank = load_question_bank_cached(class10)
print(f"  Total questions loaded: {len(bank)}")
for q in bank[:5]:
    err = validate_question(q)
    status = "OK" if not err else f"FAIL: {err}"
    print(f"  {q.question_id} [{q.question_type.value}]: {status}")

print("\n" + "=" * 60)
print("SMOKE TEST COMPLETE")
print("=" * 60)
