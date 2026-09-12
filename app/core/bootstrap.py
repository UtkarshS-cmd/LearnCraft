"""Initialization helpers for the structured LearnCraft app package."""

from database import initialize_database


def bootstrap_app() -> None:
    """Initialize the SQLite schema for the app."""
    initialize_database()


__all__ = ["bootstrap_app"]
