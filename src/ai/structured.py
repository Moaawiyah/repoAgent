"""Validate exact structured JSON; never salvage prose as a valid answer."""

import json
import re

from pydantic import BaseModel, ValidationError

from repoagent.ai.provider import CompletionRequest, CompletionResult, LLMProvider
from repoagent.domain.errors import LLMOutputError

_CODE_FENCE = re.compile(r"^```(?:json)?\s*\n(.*)\n```$", re.DOTALL)


def _unwrap_code_fence(text: str) -> str:
    """Strip one whole-response ```json fence some providers add despite an
    exact-JSON instruction. Only a match spanning the entire trimmed response
    is unwrapped; JSON embedded in surrounding prose is never extracted."""
    match = _CODE_FENCE.match(text.strip())
    return match.group(1).strip() if match else text


def _truncate_oversized_lists(text: str, schema: dict) -> str:
    """Drop trailing items beyond a field's own declared ``maxItems``.

    Some structured-output serving stacks (tool-call/function-calling
    grammars in particular) enforce required fields, types, and enums but
    not array length, so a model can overshoot a bounded list by a couple of
    items. This only truncates a top-level array to the schema's own
    declared cap; it never reorders, merges, invents, or reinterprets
    content, and never touches a field without an explicit ``maxItems`` or a
    nested (non-top-level) array.
    """
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text
    if not isinstance(data, dict):
        return text
    changed = False
    for key, spec in schema.get("properties", {}).items():
        limit, value = spec.get("maxItems"), data.get(key)
        if isinstance(limit, int) and isinstance(value, list) and len(value) > limit:
            data[key], changed = value[:limit], True
    return json.dumps(data) if changed else text


def structured_generate[Model: BaseModel](
    provider: LLMProvider,
    prompt_name: str,
    system: str,
    user: str,
    output_model: type[Model],
) -> tuple[CompletionResult, Model]:
    try:
        request = CompletionRequest(
            prompt_name=prompt_name,
            system=system,
            user=user,
            output_schema=output_model.model_json_schema(),
        )
    except ValidationError:
        raise LLMOutputError("Prompt exceeds the configured safety bound") from None
    result = provider.complete(request)
    text = _unwrap_code_fence(result.text)
    text = _truncate_oversized_lists(text, request.output_schema)
    try:
        return result, output_model.model_validate_json(text)
    except ValidationError:
        raise LLMOutputError(f"Invalid structured output for {prompt_name}") from None
