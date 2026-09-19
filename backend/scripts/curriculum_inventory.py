"""Inventory curriculum JSON packages: package ids, subjects, chapters, lessons."""
import glob
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

for path in sorted(glob.glob("data/curriculum/*.json")):
    try:
        data = json.load(open(path, encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(path, "-> PARSE ERROR:", exc)
        continue
    subjects = data.get("subjects") or []
    if subjects:
        pkg = data.get("package_id") or data.get("id") or "?"
        chapters = sum(len(s.get("chapters", [])) for s in subjects)
        lessons = sum(len(c.get("lessons", [])) for s in subjects for c in s.get("chapters", []))
        questions = sum(len(c.get("questions", [])) for s in subjects for c in s.get("chapters", []))
        names = ", ".join(s.get("slug", "?") for s in subjects)
        print(f"{path}: pkg={pkg} subjects=[{names}] chapters={chapters} lessons={lessons} questions={questions}")
        for s in subjects:
            for c in s.get("chapters", []):
                n_lessons = len(c.get("lessons", []))
                n_q = len(c.get("questions", []))
                print(f"    {s.get('slug','?')}/{c.get('chapter_id','?')}: {c.get('title','?')[:60]} (L={n_lessons}, Q={n_q})")
    else:
        print(f"{path}: keys={list(data.keys())[:8]}")
