"""Official OpenAI SDK adapter; no vendor types escape this module."""

from repoagent.ai.chat import arguments, completion
from repoagent.ai.provider import CompletionRequest, CompletionResult, LLMProvider
from repoagent.ai.rate_limit import RateLimitRetry
from repoagent.ai.throttle import shared_limiter, throttled_call
from repoagent.config import Settings
from repoagent.domain.errors import LLMError


class OpenAIChatProvider:
    """Also serves any OpenAI-compatible endpoint selected via ``llm_base_url``
    (e.g. z.ai); the vendor name in errors/usage always reads ``openai``."""

    name = "openai"

    def __init__(self, settings: Settings) -> None:
        if not settings.llm_api_key:
            raise LLMError("OpenAI provider requires REPOAGENT_LLM_API_KEY")
        self._settings = settings
        self._limiter = shared_limiter(
            f"openai:{settings.llm_base_url or 'api.openai.com'}:{settings.llm_model}",
            settings.llm_tokens_per_minute,
            settings.llm_requests_per_minute,
        )

    def complete(self, request: CompletionRequest) -> CompletionResult:
        from openai import APIError, OpenAI, RateLimitError

        settings = self._settings
        try:
            with OpenAI(
                api_key=settings.llm_api_key.get_secret_value(),
                base_url=settings.llm_base_url,
                timeout=settings.llm_timeout,
                max_retries=0,
            ) as client:
                payload = arguments(
                    request,
                    settings.llm_model,
                    settings.llm_max_output_tokens,
                    settings.llm_structured_output,
                )
                response = RateLimitRetry(
                    settings.llm_rate_limit_retries, settings.llm_rate_limit_max_wait
                ).call(
                    lambda: throttled_call(
                        self._limiter,
                        lambda: client.chat.completions.create(**payload),
                        payload,
                    ),
                    RateLimitError,
                )
        except RateLimitError:
            raise LLMError(
                "OpenAI rate limit or quota not recovered within the retry budget"
            ) from None
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
