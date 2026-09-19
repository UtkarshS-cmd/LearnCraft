import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

for name in ("mathematics", "science"):
    d = json.load(open(f"data/curriculum/{name}.json", encoding="utf-8"))
    c = d["chapters"][0]
    print("==", name, c["title"])
    for t in c["topics"]:
        print("  topic keys:", list(t.keys()))
        print("  topic sample:", json.dumps(t, ensure_ascii=False)[:600])
        break
