"""Deterministic LLM budget: call count, token total and task deadline.

Wraps any ``LLMProvider``. Once a bound is reached every further call
raises ``LLMBudgetExceeded`` (an ``LLMError``), which existing agents
already turn into an explicit provider-error/uncertain outcome instead of
continuing. The deadline makes the whole workflow's LLM phase time-bounded.
"""

import time
from collections.abc import Callable

from repoagent.ai.provider import CompletionRequest, CompletionResult, LLMProvider
from repoagent.domain.errors import LLMError


class LLMBudgetExceeded(LLMError):
    """A deterministic workflow limit stopped further LLM calls."""


class BudgetedProvider:
    def __init__(
        self,
        provider: LLMProvider,
        *,
        max_calls: int,
        max_tokens: int | None = None,
        timeout_seconds: float | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._provider, self._clock = provider, clock
        self.name = provider.name
        self._max_calls, self._max_tokens = max_calls, max_tokens
        self._deadline = clock() + timeout_seconds if timeout_seconds else None
        self.calls = 0
        self.tokens = 0

    def _check(self) -> None:
        if self.calls >= self._max_calls:
            raise LLMBudgetExceeded(f"LLM call limit reached ({self._max_calls})")
        if self._max_tokens is not None and self.tokens >= self._max_tokens:
            raise LLMBudgetExceeded(f"LLM token budget reached ({self._max_tokens})")
        if self._deadline is not None and self._clock() >= self._deadline:
            raise LLMBudgetExceeded("Task time limit reached")

    def complete(self, request: CompletionRequest) -> CompletionResult:
        self._check()
        self.calls += 1
        result = self._provider.complete(request)
        self.tokens += result.usage.input_tokens + result.usage.output_tokens
        return result
