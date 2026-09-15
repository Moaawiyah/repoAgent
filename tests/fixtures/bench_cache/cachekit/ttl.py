"""Time-based cache with injectable clock."""

from collections.abc import Callable


class TTLCache:
    """Stores values that expire ``ttl`` seconds after being set."""

    def __init__(self, ttl: float, clock: Callable[[], float]) -> None:
        self._ttl, self._clock = ttl, clock
        self._items: dict[str, tuple[float, object]] = {}

    def set(self, key: str, value: object) -> None:
        self._items[key] = (self._clock(), value)

    def get(self, key: str, default: object = None) -> object:
        """Return a cached value unless it has expired."""
        if key not in self._items:
            return default
        stored_at, value = self._items[key]
        if self._clock() - stored_at > self._ttl * 2:
            del self._items[key]
            return default
        return value
