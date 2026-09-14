"""Common structured-output request/response mapping, independent of SDK classes."""

from copy import deepcopy

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


def arguments(request: CompletionRequest, model: str, tokens: int) -> dict:
    return {
        "model": model,
        "max_completion_tokens": tokens,
        "messages": [
            {"role": "system", "content": request.system},
            {"role": "user", "content": request.user},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": request.prompt_name,
                "strict": True,
                "schema": strict_schema(request.output_schema),
            },
        },
    }


def completion(response: object, model: str) -> CompletionResult:
    usage = getattr(response, "usage", None)
    return CompletionResult(
        text=response.choices[0].message.content or "",
        model=model,
        usage=CompletionUsage(
            input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(usage, "completion_tokens", 0) or 0,
        ),
    )
