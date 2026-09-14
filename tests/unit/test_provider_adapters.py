"""Official SDK boundaries: structured schemas, usage, and sanitized failures."""

from types import SimpleNamespace

import httpx
import pytest

from repoagent.ai.chat import strict_schema
from repoagent.ai.models import EvidenceAssessment
from repoagent.ai.openai_provider import llm_provider_from_settings
from repoagent.ai.provider import CompletionRequest
from repoagent.config import Settings
from repoagent.domain.errors import LLMError


@pytest.mark.parametrize("vendor,class_name", [("groq", "Groq"), ("openai", "OpenAI")])
@pytest.mark.parametrize("failed", [False, True])
def test_official_sdk_call(monkeypatch, vendor, class_name, failed):
    import importlib

    module = importlib.import_module(vendor)
    calls = []

    class Client:
        def __init__(self, **kwargs):
            calls.append(kwargs)
            self.chat = SimpleNamespace(completions=self)

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def create(self, **kwargs):
            calls.append(kwargs)
            if failed:
                raise module.APIError(
                    "secret provider payload",
                    request=httpx.Request("POST", "https://x"),
                    body=None,
                )
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="{}"))],
                usage=SimpleNamespace(prompt_tokens=100, completion_tokens=20),
            )

    monkeypatch.setattr(module, class_name, Client)
    provider = llm_provider_from_settings(
        Settings(llm_provider=vendor, llm_api_key="x")
    )
    request = CompletionRequest(
        prompt_name="evidence_assessment",
        system="trusted",
        user="untrusted",
        output_schema=EvidenceAssessment.model_json_schema(),
    )
    if failed:
        with pytest.raises(LLMError) as error:
            provider.complete(request)
        assert "secret" not in str(error.value)
    else:
        result = provider.complete(request)
        assert result.usage.input_tokens == 100
        assert result.usage.output_tokens == 20
    assert calls[0]["max_retries"] == 0
    assert calls[1]["response_format"]["json_schema"]["strict"]
    assert [m["role"] for m in calls[1]["messages"]] == ["system", "user"]
    assert "tools" not in calls[1]


def test_schema_is_strict_and_input_unchanged():
    original = EvidenceAssessment.model_json_schema()
    strict = strict_schema(original)
    assert set(strict["required"]) == set(strict["properties"])
    assert strict["additionalProperties"] is False
    assert "default" not in strict["properties"]["enough_evidence"]
    assert original["properties"]["enough_evidence"]["default"] is False


def test_groq_requires_key():
    with pytest.raises(LLMError, match="API_KEY"):
        llm_provider_from_settings(Settings(llm_provider="groq"))
