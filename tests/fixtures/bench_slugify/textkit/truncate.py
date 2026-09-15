"""Summaries for article previews."""


def truncate_words(text: str, limit: int) -> str:
    """Keep at most ``limit`` words, adding an ellipsis when shortened."""
    words = text.split()
    if len(words) <= limit:
        return text
    return " ".join(words[:limit]) + "..."
