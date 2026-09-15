"""Bounded retry for provider rate limits (HTTP 429); other errors never retry."""

import logging
import time
from collections.abc import Callable

LOGGER = logging.getLogger(__name__)
BASE_BACKOFF_SECONDS = 2.0


def retry_after_seconds(error: Exception) -> float | None:
    """Server-provided delay from ``retry-after-ms`` / ``retry-after`` headers."""
    response = getattr(error, "response", None)
    headers = getattr(response, "headers", None) or {}
    for name, scale in (("retry-after-ms", 0.001), ("retry-after", 1.0)):
        value = headers.get(name)
        if value is None:
            continue
        try:
            return max(0.0, float(value) * scale)
        except (TypeError, ValueError):
            continue
    return None


class RateLimitRetry:
    """Retries only the given rate-limit exception, with capped waits."""

    def __init__(
        self,
        retries: int,
        max_wait_seconds: float,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self._retries, self._max_wait = retries, max_wait_seconds
        self._sleep = sleep or (lambda seconds: time.sleep(seconds))

    def call[T](self, operation: Callable[[], T], rate_limit: type[Exception]) -> T:
        for attempt in range(self._retries + 1):
            try:
                return operation()
            except rate_limit as error:
                delay = retry_after_seconds(error)
                # A server delay beyond the wait cap (e.g. an exhausted daily
                # quota) will not clear in time: fail fast instead of sleeping.
                if attempt == self._retries or (
                    delay is not None and delay > self._max_wait
                ):
                    raise
                if delay is None:
                    delay = BASE_BACKOFF_SECONDS * 2**attempt
                LOGGER.warning(
                    "Provider rate limited",
                    extra={"event": "llm_rate_limited", "status": attempt + 1},
                )
                self._sleep(min(delay, self._max_wait))
        raise AssertionError("unreachable")  # pragma: no cover
