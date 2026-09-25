"""Adapter: any LangChain chat model as a RepoAgent ``LLMProvider``.

RepoAgent code keeps depending only on the provider protocol; LangChain
types stay inside this adapter. Structured output uses the model's native
``with_structured_output`` (tool/JSON-schema calling) when requested, and
the result is still validated by RepoAgent's own ``structured_generate``.

Rate limiting reuses the same proactive ``SlidingWindowLimiter`` gatekeeper
that ``GroqProvider``/``OpenAIChatProvider`` apply (``ai/throttle.py``), so a
LangChain-backed provider configured for a rate-limited vendor blocks under
the same shared, deterministic per-minute budget rather than bypassing it.
Reactive 429 backoff is vendor-specific and stays with those two adapters.
"""

import json
from typing import Any, cast

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from repoagent.ai.chat import strict_schema
from repoagent.ai.provider import CompletionRequest, CompletionResult, CompletionUsage
from repoagent.ai.throttle import SlidingWindowLimiter, estimate_tokens, shared_limiter
from repoagent.domain.errors import LLMError

SCHEMA_INSTRUCTION = "\n\nReturn only one JSON object matching this JSON schema:\n"


def messages_for(request: CompletionRequest, *, inline_schema: bool) -> list:
    """System/user messages; untrusted data stays in the user message."""
    system = request.system
    if inline_schema and request.output_schema:
        system += SCHEMA_INSTRUCTION + json.dumps(request.output_schema)
    return [SystemMessage(content=system), HumanMessage(content=request.user)]


def _text(message: BaseMessage | None) -> str:
    if message is None:
        return ""
    content = message.content
    if isinstance(content, str):
        return content
    return "".join(
        part.get("text", "") if isinstance(part, dict) else str(part)
        for part in content
    )


def _usage(message: BaseMessage | None) -> CompletionUsage:
    metadata = getattr(message, "usage_metadata", None) or {}
    return CompletionUsage(
        input_tokens=metadata.get("input_tokens", 0),
        output_tokens=metadata.get("output_tokens", 0),
    )


class LangChainChatProvider:
    def __init__(
        self,
        model: BaseChatModel,
        *,
        name: str | None = None,
        structured: bool = False,
        tokens_per_minute: int | None = None,
        requests_per_minute: int | None = None,
        max_output_tokens: int = 2000,
        limiter: SlidingWindowLimiter | None = None,
    ) -> None:
        self._model, self._structured = model, structured
        self.name = name or f"langchain:{model._llm_type}"
        self._max_output_tokens = max_output_tokens
        # ``limiter`` (explicit injection, e.g. for tests) takes precedence;
        # otherwise a limiter is created only when a budget was requested,
        # matching the Groq/OpenAI adapters' opt-in throttling.
        self._limiter = limiter or shared_limiter(
            f"langchain-rate:{self.name}", tokens_per_minute, requests_per_minute
        )

    def complete(self, request: CompletionRequest) -> CompletionResult:
        native = self._structured and bool(request.output_schema)
        messages = messages_for(request, inline_schema=not native)
        reservation = None
        if self._limiter is not None:
            chars = len(request.system) + len(request.user)
            reservation = self._limiter.acquire(
                estimate_tokens(chars, self._max_output_tokens)
            )
        try:
            if native:
                schema = strict_schema(request.output_schema)
                schema.setdefault("title", request.prompt_name)
                runnable = self._model.with_structured_output(schema, include_raw=True)
                output = cast(dict[str, Any], runnable.invoke(messages))
                raw, parsed = output.get("raw"), output.get("parsed")
                text = json.dumps(parsed) if parsed is not None else _text(raw)
            else:
                raw = self._model.invoke(messages)
                text = _text(raw)
        except LLMError:
            raise
        except Exception as error:  # noqa: BLE001 - vendor boundary, typed below
            raise LLMError(
                f"LangChain model call failed ({type(error).__name__})"
            ) from None
        model = getattr(raw, "response_metadata", {}).get("model_name", self.name)
        usage = _usage(raw if isinstance(raw, AIMessage) else None)
        if reservation is not None and self._limiter is not None:
            self._limiter.settle(reservation, usage.input_tokens + usage.output_tokens)
        return CompletionResult(text=text, model=str(model), usage=usage)
