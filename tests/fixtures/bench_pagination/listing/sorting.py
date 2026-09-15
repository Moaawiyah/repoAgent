"""Ordering options for listings."""


def sort_by_name(items: list[str], descending: bool = False) -> list[str]:
    """Case-insensitive name ordering."""
    return sorted(items, key=str.lower, reverse=descending)
