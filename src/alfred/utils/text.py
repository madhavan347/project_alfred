"""Pure text normalization helpers."""

import re


def slugify(value: str, *, maximum_length: int = 60) -> str:
    """Return a lowercase ASCII filename slug, or ``entry`` when empty."""
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower().strip()).strip("-")
    return normalized[:maximum_length].rstrip("-") or "entry"
