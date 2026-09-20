"""Smoke-test the /api/v1/curriculum endpoints (offline)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.main import app  # noqa: E402

client = app.test_client()

checks = [
    ("/api/v1/curriculum/classes", 200),
    ("/api/v1/curriculum/class10", 200),
    ("/api/v1/curriculum/Class X", 200),
    ("/api/v1/curriculum/unknown-class", 404),
    ("/api/v1/curriculum/class10/roadmap", 200),
    ("/api/v1/curriculum/class10/concept-graph", 200),
    ("/api/v1/curriculum/class10/simulations", 200),
    ("/api/v1/curriculum/class10/question-bank/summary", 200),
    ("/api/v1/curriculum/class10/question-bank?limit=3", 200),
    ("/api/v1/curriculum/class10/question-bank?verified=true", 200),
    ("/api/v1/curriculum/class10/question-bank?question_type=MCQ", 200),
    ("/api/v1/curriculum/class10/subjects/mathematics", 200),
    ("/api/v1/curriculum/class10/subjects/nope", 404),
]

lines = []
ok = True
for url, expected in checks:
    resp = client.get(url)
    status = resp.status_code
    payload = resp.get_json(silent=True) or {}
    marker = "OK " if status == expected else "FAIL"
    if status != expected:
        ok = False
    lines.append(f"{marker} {status:3d} (want {expected}) {url}")
    if "question-bank" in url and status == 200:
        lines.append("      count=" + str(payload.get("count")))
    if url.endswith("/roadmap") and status == 200:
        lines.append("      roadmap subjects=" + str([s["subject_slug"] for s in payload["subjects"]]))
        lines.append("      generated_from=" + str(payload.get("generated_from")))
    if url.endswith("/concept-graph") and status == 200:
        lines.append("      nodes=" + str(len(payload.get("nodes", []))))
    if url.endswith("/simulations") and status == 200:
        lines.append("      catalog=" + str(len(payload.get("catalog", []))) +
                     " mappings=" + str(len(payload.get("mappings", []))))
    if url.endswith("/summary") and status == 200:
        lines.append("      summary=" + json.dumps({k: payload[k] for k in ("total", "verified", "unverified")}))

# concept -> simulation mapping endpoint
resp = client.get("/api/v1/curriculum/class10/concepts/"
                  "cbse-x-2026-27-maths-concept-prime-factorisation/simulations")
lines.append(f"{'OK ' if resp.status_code == 200 else 'FAIL'} {resp.status_code} concept->simulations")
lines.append("      -> " + json.dumps([s.get("simulation_id") for s in resp.get_json()["items"]]))

Path(ROOT / "_curriculum_api_smoke.txt").write_text("\n".join(lines), encoding="utf-8")
print("\n".join(lines))
print("ALL OK" if ok else "FAILURES PRESENT")
