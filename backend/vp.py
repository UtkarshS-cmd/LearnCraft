import os, sys, json
os.environ["LEARNCRAFT_SECRET_KEY"] = "test"
os.environ["LEARNCRAFT_DB_PATH"] = ":memory:"
sys.path.insert(0, ".")
from app.services.curriculum_pipeline import (
    load_all_packages, available_class_dirs,
    load_class_package, load_question_bank, load_concept_graph,
    load_simulation_registry, load_roadmap, validate_class_package,
    build_concept_graph, generate_roadmap, filter_questions,
    question_bank_summary, package_summary, resolve_class_dir,
)
from app.schemas.curriculum import CurriculumPackage, Concept, Question, SourceMetadata, Difficulty, QuestionType, CompetencyCategory, Board, CANONICAL_SCHEMA_VERSION
from pathlib import Path
from collections import Counter
import tempfile

CURRICULUM = Path("data/curriculum")
c10 = CURRICULUM / "class10"
errors = []
def check(cond, msg):
    if not cond: errors.append(msg)

print("=== VERIFICATION START ===")

# 1. Schema
print("[1] SCHEMA")
c = Concept("cid","title",difficulty=Difficulty.MEDIUM,prerequisites=["p1"],
    next_concepts=["n1"],competencies=[CompetencyCategory.APPLY],
    source_metadata=SourceMetadata("sid","ncert","t","p","url","v","ay"),
    verified=False,ai_generation_notes="test",activities=["a1"],
    simulation_mappings=["s1"],question_ids=["q1"],learning_objectives=["lo1"])
d = c.to_dict(); c2 = Concept.from_dict(d)
check(c2.concept_id=="cid","C roundtrip")
check(c2.difficulty==Difficulty.MEDIUM,"C diff")
check(c2.prerequisites==["p1"],"C prereqs")
check(c2.verified is False,"C verified=False")
check(c2.ai_generation_notes=="test","C ai_notes")
q = Question("qid","cid","chid",QuestionType.MCQ,"prompt","answer",
    ["A","B"],"expl",Difficulty.EASY,CompetencyCategory.REMEMBER,1,"src",False)
d = q.to_dict(); q2 = Question.from_dict(d)
check(q2.question_id=="qid","Q roundtrip")
check(q2.verified is False,"Q verified=False")
check(q2.question_type==QuestionType.MCQ,"Q type")
print(f"  schema ok: {len(errors)} errors")

import os,sys  
os.environ['LEARNCRAFT_SECRET_KEY']='test'  
'os.environ[" "LEARNCRAFT_DB_PATH]=:memory:'  
sys.path.insert(0,'.')  
from app.services.curriculum_pipeline import *  
from app.schemas.curriculum import *  
from pathlib import Path  
C=Path('data/curriculum')/'class10'  
print('OK - C exists:',C.exists())  
