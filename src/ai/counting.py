"""Provider decorator that measures LLM calls, tokens, and prompt size."""

from pydantic import BaseModel, Field

from repoagent.ai.provider import CompletionRequest, CompletionResult, LLMProvider


class StageUsage(BaseModel):
    """Measured usage for one prompt name (stage)."""

    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    prompt_chars: int = Field(default=0, description="System plus user characters")


class CountingProvider:
    """Delegates to a provider; tokens are provider-reported, never estimated."""

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider
        self.name = provider.name
        self.stages: dict[str, StageUsage] = {}

    @property
    def calls(self) -> int:
        return sum(stage.calls for stage in self.stages.values())

    def total(self, field: str) -> int:
        return sum(getattr(stage, field) for stage in self.stages.values())

    def complete(self, request: CompletionRequest) -> CompletionResult:
        stage = self.stages.setdefault(request.prompt_name, StageUsage())
        stage.calls += 1
        stage.prompt_chars += len(request.system) + len(request.user)
        result = self._provider.complete(request)
        stage.input_tokens += result.usage.input_tokens
        stage.output_tokens += result.usage.output_tokens
        return result
