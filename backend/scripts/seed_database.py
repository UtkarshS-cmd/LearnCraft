from __future__ import annotations

from app.database.connection import initialize_database


if __name__ == "__main__":
    initialize_database()
    print("Database initialized.")
