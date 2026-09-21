import os
os.environ["LEARNCRAFT_SECRET_KEY"] = "test"
os.environ["LEARNCRAFT_DB_PATH"] = ":memory:"
import sys
sys.path.insert(0, ".")
from pathlib import Path
from app.services.curriculum_pipeline import load_all_packages
pkgs = load_all_packages()
print("Packages:", list(pkgs.keys()))
for k, p in pkgs.items():
    slugs = [s.slug for s in p.subjects]
    print(f"  {k}: {slugs}")