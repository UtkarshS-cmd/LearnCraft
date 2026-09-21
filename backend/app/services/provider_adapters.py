"""Provider adapters (P2 interfaces): Notion, Anki export, GitHub projects.

Link-out is implemented today. These adapters define the seam for future
authenticated integrations WITHOUT storing any tokens in the database.
Tokens/keys live in environment variables only (NOTION_* / GITHUB_*).
"""

from __future__ import annotations

import csv
import io
import os


class NotionAdapter:
    """Documented interface for optional Notion API integration (Level 2).

    Today LearnCraft uses Level 1 (external links). When a deployment opts in,
    implement these methods against the official Notion API using a server-side
    token from the environment. Never accept tokens via normal frontend fields.
    """

    def __init__(self, token: str | None = None):
        self.token = token or os.environ.get("NOTION_API_TOKEN", "")
        self.configured = bool(self.token)

    def status(self) -> dict:
        return {"provider": "notion", "level": 1 if not self.configured else 2,
                "configured": self.configured,
                "message": "Link-out only" if not self.configured else "API adapter available"}

    def open_workspace_url(self) -> str:
        return "https://www.notion.com/"

    # --- Level 2 stubs (require configured token; raise until implemented) ---
    def create_study_note(self, title: str, body: str, **kwargs) -> dict:
        raise NotImplementedError("Notion API integration is not configured (Level 1 link-only).")

    def create_study_plan(self, title: str, items: list, **kwargs) -> dict:
        raise NotImplementedError("Notion API integration is not configured (Level 1 link-only).")

    def export_learncraft_notes(self, notes: list, **kwargs) -> dict:
        raise NotImplementedError("Notion API integration is not configured (Level 1 link-only).")


def flashcards_to_tsv(cards: list[dict]) -> str:
    """Convert [{front, back, tags}] to Anki-compatible TSV (import via Anki desktop)."""
    output = io.StringIO()
    writer = csv.writer(output, delimiter="\t", lineterminator="\n")
    for card in cards or []:
        front = str(card.get("front", "")).strip().replace("\n", "<br>")
        back = str(card.get("back", "")).strip().replace("\n", "<br>")
        if not front or not back:
            continue
        tags = " ".join(str(t).strip().replace(" ", "_") for t in (card.get("tags") or []) if str(t).strip())
        writer.writerow([front, back, tags])
    return output.getvalue()


def validate_github_project_url(url: str) -> str:
    """Validate a github.com project URL via the shared provider allowlist."""
    from app.services.external_resources import validate_external_url
    return validate_external_url("github", url)


def parse_github_repo(url: str) -> dict:
    """Validate a GitHub URL and derive owner/repo metadata (seam for student_project).

    Returns {repository_url, owner, repository, full_name, language, topics, student_project}.
    Raises ValueError for non-GitHub/unsafe URLs or profile-only links.
    """
    from urllib.parse import urlparse

    clean = validate_github_project_url(url)
    parts = [seg for seg in urlparse(clean).path.split("/") if seg]
    if len(parts) < 2:
        raise ValueError("Link a specific repository, e.g. https://github.com/owner/repo.")
    owner, repository = parts[0], parts[1]
    if repository.endswith(".git"):
        repository = repository[:-4]
    return {"repository_url": clean, "owner": owner, "repository": repository,
            "full_name": f"{owner}/{repository}", "language": "", "topics": [],
            "student_project": True}


__all__ = ["NotionAdapter", "flashcards_to_tsv", "validate_github_project_url", "parse_github_repo"]
