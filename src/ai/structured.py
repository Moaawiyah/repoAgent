"""Validate exact structured JSON; never salvage prose as a valid answer."""

from pydantic import BaseModel, ValidationError

from repoagent.ai.provider import CompletionRequest, CompletionResult, LLMProvider
from repoagent.domain.errors import LLMOutputError


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
    try:
        return result, output_model.model_validate_json(result.text)
    except ValidationError:
        raise LLMOutputError(f"Invalid structured output for {prompt_name}") from None
