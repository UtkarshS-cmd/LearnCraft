from __future__ import annotations


def is_valid_email(value: str) -> bool:
    return "@" in value and "." in value.split("@")[-1]
