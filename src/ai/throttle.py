"""Proactive client-side rate limiting (tokens and requests per minute).

Provider quotas are per account and model, not per client object, so limiters
are shared per key inside the process. The registry is the only module state
and is guarded by a lock. Reactive 429 retries remain as a backstop.
"""

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

WINDOW_SECONDS = 60.0
MIN_SLEEP_SECONDS = 0.05
CHARS_PER_TOKEN = 3


@dataclass
class Reservation:
    at: float
    tokens: int


def estimate_tokens(prompt_chars: int, max_output_tokens: int) -> int:
    """Conservative request cost: providers count the output ceiling up front."""
    return prompt_chars // CHARS_PER_TOKEN + 1 + max_output_tokens


class SlidingWindowLimiter:
    """Blocks until a request fits the last-60-seconds token and request budget."""

    def __init__(
        self,
        tokens_per_minute: int | None,
        requests_per_minute: int | None,
        clock: Callable[[], float] | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self._tpm, self._rpm = tokens_per_minute, requests_per_minute
        self._clock = clock or time.monotonic
        self._sleep = sleep or (lambda seconds: time.sleep(seconds))
        self._events: list[Reservation] = []
        self._lock = threading.Lock()

    def acquire(self, tokens: int) -> Reservation:
        while True:
            with self._lock:
                now = self._clock()
                self._events = [e for e in self._events if now - e.at < WINDOW_SECONDS]
                used = sum(e.tokens for e in self._events)
                fits_tokens = self._tpm is None or used + tokens <= self._tpm
                # A single request larger than the budget may run on an empty window.
                fits_tokens = fits_tokens or not self._events
                fits_requests = self._rpm is None or len(self._events) < self._rpm
                if fits_tokens and fits_requests:
                    reservation = Reservation(at=now, tokens=tokens)
                    self._events.append(reservation)
                    return reservation
                wait = self._events[0].at + WINDOW_SECONDS - now
            self._sleep(max(wait, MIN_SLEEP_SECONDS))

    def settle(self, reservation: Reservation, actual_tokens: int) -> None:
        """Replace the estimate with provider-reported usage when available."""
        if actual_tokens > 0:
            with self._lock:
                reservation.tokens = actual_tokens


_REGISTRY: dict[tuple, SlidingWindowLimiter] = {}
_REGISTRY_LOCK = threading.Lock()


def shared_limiter(
    key: str, tokens_per_minute: int | None, requests_per_minute: int | None
) -> SlidingWindowLimiter | None:
    if tokens_per_minute is None and requests_per_minute is None:
        return None
    identity = (key, tokens_per_minute, requests_per_minute)
    with _REGISTRY_LOCK:
        if identity not in _REGISTRY:
            _REGISTRY[identity] = SlidingWindowLimiter(
                tokens_per_minute, requests_per_minute
            )
        return _REGISTRY[identity]
