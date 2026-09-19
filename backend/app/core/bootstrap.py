"""Initialization helpers for the structured LearnCraft app package."""

from app.database.connection import initialize_database


def bootstrap_app() -> None:
    """Initialize the SQLite schema for the app."""
    initialize_database()


__all__ = ["bootstrap_app"]
