"""Provider calls, failure outcomes, usage and observable trace entries."""

import logging

from pydantic import BaseModel

from repoagent.agent.prompts import SYSTEM_GUARD, context
from repoagent.agent.state import InvestigationState
from repoagent.ai.provider import LLMProvider
from repoagent.ai.structured import structured_generate
from repoagent.domain.investigation import InvestigationTraceEntry, LLMUsage


def generate[Output: BaseModel](
    state: InvestigationState, provider: LLMProvider, task: str, model: type[Output]
) -> tuple[Output, LLMUsage]:
    user = context(state, task)
    result, output = structured_generate(provider, task, SYSTEM_GUARD, user, model)
    previous = state.usage
    return output, LLMUsage(
        model=result.model,
        llm_calls=previous.llm_calls + 1,
        input_tokens=previous.input_tokens + result.usage.input_tokens,
        output_tokens=previous.output_tokens + result.usage.output_tokens,
        estimated_context_tokens=previous.estimated_context_tokens
        + (len(user) + 3) // 4,
    )


def trace(
    state: InvestigationState,
    action: str,
    decision: str,
    rationale: str = "",
    query: str | None = None,
    symbols: list[str] | None = None,
) -> list[InvestigationTraceEntry]:
    logging.getLogger("repoagent").info(
        action, extra={"event": action, "task_id": state.task_id}
    )
    return [
        *state.trace,
        InvestigationTraceEntry(
            iteration=state.current_iteration,
            action=action,
            query=query,
            found_symbols=symbols or [],
            decision=decision,
            rationale=rationale[:500],
        ),
    ]


GENERIC_FAILURE = "Provider call or output failed"


def failure(state: InvestigationState, action: str, reason: str = "") -> dict:
    """``reason`` is a RepoAgent-authored LLMError message, never provider text."""
    message = f"{GENERIC_FAILURE}: {reason}"[:500] if reason else GENERIC_FAILURE
    return {
        "termination": "provider_error",
        "error": message,
        "usage": state.usage.model_copy(
            update={"llm_calls": state.usage.llm_calls + 1}
        ),
        "trace": trace(state, action, "stop", message),
    }


def fresh_queries(state: InvestigationState, queries: list[str]) -> list[str]:
    seen = {q.casefold().strip() for q in state.executed_queries}
    result = []
    for query in queries:
        clean = query.strip()
        if clean and clean.casefold() not in seen:
            result.append(clean)
            seen.add(clean.casefold())
    return result[: max(0, state.limits.max_queries - len(state.executed_queries))]
