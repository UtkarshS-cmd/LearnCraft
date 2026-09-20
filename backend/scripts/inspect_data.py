"""Inspect existing Class X curriculum data files."""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

for name in ("mathematics", "science", "social-science"):
    with open(f"data/curriculum/{name}.json", encoding="utf-8") as fh:
        d = json.load(fh)
    print("==", name, d.get("subject_id"))
    for c in d.get("chapters", []):
        n_les = sum(len(t.get("lessons", [])) for t in c.get("topics", []))
        n_q = sum(len(t.get("questions", [])) for t in c.get("topics", []))
        concepts = [
            con["concept_id"]
            for t in c.get("topics", [])
            for l in t.get("lessons", [])
            for con in l.get("concepts", [])
        ]
        print(f"  ch{c['chapter_number']} {c['chapter_id']} | {c['title']} | "
              f"lessons={n_les} q={n_q} concepts={len(concepts)}")

print()
print("== ncert_class10_syllabus.json")
with open("data/curriculum/ncert_class10_syllabus.json", encoding="utf-8") as fh:
    d = json.load(fh)
for subj, chapters in d.items():
    print(subj, "type:", type(chapters).__name__)
    if isinstance(chapters, list):
        for c in chapters:
            qs = c.get("questions", [])
            print(f"  ch{c.get('chapter_number')} {c.get('chapter_name')} questions={len(qs)}")
            if qs:
                print("    sample keys:", sorted(qs[0].keys()))
                break
