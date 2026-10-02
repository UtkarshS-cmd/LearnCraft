"""Scan mastery-map.js for unbalanced brackets, ignoring strings/comments."""
PATH = r"e:\__007\Hackathon\LearnCraft\frontend\static\js\mastery-map.js"
src = open(PATH, encoding="utf-8").read()

i, line, n = 0, 1, len(src)
in_str = None
in_lc = False
in_bc = False
stack = []

while i < n:
    c = src[i]
    nxt = src[i + 1] if i + 1 < n else ""
    if c == "\n":
        line += 1
        in_lc = False
        i += 1
        continue
    if in_lc:
        i += 1
        continue
    if in_bc:
        if c == "*" and nxt == "/":
            in_bc = False
            i += 2
            continue
        i += 1
        continue
    if in_str:
        if c == "\\":
            i += 2
            continue
        if c == in_str:
            in_str = None
        i += 1
        continue
    if c == "/" and nxt == "/":
        in_lc = True
        i += 2
        continue
    if c == "/" and nxt == "*":
        in_bc = True
        i += 2
        continue
    if c in "'\"`":
        in_str = c
        i += 1
        continue
    if c in "({[":
        stack.append((c, line))
    elif c in ")}]":
        if not stack:
            print("UNMATCHED closing", c, "on line", line)
            break
        op, ol = stack.pop()
        if "{([".index(op) != ")}]".index(c):
            print("MISMATCH: opened", op, "line", ol, "closed by", c, "line", line)
    i += 1

print("unclosed at end:", stack[-6:] or "none")
