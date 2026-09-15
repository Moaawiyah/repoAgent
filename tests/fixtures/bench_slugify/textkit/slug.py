"""URL slug generation for article titles."""

import re


def slugify(title: str) -> str:
    """Lowercase a title and join words with single hyphens."""
    text = title.strip().lower()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    return re.sub(r"\s", "-", text).strip("-")
