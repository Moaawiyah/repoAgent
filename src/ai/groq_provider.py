"""Groq structured outputs using the official Groq Python SDK."""

from repoagent.ai.chat import arguments, completion
from repoagent.ai.provider import CompletionRequest, CompletionResult
from repoagent.config import Settings
from repoagent.domain.errors import LLMError


class GroqProvider:
    name = "groq"

    def __init__(self, settings: Settings) -> None:
        if not settings.llm_api_key:
            raise LLMError("Groq requires REPOAGENT_LLM_API_KEY")
        self._settings = settings

    def complete(self, request: CompletionRequest) -> CompletionResult:
        from groq import APIError, Groq

        settings = self._settings
        try:
            with Groq(
                api_key=settings.llm_api_key.get_secret_value(),
                timeout=settings.llm_timeout,
                max_retries=0,
            ) as client:
                response = client.chat.completions.create(
                    **arguments(
                        request, settings.llm_model, settings.llm_max_output_tokens
                    )
                )
        except APIError:
            raise LLMError(
                "Groq request failed; check configuration and free-tier rate limits"
            ) from None
        return completion(response, settings.llm_model)
