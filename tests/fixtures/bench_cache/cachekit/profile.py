"""Cached profile lookups for the API."""

from cachekit.keys import make_key
from cachekit.ttl import TTLCache


def cached_profile(cache: TTLCache, user_id: int, fetch) -> dict:
    """Fetch a profile once per cache lifetime."""
    key = make_key("profile", user_id)
    value = cache.get(key)
    if value is None:
        value = fetch(user_id)
        cache.set(key, value)
    return value
