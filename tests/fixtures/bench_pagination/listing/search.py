"""Search results with pagination metadata."""

from listing.paginate import page_count, page_slice


def search(items: list[str], term: str, page: int = 1, size: int = 10) -> dict:
    """Filter items and return one page plus the number of pages."""
    matches = [item for item in items if term.lower() in item.lower()]
    return {"results": page_slice(matches, page, size), "pages": page_count(len(matches), size)}
