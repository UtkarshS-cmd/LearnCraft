#!/usr/bin/env python3
"""Smoke-test the curriculum API endpoints with the class-10 package."""
import os
import sys

os.environ.setdefault("LEARNCRAFT_SECRET_KEY", "test")
os.environ.setdefault("LEARNCRAFT_DB_PATH", ":memory:")

from app.main import app

client = app.test_client()

print("=" * 60)
print("API SMOKE TEST")
print("=" * 60)

# Test 1: List classes
r = client.get("/api/v1/curriculum/classes")
print(f"\nGET /api/v1/curriculum/classes: {r.status_code}")
data = r.get_json()
print(f"  classes: {[c['dir'] for c in data['items']]}")

# Test 2: Get class10
r = client.get("/api/v1/curriculum/class10")
print(f"\nGET /api/v1/curriculum/class10: {r.status_code}")
data = r.get_json()
print(f"  package_id: {data.get('package_id')}")
print(f"  counts: subjects={data['counts']['subjects']}, chapters={data['counts']['chapters']}, concepts={data['counts']['concepts']}")

# Test 3: Roadmap
r = client.get("/api/v1/curriculum/class10/roadmap")
print(f"\nGET /api/v1/curriculum/class10/roadmap: {r.status_code}")
data = r.get_json()
print(f"  subjects: {[s['subject_slug'] for s in data.get('subjects', [])]}")
for s in data.get("subjects", []):
    terms = s.get("terms", [])
    total_concepts = sum(len(t.get("concepts", [])) for t in terms)
    print(f"    {s['subject_slug']}: {len(terms)} terms, {total_concepts} concepts")

# Test 4: Concept graph
r = client.get("/api/v1/curriculum/class10/concept-graph")
print(f"\nGET /api/v1/curriculum/class10/concept-graph: {r.status_code}")
data = r.get_json()
print(f"  nodes: {len(data.get('nodes', []))}")

# Test 5: Simulations
r = client.get("/api/v1/curriculum/class10/simulations")
print(f"\nGET /api/v1/curriculum/class10/simulations: {r.status_code}")
data = r.get_json()
print(f"  catalog items: {len(data.get('catalog', []))}")
print(f"  mappings: {len(data.get('mappings', []))}")

# Test 6: Question bank summary
r = client.get("/api/v1/curriculum/class10/question-bank/summary")
print(f"\nGET /api/v1/curriculum/class10/question-bank/summary: {r.status_code}")
data = r.get_json()
print(f"  total: {data.get('total')}")
print(f"  by_type: {data.get('by_type')}")

# Test 7: Question bank (limited)
r = client.get("/api/v1/curriculum/class10/question-bank?limit=3&chapter_id=cbse-x-2026-27-maths-polynomials")
print(f"\nGET /api/v1/curriculum/class10/question-bank?limit=3: {r.status_code}")
data = r.get_json()
print(f"  count: {data['count']}")
for q in data["items"]:
    print(f"    {q['question_id']} [{q['question_type']}] verified={q['verified']}")

# Test 8: Subject
r = client.get("/api/v1/curriculum/class10/subjects/mathematics")
print(f"\nGET /api/v1/curriculum/class10/subjects/mathematics: {r.status_code}")
data = r.get_json()
print(f"  subject: {data.get('name')} ({len(data.get('chapters', []))} chapters)")

# Test 9: Concept simulations
r = client.get("/api/v1/curriculum/class10/concepts/cbse-x-2026-27-maths-concept-prime-factorisation/simulations")
print(f"\nGET /api/v1/curriculum/class10/concepts/.../simulations: {r.status_code}")
data = r.get_json()
print(f"  items: {len(data.get('items', []))}")

# Test 10: 404
r = client.get("/api/v1/curriculum/class9")
print(f"\nGET /api/v1/curriculum/class9 (expect 404): {r.status_code}")
assert r.status_code == 404, f"Expected 404, got {r.status_code}"

print("\n" + "=" * 60)
print("API SMOKE TEST PASSED")
print("=" * 60)
