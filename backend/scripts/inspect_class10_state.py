#!/usr/bin/env python3
"""Inspect class-10 curriculum state."""
import json
import pathlib
from collections import Counter

BASE = pathlib.Path(__file__).resolve().parent.parent / "data" / "curriculum" / "class10"
print("=" * 60)
print("CLASS 10 CURRICULUM STATE")
print("=" * 60)

for fname in ["manifest.json", "meta.json"]:
    p = BASE / fname
    if p.exists():
        with open(p) as f:
            d = json.load(f)
        print(f"\n--- {fname} ---")
        print(json.dumps(d, indent=2)[:2000])
    else:
        print(f"\n--- {fname} --- MISSING")

# Concept graph
gpath = BASE / "concept_graph.json"
if gpath.exists():
    with open(gpath) as f:
        g = json.load(f)
    nodes = g.get("nodes", [])
    edges = g.get("edges", [])
    print(f"\n--- concept_graph.json ---")
    print(f"Nodes: {len(nodes)}, Edges: {len(edges)}")
    print("Sample nodes:")
    for n in nodes[:3]:
        print(f"  {n.get('id')}: {n.get('label','')[:80]}")
    print("Sample edges:")
    for e in edges[:3]:
        print(f"  {e.get('source')} -> {e.get('target')} [{e.get('relation','')}]")
else:
    print("\n--- concept_graph.json --- MISSING")

# Roadmap
rpath = BASE / "roadmap.json"
if rpath.exists():
    with open(rpath) as f:
        r = json.load(f)
    phases = r.get("phases", [])
    print(f"\n--- roadmap.json ---")
    print(f"Phases: {len(phases)}")
    total_steps = sum(len(p.get("steps", [])) for p in phases)
    print(f"Total steps: {total_steps}")
    for p in phases[:2]:
        print(f"  Phase: {p.get('title','')[:80]}")
        for s in p.get("steps", [])[:2]:
            print(f"    Step: {s.get('id','')} - {s.get('title','')[:60]}")
else:
    print("\n--- roadmap.json --- MISSING")

# Simulation registry
spath = BASE / "simulation_registry.json"
if spath.exists():
    with open(spath) as f:
        s = json.load(f)
    sims = s.get("simulations", [])
    print(f"\n--- simulation_registry.json ---")
    print(f"Simulations: {len(sims)}")
    for sim in sims[:3]:
        print(f"  {sim.get('id','')}: {sim.get('concept_id','')} - {sim.get('title','')[:60]}")
else:
    print("\n--- simulation_registry.json --- MISSING")

# Question bank
qpath = BASE / "question_bank.json"
if qpath.exists():
    with open(qpath) as f:
        qb = json.load(f)
    questions = qb.get("questions", [])
    qtypes = Counter(q.get("type", "??") for q in questions)
    print(f"\n--- question_bank.json ---")
    print(f"Questions: {len(questions)}")
    print(f"By type: {dict(qtypes)}")
    for q in questions[:3]:
        print(f"  [{q.get('type','')}] {q.get('concept_id','')} - {q.get('prompt','')[:80]}")
else:
    print("\n--- question_bank.json --- MISSING")
