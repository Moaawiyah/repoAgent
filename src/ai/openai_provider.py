"""Official OpenAI SDK adapter; no vendor types escape this module."""

from repoagent.ai.chat import arguments, completion
from repoagent.ai.provider import CompletionRequest, CompletionResult, LLMProvider
from repoagent.config import Settings
from repoagent.domain.errors import LLMError


class OpenAIChatProvider:
    name = "openai"

    def __init__(self, settings: Settings) -> None:
        if not settings.llm_api_key:
            raise LLMError("OpenAI provider requires REPOAGENT_LLM_API_KEY")
        self._settings = settings

    def complete(self, request: CompletionRequest) -> CompletionResult:
        from openai import APIError, OpenAI

        settings = self._settings
        try:
            with OpenAI(
                api_key=settings.llm_api_key.get_secret_value(),
                base_url=settings.llm_base_url,
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
                "OpenAI request failed; check configuration and rate limits"
            ) from None
        return completion(response, settings.llm_model)


def llm_provider_from_settings(settings: Settings) -> LLMProvider | None:
    if settings.llm_provider == "groq":
        from repoagent.ai.groq_provider import GroqProvider

        return GroqProvider(settings)
    return OpenAIChatProvider(settings) if settings.llm_provider == "openai" else None
