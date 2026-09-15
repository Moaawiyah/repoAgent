from cachekit.profile import cached_profile
from cachekit.ttl import TTLCache


def test_profile_fetched_once_within_ttl():
    now = [0.0]
    calls = []
    cache = TTLCache(10, lambda: now[0])
    fetch = lambda uid: calls.append(uid) or {"id": uid}
    cached_profile(cache, 1, fetch)
    now[0] = 5
    cached_profile(cache, 1, fetch)
    assert calls == [1]
