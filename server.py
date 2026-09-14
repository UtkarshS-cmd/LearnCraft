"""Compatibility entry point for running LearnCraft from the repository root."""

from app.main import app, create_app

__all__ = ["app", "create_app"]


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
