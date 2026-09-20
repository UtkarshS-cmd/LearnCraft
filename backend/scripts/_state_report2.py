"""Write a snapshot of the repo state to _state_report2.txt (dev helper, not shipped)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "_state_report2.txt"
sys.path.insert(0, str(ROOT))

lines: list[str] = []


def add(title: str) -> None:
    lines.append("")
    lines.append(f"=== {title} ===")


add("data/curriculum files")
for p in sorted((ROOT / "data" / "curriculum").rglob("*")):
    if p.is_file():
        lines.append(f"{p.relative_to(ROOT)} {p.stat().st_size}")

add("app py tree")
for p in sorted((ROOT / "app").rglob("*.py")):
    lines.append(str(p.relative_to(ROOT)))

add("tests py tree")
for p in sorted((ROOT / "tests").rglob("*.py")):
    lines.append(str(p.relative_to(ROOT)))

add("frontend assets")
for base in (ROOT.parent / "frontend", ROOT / "app" / "static", ROOT / "app" / "templates"):
    if base.exists():
        for p in sorted(base.rglob("*")):
            if p.is_file() and p.suffix in (".js", ".html", ".css"):
                lines.append(f"{p} {p.stat().st_size}")

add("schema module")
try:
    from app.schemas import curriculum as c
    for name in sorted(dir(c)):
        obj = getattr(c, name)
        if isinstance(obj, type) and hasattr(obj, "__dataclass_fields__"):
            lines.append(f"dataclass {name}: {sorted(obj.__dataclass_fields__)}")
    lines.append(f"CANONICAL_SCHEMA_VERSION={getattr(c, 'CANONICAL_SCHEMA_VERSION', None)}")
    lines.append(f"SCHEMA_DOC={getattr(c, 'SCHEMA_DOC', None)}")
except Exception as exc:  # pragma: no cover - dev helper
    lines.append(f"schema import failed: {exc!r}")

add("content_catalog")
try:
    from app.services import content_catalog as cc
    lines.append(f"CURRICULUM_DIR={cc.CURRICULUM_DIR}")
    for name in sorted(dir(cc)):
        if name.isupper() and not name.startswith("_"):
            val = getattr(cc, name)
            if isinstance(val, (str, int, dict, list, tuple, set)):
                lines.append(f"{name}={val}")
    for fn_name in ("load_packages", "load_class_packages", "list_class_packages"):
        fn = getattr(cc, fn_name, None)
        if callable(fn):
            try:
                res = fn()
                lines.append(f"{fn_name}() ok -> {type(res).__name__} len={len(res)}")
                if isinstance(res, (list, tuple)):
                    for item in res[:10]:
                        if isinstance(item, dict):
                            lines.append("   " + json.dumps(item, default=str)[:300])
            except Exception as exc:
                lines.append(f"{fn_name}() failed: {exc!r}")
except Exception as exc:  # pragma: no cover
    lines.append(f"content_catalog import failed: {exc!r}")

add("curriculum_pipeline")
try:
    from app.services import curriculum_pipeline as cp
    for name in sorted(dir(cp)):
        if not name.startswith("_"):
            obj = getattr(cp, name)
            if callable(obj) or isinstance(obj, (str, int, dict, list, tuple, set)):
                lines.append(f"{name}: {type(obj).__name__}")
except Exception as exc:  # pragma: no cover
    lines.append(f"curriculum_pipeline import failed: {exc!r}")

OUT.write_text("\n".join(lines), encoding="utf-8")
print("wrote", OUT)
