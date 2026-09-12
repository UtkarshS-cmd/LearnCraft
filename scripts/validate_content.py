"""Validate structured curriculum packages before importing them."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.content_catalog import load_packages, validate_packages


def main():
    errors = validate_packages(load_packages())
    if errors:
        raise SystemExit("Content validation failed:\n" + "\n".join(errors))
    packages = load_packages()
    print(f"Valid: {len(packages)} subjects, {sum(len(p['chapters']) for p in packages)} chapters")


if __name__ == "__main__":
    main()
