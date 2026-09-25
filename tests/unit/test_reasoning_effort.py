"""``llm_reasoning_effort`` is forwarded only when configured."""

from types import SimpleNamespace

import openai
import pytest

from repoagent.ai.openai_provider import llm_provider_from_settings
from repoagent.ai.provider import CompletionRequest
from repoagent.config import Settings


@pytest.mark.parametrize("effort", [None, "none"])
def test_reasoning_effort_is_optional(monkeypatch, effort):
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
            message = SimpleNamespace(content="{}", tool_calls=None)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=message)], usage=None
            )

    monkeypatch.setattr(openai, "OpenAI", Client)
    settings = Settings(
        llm_provider="openai", llm_api_key="x", llm_reasoning_effort=effort
    )
    request = CompletionRequest(prompt_name="p", system="s", user="u")
    assert llm_provider_from_settings(settings).complete(request).text == "{}"
    assert calls[0].get("reasoning_effort") == effort
    assert ("reasoning_effort" in calls[0]) is (effort is not None)
