"""Common structured-output request/response mapping, independent of SDK classes."""

from copy import deepcopy
from typing import Any

from repoagent.ai.provider import CompletionRequest, CompletionResult, CompletionUsage


def strict_schema(schema: dict) -> dict:
    result = deepcopy(schema)

    def visit(value: object) -> None:
        if isinstance(value, dict):
            value.pop("default", None)
            if value.get("type") == "object":
                value["additionalProperties"] = False
                value["required"] = list(value.get("properties", {}))
            for nested in value.values():
                visit(nested)
        elif isinstance(value, list):
            for nested in value:
                visit(nested)

    visit(result)
    return result


def arguments(
    request: CompletionRequest,
    model: str,
    tokens: int,
    mode: str = "response_format",
) -> dict:
    """Build chat-completion arguments; ``mode`` selects how the schema is
    enforced.

    ``response_format`` (default) uses OpenAI/Groq-style constrained JSON
    output. ``tool_call`` instead forces a single function call whose
    arguments must match the schema; some OpenAI-compatible serving stacks
    (e.g. certain GLM deployments) apply real grammar-constrained decoding to
    tool-call arguments while treating ``response_format`` as a soft hint.
    """
    payload = {
        "model": model,
        "max_completion_tokens": tokens,
        "messages": [
            {"role": "system", "content": request.system},
            {"role": "user", "content": request.user},
        ],
    }
    schema = strict_schema(request.output_schema)
    if mode == "tool_call":
        payload["tools"] = [
            {
                "type": "function",
                "function": {
                    "name": request.prompt_name,
                    "strict": True,
                    "parameters": schema,
                },
            }
        ]
        payload["tool_choice"] = {
            "type": "function",
            "function": {"name": request.prompt_name},
        }
    else:
        payload["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": request.prompt_name,
                "strict": True,
                "schema": schema,
            },
        }
    return payload


def completion(response: Any, model: str) -> CompletionResult:
    """Read the model's answer from either a tool call or message content."""
    usage = getattr(response, "usage", None)
    message = response.choices[0].message
    calls = getattr(message, "tool_calls", None) or []
    text = calls[0].function.arguments if calls else (message.content or "")
    return CompletionResult(
        text=text,
        model=model,
        usage=CompletionUsage(
            input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(usage, "completion_tokens", 0) or 0,
        ),
    )
