import os, sys, json, tempfile
from pathlib import Path
os.environ.setdefault("LEARNCRAFT_SECRET_KEY", "test")
os.environ.setdefault("LEARNCRAFT_DB_PATH", ":memory:")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")
from app.services.curriculum_pipeline import *
from app.schemas.curriculum import Difficulty, QuestionType, Board, CANONICAL_SCHEMA_VERSION
CURRICULUM = Path("data/curriculum")
c10 = CURRICULUM / "class10"
errors = []
def check(cond, msg): 
    if not cond: errors.append(str(msg))
print("=" * 60); print("PIPELINE CHECK"); print("=" * 60)
print("\n[1] SCHEMA")
check(Difficulty.FOUNDATION.value == "FOUNDATION", "FOUNDATION")
check(Difficulty.CHALLENGE.value == "CHALLENGE", "CHALLENGE")
for qt in QuestionType: check(qt.value, f"QType {qt.value}")
print(f"  schema: {len(errors)} err")
print("\n[2] CLASS10 PACKAGE")
check(c10.is_dir(), "c10 dir")
check((c10 / "manifest.json").exists(), "manifest")
pkg = load_class_package(c10)
check(pkg.class_level == "Class X", f"class_level={pkg.class_level}")
check(pkg.board == Board.CBSE, f"board={pkg.board}")
check(pkg.academic_year == "2026-27", f"year={pkg.academic_year}")
check(len(pkg.subjects) == 3, f"subjects={len(pkg.subjects)}")
tot = sum(sum(len(ch.concepts) for ch in s.chapters) for s in pkg.subjects)
print(f"  subjects={[s.slug for s in pkg.subjects]} concepts={tot}")
for s in pkg.subjects:
    for ch in s.chapters:
        check(ch.concepts, f"{ch.chapter_id} no concepts")
        for cc in ch.concepts:
            check(cc.source_metadata is not None, f"{cc.concept_id} no source_meta")
print(f"  package: {len(errors)} err")
print("\n[3] CONCEPT GRAPH")
graph = load_concept_graph(c10)
check("nodes" in graph and "label_prerequisites" in graph, "graph keys")
cids = {n["concept_id"] for n in graph["nodes"]}
for n in graph["nodes"]:
    for p in n.get("prerequisites", []): check(p in cids, f"bad prereq {p}")
    for nx in n.get("next_concepts", []): check(nx in cids, f"bad next {nx}")
print(f"  graph: nodes={len(graph['nodes'])} prereqs={len(graph['label_prerequisites'])} err={len(errors)}")
print("\n[4] ROADMAP")
rm = load_roadmap(c10)
check("subjects" in rm and "generated_from" in rm, "rm keys")
check(rm.get("generated_from") == "concept_graph.json", f"rm provenance={rm.get('generated_from')}")
check(rm.get("algorithm") == "topological_dfs", f"rm algo={rm.get('algorithm')}")
gen_rm = generate_roadmap(pkg, build_concept_graph(c10))
check(len(gen_rm["subjects"]) == len(rm["subjects"]), "gen rm match")
print(f"  roadmap: subjects={len(rm['subjects'])} err={len(errors)}")
print("\n[5] SIM REGISTRY")
sim = load_simulation_registry(c10)
check("catalog" in sim and "mappings" in sim, "sim keys")
for e in sim["catalog"]:
    if e.get("simulation_id","").startswith("sim-"):
        check(e.get("offline", False), f"{e['simulation_id']} not offline")
sim_cids = {m["concept_id"] for m in sim["mappings"]}
for cid in sim_cids: check(cid in cids, f"sim unknown concept {cid}")
print(f"  sim: catalog={len(sim['catalog'])} mappings={len(sim['mappings'])} err={len(errors)}")
print("\n[6] QUESTION BANK")
bank = load_question_bank(c10)
check(len(bank) > 0, "empty bank")
for q in bank[:60]:
    if q.question_type == QuestionType.TRUE_FALSE:
        check(q.answer in ("TRUE","FALSE"), f"{q.question_id} TF:{q.answer}")
    elif q.question_type == QuestionType.MCQ and q.options:
        opt_texts = [o.get("text","") for o in q.options]
        if q.answer not in opt_texts: errors.append(f"MCQ ans missing: {q.question_id}")
print(f"  bank: total={len(bank)} verif={sum(1 for q in bank if q.verified)} unverif={sum(1 for q in bank if not q.verified)} err={len(errors)}")
check(filter_questions(c10, question_type="MCQ", verified=True), "no filtered MCQ+verif")
check(filter_questions(c10, difficulty="EASY"), "no filtered EASY")
print("\n[7] VALIDATION")
v = validate_class_package(c10)
check(v.get("valid") is True, f"valid failed: {v.get('errors')}")
with tempfile.TemporaryDirectory() as td:
    tp = Path(td)
    (tp / "manifest.json").write_text(json.dumps({"schema_version":"2026.09.1","board":"CBSE","class_level":"Class X","academic_year":"2026-27","package_id":"bad","version":"1.0.0","source_version":"x","generated_at":"2026-01-01T00:00:00Z","generated_by":"t","source":"t","verified":False,"subjects":[{"subject_id":"s1","class_level":"Class X","board":"CBSE","slug":"math","name":"Math","description":"x","book_id":"b","book_title":"t","publisher":"NCERT","source":"t","verified":False,"chapters":[{"chapter_id":"c1","class_level":"Class X","subject_slug":"math","chapter_number":1,"title":"t","summary":"x","description":"x","concepts":[{"concept_id":"x","title":"x","description":"x","explanation":"x","difficulty":"INVALID","learning_objectives":[],"prerequisites":["ghost"],"next_concepts":["ghost2"],"competencies":["BAD"],"activities":[],"simulation_mappings":["ghost-sim"],"question_ids":["ghost-q"],"source_metadata":None,"verified":False,"ai_generation_notes":None}],"sub_concepts":[],"learning_objectives":[],"activities":[],"simulation_mappings":[],"difficulty":"INVALID","prerequisites":[],"competencies":["BAD"],"lesson_ids":[],"source":"t","verified":False,"verified_at":None}]}]}, encoding="utf-8")
    bv = validate_class_package(tp)
    check(bv.get("valid") is False, "bad should fail")
print(f"  validation: err={len(errors)}")
print("\n[8] UTILITIES")
check(resolve_class_dir("class10") == c10, "resolve")
check(resolve_class_dir("nonexistent") is None, "resolve miss")
check(len(available_class_dirs()) >= 1, "available dirs")
print(f"  utilities: err={len(errors)}")
print("\n" + "=" * 60)
print(f"RESULT: {'PASS' if not errors else 'FAIL'} ({len(errors)} errors)")
if errors:
    for e in errors[:10]: print(f"  ERROR: {e}")
import sys as _sys; _sys.exit(0 if not errors else 1)
