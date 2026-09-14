"""Provider decorator that measures LLM calls for repair metrics."""

from repoagent.ai.provider import CompletionRequest, CompletionResult, LLMProvider


class CountingProvider:
    """Delegates to a provider while counting completed and attempted calls."""

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider
        self.name = provider.name
        self.calls = 0

    def complete(self, request: CompletionRequest) -> CompletionResult:
        self.calls += 1
        return self._provider.complete(request)
