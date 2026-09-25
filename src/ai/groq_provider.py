"""Groq structured outputs using the official Groq Python SDK."""

from repoagent.ai.chat import arguments, completion
from repoagent.ai.provider import CompletionRequest, CompletionResult
from repoagent.ai.rate_limit import RateLimitRetry
from repoagent.ai.throttle import shared_limiter, throttled_call
from repoagent.config import Settings
from repoagent.domain.errors import LLMError, LLMOutputError


class GroqProvider:
    name = "groq"

    def __init__(self, settings: Settings) -> None:
        if not settings.llm_api_key:
            raise LLMError("Groq requires REPOAGENT_LLM_API_KEY")
        self._settings = settings
        self._limiter = shared_limiter(
            f"groq:{settings.llm_model}",
            settings.llm_tokens_per_minute,
            settings.llm_requests_per_minute,
        )

    def complete(self, request: CompletionRequest) -> CompletionResult:
        from groq import APIError, APIStatusError, Groq, RateLimitError

        settings = self._settings
        try:
            with Groq(
                api_key=_secret(settings),
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
                "Groq rate limit or quota not recovered within the retry budget"
            ) from None
        except APIStatusError as error:
            if _schema_rejected(error):
                raise LLMOutputError(
                    "Groq rejected model output that violated the JSON schema"
                ) from None
            raise LLMError(
                "Groq request failed; check configuration and free-tier rate limits"
            ) from None
        except APIError:
            raise LLMError(
                "Groq request failed; check configuration and free-tier rate limits"
            ) from None
        return completion(response, settings.llm_model)


def _schema_rejected(error: Exception) -> bool:
    """Groq returns 400 ``json_validate_failed`` for schema-violating output."""
    body = getattr(error, "body", None)
    detail = body.get("error", {}) if isinstance(body, dict) else {}
    return isinstance(detail, dict) and detail.get("code") == "json_validate_failed"


def _secret(settings: Settings) -> str:
    key = settings.llm_api_key
    if key is None:
        raise LLMError("Groq provider requires REPOAGENT_LLM_API_KEY")
    return key.get_secret_value()
