"""Bounded rate-limit retries: server delays, caps, and adapter behavior."""

import importlib
from types import SimpleNamespace

import httpx
import pytest

from repoagent.ai.openai_provider import llm_provider_from_settings
from repoagent.ai.provider import CompletionRequest
from repoagent.ai.rate_limit import RateLimitRetry, retry_after_seconds
from repoagent.config import Settings
from repoagent.domain.errors import LLMError


class Limited(Exception):
    def __init__(self, headers=None):
        super().__init__("429")
        self.response = SimpleNamespace(headers=headers or {})


def flaky(failures, error=Limited):
    state = {"calls": 0}

    def operation():
        state["calls"] += 1
        if state["calls"] <= failures:
            raise error({"retry-after": "7.02"}) if error is Limited else error()
        return "ok"

    return operation, state


def test_server_delay_is_honored_and_capped():
    waits = []
    operation, state = flaky(2)
    assert RateLimitRetry(3, 10, waits.append).call(operation, Limited) == "ok"
    assert state["calls"] == 3 and waits == [7.02, 7.02]
    assert retry_after_seconds(Limited({"retry-after-ms": "1500"})) == 1.5
    assert retry_after_seconds(Limited({"retry-after": "soon"})) is None


def test_backoff_without_headers_and_final_failure():
    waits = []

    def always():
        raise Limited()

    with pytest.raises(Limited):
        RateLimitRetry(2, 60, waits.append).call(always, Limited)
    assert waits == [2.0, 4.0]


def test_other_errors_are_never_retried():
    waits = []
    operation, state = flaky(1, error=ValueError)
    with pytest.raises(ValueError):
        RateLimitRetry(3, 60, waits.append).call(operation, Limited)
    assert state["calls"] == 1 and not waits


@pytest.mark.parametrize("vendor,class_name", [("groq", "Groq"), ("openai", "OpenAI")])
@pytest.mark.parametrize("failures", [1, 9])
def test_adapters_retry_rate_limits(monkeypatch, vendor, class_name, failures):
    module = importlib.import_module(vendor)
    monkeypatch.setattr("repoagent.ai.rate_limit.time.sleep", lambda _: None)
    calls = []
    response = httpx.Response(
        429,
        headers={"retry-after": "0"},
        request=httpx.Request("POST", "https://x"),
    )

    class Client:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=self)

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def create(self, **kwargs):
            calls.append(kwargs)
            if len(calls) <= failures:
                raise module.RateLimitError("secret", response=response, body=None)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="{}"))],
                usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1),
            )

    monkeypatch.setattr(module, class_name, Client)
    settings = Settings(llm_provider=vendor, llm_api_key="x", llm_rate_limit_retries=2)
    provider = llm_provider_from_settings(settings)
    request = CompletionRequest(prompt_name="p", system="s", user="u")
    if failures == 1:
        assert provider.complete(request).text == "{}" and len(calls) == 2
    else:
        with pytest.raises(LLMError, match="quota not recovered") as error:
            provider.complete(request)
        assert "secret" not in str(error.value) and len(calls) == 3


@pytest.mark.parametrize(
    "code, message",
    [("json_validate_failed", "violated the JSON schema"), ("other", "request failed")],
)
def test_groq_schema_rejection_is_an_output_error(monkeypatch, code, message):
    import groq

    response = httpx.Response(400, request=httpx.Request("POST", "https://x"))

    class Client:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=self)

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def create(self, **kwargs):
            body = {"error": {"code": code, "failed_generation": "secret output"}}
            raise groq.BadRequestError("bad", response=response, body=body)

    monkeypatch.setattr(groq, "Groq", Client)
    provider = llm_provider_from_settings(
        Settings(llm_provider="groq", llm_api_key="x")
    )
    with pytest.raises(LLMError, match=message) as error:
        provider.complete(CompletionRequest(prompt_name="p", system="s", user="u"))
    assert "secret" not in str(error.value)


def test_server_delay_beyond_cap_fails_fast():
    waits = []
    operation, state = flaky(3)
    with pytest.raises(Limited):
        RateLimitRetry(5, 5, waits.append).call(operation, Limited)
    assert state["calls"] == 1 and not waits
