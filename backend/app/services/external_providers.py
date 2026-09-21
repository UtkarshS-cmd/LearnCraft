"""Central registry of supported external learning providers.

Link-out only: LearnCraft never scrapes these platforms. Each entry carries
the official homepage URL, capabilities, and the host allowlist used by URL
validation. Provider-specific behavior lives here - never in curriculum pages.
"""

from __future__ import annotations

PROVIDERS: dict[str, dict] = {
    "notion": {
        "provider_id": "notion",
        "name": "Notion",
        "description": "Knowledge workspace for study notes and plans.",
        "official_url": "https://www.notion.com/",
        "icon": "📝",
        "allowed_hosts": {"notion.com", "www.notion.com"},
        "supported_resource_types": ["note", "document", "study_plan", "article"],
        "authentication_supported": True,
        "embedding_supported": True,
        "deep_link_supported": True,
    },
    "obsidian": {
        "provider_id": "obsidian",
        "name": "Obsidian",
        "description": "Local-first personal knowledge graph.",
        "official_url": "https://obsidian.md/",
        "icon": "🧠",
        "allowed_hosts": {"obsidian.md"},
        "supported_resource_types": ["note", "document"],
        "authentication_supported": False,
        "embedding_supported": False,
        "deep_link_supported": True,
        "local_first": True,
    },
    "physics_wallah": {
        "provider_id": "physics_wallah",
        "name": "Physics Wallah",
        "description": "Lectures and courses (external links only).",
        "official_url": "https://www.pw.live/",
        "icon": "🎓",
        "allowed_hosts": {"pw.live", "www.pw.live"},
        "supported_resource_types": ["lecture", "course", "video"],
        "authentication_supported": False,
        "embedding_supported": False,
        "deep_link_supported": True,
    },
    "khan_academy": {
        "provider_id": "khan_academy",
        "name": "Khan Academy",
        "description": "Concept lessons and practice.",
        "official_url": "https://www.khanacademy.org/",
        "india_url": "https://india.khanacademy.org/",
        "icon": "📚",
        "allowed_hosts": {"khanacademy.org", "www.khanacademy.org", "india.khanacademy.org"},
        "supported_resource_types": ["lesson", "video", "practice", "course", "article"],
        "authentication_supported": False,
        "embedding_supported": True,
        "deep_link_supported": True,
    },
    "anki": {
        "provider_id": "anki",
        "name": "Anki",
        "description": "Spaced-repetition flashcards.",
        "official_url": "https://apps.ankiweb.net/",
        "icon": "🧠",
        "allowed_hosts": {"apps.ankiweb.net", "ankiweb.net"},
        "supported_resource_types": ["flashcard", "practice"],
        "authentication_supported": False,
        "embedding_supported": False,
        "deep_link_supported": False,
    },
    "github": {
        "provider_id": "github",
        "name": "GitHub",
        "description": "Code examples, DSA and projects.",
        "official_url": "https://github.com/",
        "icon": "💻",
        "allowed_hosts": {"github.com", "www.github.com"},
        "supported_resource_types": ["repository", "practice", "article"],
        "authentication_supported": False,
        "embedding_supported": False,
        "deep_link_supported": True,
    },
    "youtube": {
        "provider_id": "youtube",
        "name": "YouTube",
        "description": "Verified educational videos.",
        "official_url": "https://www.youtube.com/",
        "icon": "▶",
        "allowed_hosts": {"youtube.com", "www.youtube.com", "youtu.be", "www.youtube-nocookie.com"},
        "supported_resource_types": ["video", "lecture"],
        "authentication_supported": False,
        "embedding_supported": True,
        "deep_link_supported": True,
    },
    "google_drive": {
        "provider_id": "google_drive",
        "name": "Google Drive",
        "description": "Study documents and folders.",
        "official_url": "https://drive.google.com/",
        "icon": "📁",
        "allowed_hosts": {"drive.google.com", "docs.google.com"},
        "supported_resource_types": ["document", "note", "study_plan"],
        "authentication_supported": True,
        "embedding_supported": False,
        "deep_link_supported": True,
    },
}

RESOURCE_TYPES = {
    "lecture", "course", "video", "note", "document", "flashcard",
    "repository", "practice", "simulation", "article", "study_plan", "lesson",
}

DIFFICULTIES = {"BEGINNER", "FOUNDATION", "EASY", "MEDIUM", "HARD", "ADVANCED"}


def get_provider(provider_id: str) -> dict | None:
    return PROVIDERS.get(str(provider_id or "").strip().lower())


def list_providers() -> list[dict]:
    items = []
    for info in PROVIDERS.values():
        item = dict(info)
        hosts = item.get("allowed_hosts")
        if isinstance(hosts, set):
            item["allowed_hosts"] = sorted(hosts)
        items.append(item)
    return items


def provider_ids() -> set[str]:
    return set(PROVIDERS)


__all__ = ["PROVIDERS", "RESOURCE_TYPES", "DIFFICULTIES", "get_provider", "list_providers", "provider_ids"]
