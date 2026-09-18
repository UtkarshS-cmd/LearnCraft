"""Print the structural schema of a curriculum package JSON."""
import json
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "data/curriculum/cbse_class_x_2026_27.json"
d = json.load(open(path, encoding="utf-8"))
print("top keys:", list(d.keys()))
print("board/class/year:", d.get("board"), d.get("class_level"), d.get("academic_year"))
for s in d["subjects"]:
    print("subject:", s["slug"], "keys:", [k for k in s.keys() if k not in ("chapters",)])
    chs = s.get("chapters", [])
    print("  chapters:", len(chs))
    if not chs:
        continue
    ch = chs[0]
    print("  chapter keys:", list(ch.keys()))
    t = ch["topics"][0]
    print("  topic keys:", list(t.keys()))
    l = t["lessons"][0]
    print("  lesson keys:", list(l.keys()))
    print("  objectives:", l.get("learning_objectives"))
    blocks = l.get("content_blocks") or l.get("content_blocks_json")
    print("  block types:", [b.get("type") for b in blocks] if isinstance(blocks, list) else type(blocks))
    if isinstance(blocks, list):
        print("  block0:", json.dumps(blocks[0])[:300])
        if len(blocks) > 1:
            print("  block1:", json.dumps(blocks[1])[:300])
    q = t["questions"][0]
    print("  question keys:", list(q.keys()))
    print("  q opt keys:", list(q["options"][0].keys()) if q.get("options") else None)
