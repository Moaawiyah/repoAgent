"""Article records exposed by the blog."""

from textkit.slug import slugify
from textkit.truncate import truncate_words


def article_url(title: str) -> str:
    """Public URL path for an article."""
    return f"/articles/{slugify(title)}"


def preview(body: str) -> str:
    """Short preview text for listing pages."""
    return truncate_words(body, 20)
