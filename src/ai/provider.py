"""Vendor-independent language-model provider contract."""

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from repoagent.domain.errors import LLMError

MAX_PROMPT_CHARS = 60000


class CompletionRequest(BaseModel):
    """One structured prompt; content is treated as data by providers."""

    model_config = ConfigDict(frozen=True)
    output_schema: dict = Field(default_factory=dict)
    prompt_name: str
    system: str = Field(max_length=8000)
    user: str = Field(max_length=MAX_PROMPT_CHARS)


class CompletionUsage(BaseModel):
    """Provider-reported usage when available."""

    model_config = ConfigDict(frozen=True)
    input_tokens: int = 0
    output_tokens: int = 0


class CompletionResult(BaseModel):
    """Raw completion text plus usage and model identity."""

    model_config = ConfigDict(frozen=True)
    text: str
    model: str = ""
    usage: CompletionUsage = Field(default_factory=CompletionUsage)


class LLMProvider(Protocol):
    """Boundary between RepoAgent and any chat-completion backend.

    Concrete adapters own vendor SDKs; domain and application code depend
    only on this protocol. Implementations must be deterministic when
    offline (tests, benchmarks) and must never log prompt bodies.
    """

    name: str

    def complete(self, request: CompletionRequest) -> CompletionResult: ...


def require_provider(provider: LLMProvider | None, purpose: str) -> LLMProvider:
    """Fail with a typed error when no provider is configured."""
    if provider is None:
        raise LLMError(
            f"No LLM provider configured for {purpose}; set REPOAGENT_LLM_PROVIDER"
        )
    return provider
