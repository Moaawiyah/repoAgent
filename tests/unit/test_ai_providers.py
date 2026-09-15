"""Strict outputs, provider selection and secret handling."""

import pytest

from repoagent.ai.models import EvidenceAssessment, HypothesisSet, SearchPlan
from repoagent.ai.openai_provider import OpenAIChatProvider, llm_provider_from_settings
from repoagent.ai.provider import require_provider
from repoagent.ai.structured import structured_generate
from repoagent.config import Settings
from repoagent.domain.errors import LLMError, LLMOutputError
from tests.support.scripted import ScriptedLLMProvider


def test_scripted_provider_records_schema():
    provider = ScriptedLLMProvider([{"queries": ["query"]}])
    _, plan = structured_generate(provider, "search_plan", "system", "data", SearchPlan)
    assert plan.queries == ["query"]
    assert provider.requests[0].output_schema["properties"]["queries"]
    with pytest.raises(AssertionError):
        provider.complete(provider.requests[0])


@pytest.mark.parametrize(
    "payload", ['prose {"queries":["x"]}', "bad", '{"queries": []}']
)
def test_malformed_outputs_rejected(payload):
    with pytest.raises(LLMOutputError):
        structured_generate(
            ScriptedLLMProvider([payload]), "plan", "system", "data", SearchPlan
        )


@pytest.mark.parametrize(
    "payload",
    [
        '```json\n{"queries": ["x"]}\n```',
        '```\n{"queries": ["x"]}\n```',
        '  ```json\n{"queries": ["x"]}\n```  ',
    ],
)
def test_whole_response_code_fence_is_unwrapped(payload):
    """Some OpenAI-compatible models (e.g. GLM via z.ai) wrap otherwise valid
    JSON in a markdown fence despite an exact-JSON instruction."""
    _, plan = structured_generate(
        ScriptedLLMProvider([payload]), "plan", "system", "data", SearchPlan
    )
    assert plan.queries == ["x"]


def test_fenced_prose_is_still_rejected():
    """A fence does not license extracting JSON from surrounding prose."""
    payload = '```json\nHere you go: {"queries": ["x"]}\n```'
    with pytest.raises(LLMOutputError):
        structured_generate(
            ScriptedLLMProvider([payload]), "plan", "system", "data", SearchPlan
        )


def test_oversized_top_level_list_is_truncated_to_declared_cap():
    """Some serving stacks (tool-call grammars especially) enforce required
    fields, types, and enums but not array length, so a model can overshoot
    a bounded list by a couple of items."""
    payload = {"queries": ["a", "b", "c", "d", "e", "f", "g"]}  # cap is 6
    _, plan = structured_generate(
        ScriptedLLMProvider([payload]), "plan", "system", "data", SearchPlan
    )
    assert plan.queries == ["a", "b", "c", "d", "e", "f"]


def test_truncation_only_drops_trailing_items_within_declared_cap():
    payload = {
        "assessments": [],
        "unknowns": ["u1", "u2", "u3", "u4", "u5"],  # cap is 6: untouched
        "next_queries": ["q1", "q2", "q3", "q4", "q5"],  # cap is 4: truncated
    }
    _, result = structured_generate(
        ScriptedLLMProvider([payload]),
        "evidence_assessment",
        "system",
        "data",
        EvidenceAssessment,
    )
    assert result.unknowns == ["u1", "u2", "u3", "u4", "u5"]
    assert result.next_queries == ["q1", "q2", "q3", "q4"]


def test_truncation_never_reaches_into_nested_lists():
    """Only top-level fields are truncated; a nested list beyond its own cap
    still fails validation exactly as before, rather than being silently
    trimmed at a level the schema walk was never meant to reach."""
    draft = {"statement": "s", "affected_symbols": [f"s{i}" for i in range(9)]}
    payload = {"hypotheses": [draft]}
    with pytest.raises(LLMOutputError):
        structured_generate(
            ScriptedLLMProvider([payload]),
            "hypothesis_set",
            "system",
            "data",
            HypothesisSet,
        )


def test_output_and_prompt_limits():
    with pytest.raises(ValueError):
        SearchPlan(queries=["x" * 501])
    with pytest.raises(ValueError):
        HypothesisSet(hypotheses=[{"statement": "s", "confidence": 1.5}])
    with pytest.raises(LLMOutputError):
        structured_generate(
            ScriptedLLMProvider([]), "plan", "s", "x" * 60001, SearchPlan
        )


def test_provider_configuration():
    assert llm_provider_from_settings(Settings()) is None
    with pytest.raises(LLMError):
        require_provider(None, "investigation")
    with pytest.raises(LLMError):
        OpenAIChatProvider(Settings(llm_provider="openai"))
    secret = "private-test-key"
    settings = Settings(llm_provider="groq", llm_api_key=secret)
    assert llm_provider_from_settings(settings).name == "groq"
    assert secret not in repr(settings)
    assert secret not in settings.model_dump_json()
