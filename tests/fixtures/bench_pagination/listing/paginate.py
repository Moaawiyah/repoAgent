"""Pagination for search result listings."""


def page_count(total_items: int, page_size: int) -> int:
    """Number of pages needed to show every item."""
    if page_size <= 0:
        raise ValueError("page_size must be positive")
    return total_items // page_size


def page_slice(items: list, page: int, page_size: int) -> list:
    """Items shown on a 1-based page."""
    start = (page - 1) * page_size
    return items[start : start + page_size]
