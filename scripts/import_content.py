"""Import validated structured curriculum packages into the local catalog."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database.connection import initialize_database
from app.services.content_catalog import import_packages, load_packages


def main():
    initialize_database()
    counts = import_packages(load_packages())
    print("Imported:", ", ".join(f"{key}={value}" for key, value in counts.items()))


if __name__ == "__main__":
    main()
