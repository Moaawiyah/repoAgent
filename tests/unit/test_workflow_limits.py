"""Deterministic workflow limits: LLM calls, tokens, deadline, verification."""

import pytest

from repoagent import Settings
from repoagent.ai.budget import BudgetedProvider, LLMBudgetExceeded
from repoagent.ai.provider import CompletionRequest, CompletionResult, CompletionUsage
from repoagent.application.audit_verification import verify_candidates
from repoagent.domain.audit import VerificationStatus
from repoagent.domain.limits import WorkflowLimits
from tests.support.audit import build_context
from tests.support.scripted import ScriptedLLMProvider

REQUEST = CompletionRequest(prompt_name="p", system="s", user="u")


class Metered:
    name = "metered"

    def __init__(self, tokens=10):
        self.calls, self.tokens = 0, tokens

    def complete(self, request):
        self.calls += 1
        usage = CompletionUsage(input_tokens=self.tokens, output_tokens=self.tokens)
        return CompletionResult(text="{}", usage=usage)


def test_call_limit_blocks_the_next_call_without_reaching_the_provider():
    inner = Metered()
    budget = BudgetedProvider(inner, max_calls=2)
    budget.complete(REQUEST)
    budget.complete(REQUEST)
    with pytest.raises(LLMBudgetExceeded, match="call limit"):
        budget.complete(REQUEST)
    assert inner.calls == 2 and budget.calls == 2 and budget.tokens == 40
    assert budget.name == "metered"


def test_token_budget_and_deadline():
    tokens = BudgetedProvider(Metered(tokens=600), max_calls=10, max_tokens=1000)
    tokens.complete(REQUEST)
    with pytest.raises(LLMBudgetExceeded, match="token budget"):
        tokens.complete(REQUEST)
    now = [0.0]
    timed = BudgetedProvider(
        Metered(), max_calls=10, timeout_seconds=5, clock=lambda: now[0]
    )
    timed.complete(REQUEST)
    now[0] = 6.0
    with pytest.raises(LLMBudgetExceeded, match="time limit"):
        timed.complete(REQUEST)


def test_limits_consolidate_settings():
    settings = Settings(
        repair_max_attempts=2,
        discovery_max_candidates=7,
        workflow_max_llm_calls=40,
        workflow_max_tokens=5000,
        workflow_task_timeout=120,
        execution_timeout=90,
    )
    limits = WorkflowLimits.from_settings(settings)
    assert limits.repair_attempts == 2 and limits.discovery_candidates == 7
    assert limits.llm_calls == 40 and limits.tokens == 5000
    assert limits.task_timeout_seconds == 120 and limits.sandbox_timeout_seconds == 90
    assert limits.investigation_iterations == settings.investigation_max_iterations


def test_exhausted_budget_leaves_candidates_uncertain_with_reason():
    context = build_context()
    from repoagent.audit.detectors import ast_detectors

    candidates = [c for d in ast_detectors() for c in d.detect(context)][:3]
    verdict = {"status": "verified", "reasoning": "ok", "confidence": 0.9}
    provider = BudgetedProvider(ScriptedLLMProvider([verdict] * 3), max_calls=1)
    results, metrics = verify_candidates(provider, candidates)
    assert [c.status for c in results] == [
        VerificationStatus.VERIFIED,
        VerificationStatus.UNCERTAIN,
        VerificationStatus.UNCERTAIN,
    ]
    assert "call limit" in results[1].verification.reasoning
    assert metrics.verified == 1 and metrics.uncertain == 2
    # Only the one candidate that actually reached the provider is counted;
    # the two short-circuited by the budget must not inflate the call count.
    assert metrics.verification_llm_calls == 1
