"""Strict outputs, provider selection and secret handling."""

import pytest

from repoagent.ai.models import HypothesisSet, SearchPlan
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
