"""Tool-call structured-output mode.

Some OpenAI-compatible endpoints treat ``response_format`` json_schema as a
soft hint but apply real grammar-constrained decoding to tool-call
arguments (observed with a GLM model served via z.ai). This mode targets
that behavior without weakening RepoAgent's own strict validation.
"""

from types import SimpleNamespace

import pytest

from repoagent.ai.chat import arguments, completion
from repoagent.ai.models import EvidenceAssessment
from repoagent.ai.openai_provider import llm_provider_from_settings
from repoagent.ai.provider import CompletionRequest
from repoagent.config import Settings


def test_tool_call_mode_builds_a_forced_function_and_parses_its_arguments():
    request = CompletionRequest(
        prompt_name="evidence_assessment",
        system="trusted",
        user="untrusted",
        output_schema=EvidenceAssessment.model_json_schema(),
    )
    payload = arguments(request, "glm-4.7-flashx", 2000, "tool_call")
    assert "response_format" not in payload
    [tool] = payload["tools"]
    assert tool["function"]["name"] == "evidence_assessment"
    assert tool["function"]["strict"] and tool["function"]["parameters"]
    assert payload["tool_choice"] == {
        "type": "function",
        "function": {"name": "evidence_assessment"},
    }
    call = SimpleNamespace(
        function=SimpleNamespace(arguments='{"enough_evidence": true}')
    )
    message = SimpleNamespace(content=None, tool_calls=[call])
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=message)],
        usage=SimpleNamespace(prompt_tokens=5, completion_tokens=3),
    )
    result = completion(response, "glm-4.7-flashx")
    assert result.text == '{"enough_evidence": true}'
    assert (result.usage.input_tokens, result.usage.output_tokens) == (5, 3)


def test_response_format_mode_ignores_absent_tool_calls():
    message = SimpleNamespace(content="{}", tool_calls=None)
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=message)],
        usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1),
    )
    assert completion(response, "m").text == "{}"


@pytest.mark.parametrize("vendor,class_name", [("groq", "Groq"), ("openai", "OpenAI")])
def test_tool_call_mode_end_to_end_through_the_official_sdk(
    monkeypatch, vendor, class_name
):
    import importlib

    module = importlib.import_module(vendor)
    calls = []

    class Client:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=self)

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def create(self, **kwargs):
            calls.append(kwargs)
            call = SimpleNamespace(
                function=SimpleNamespace(arguments='{"queries": ["x"]}')
            )
            message = SimpleNamespace(content=None, tool_calls=[call])
            return SimpleNamespace(
                choices=[SimpleNamespace(message=message)],
                usage=SimpleNamespace(prompt_tokens=10, completion_tokens=4),
            )

    monkeypatch.setattr(module, class_name, Client)
    settings = Settings(
        llm_provider=vendor, llm_api_key="x", llm_structured_output="tool_call"
    )
    request = CompletionRequest(
        prompt_name="search_plan",
        system="s",
        user="u",
        output_schema={"type": "object"},
    )
    result = llm_provider_from_settings(settings).complete(request)
    assert result.text == '{"queries": ["x"]}'
    assert "tools" in calls[0] and "response_format" not in calls[0]
    assert calls[0]["tool_choice"]["function"]["name"] == "search_plan"
