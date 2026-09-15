"""Cache key construction."""


def make_key(namespace: str, *parts: object) -> str:
    """Stable colon-separated key."""
    return ":".join([namespace, *map(str, parts)])
