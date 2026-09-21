import os
os.environ.setdefault("LEARNCRAFT_SECRET_KEY", "test")
os.environ.setdefault("LEARNCRAFT_DB_PATH", ":memory:")
import sys
sys.path.insert(0, ".")
