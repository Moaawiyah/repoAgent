"""Proactive sliding-window limiter and its provider integrations."""

from types import SimpleNamespace

from repoagent.ai.openai_provider import llm_provider_from_settings
from repoagent.ai.provider import CompletionRequest
from repoagent.ai.throttle import SlidingWindowLimiter, estimate_tokens, shared_limiter
from repoagent.config import Settings


class FakeClock:
    def __init__(self):
        self.now, self.sleeps = 0.0, []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(round(seconds, 2))
        self.now += seconds


def limiter(tpm=None, rpm=None):
    clock = FakeClock()
    return SlidingWindowLimiter(tpm, rpm, clock=clock, sleep=clock.sleep), clock


def fake_sdk_client(created: list):
    """Records ``create`` calls and reports usage, standing in for any
    vendor SDK's chat-completions client (Groq, OpenAI, OpenAI-compatible)."""

    class Client:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=self)

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def create(self, **kwargs):
            created.append(kwargs)
            usage = SimpleNamespace(
                prompt_tokens=40, completion_tokens=10, total_tokens=50
            )
            message = SimpleNamespace(content="{}")
            return SimpleNamespace(
                choices=[SimpleNamespace(message=message)], usage=usage
            )

    return Client


def test_token_budget_waits_for_oldest_reservation_to_expire():
    bucket, clock = limiter(tpm=8000)
    bucket.acquire(5000)
    clock.now = 10
    bucket.acquire(2500)
    clock.now = 20
    third = bucket.acquire(3000)
    assert clock.sleeps == [40.0] and third.at == 60.0


def test_settled_usage_frees_budget_and_request_cap_applies():
    bucket, clock = limiter(tpm=8000, rpm=2)
    first = bucket.acquire(6000)
    bucket.settle(first, 1200)
    bucket.settle(first, 0)
    bucket.acquire(6000)
    assert not clock.sleeps and first.tokens == 1200
    bucket.acquire(10)
    assert clock.sleeps == [60.0]


def test_oversized_request_runs_alone_on_empty_window():
    bucket, clock = limiter(tpm=1000)
    bucket.acquire(5000)
    assert not clock.sleeps
    bucket.acquire(1)
    assert clock.sleeps == [60.0]


def test_estimate_and_registry():
    assert estimate_tokens(3000, 2000) == 3001
    assert shared_limiter("k", None, None) is None
    assert shared_limiter("k", 8000, 30) is shared_limiter("k", 8000, 30)
    assert shared_limiter("k", 8000, 30) is not shared_limiter("other", 8000, 30)


def test_groq_provider_reserves_and_settles(monkeypatch):
    import groq

    created = []
    monkeypatch.setattr(groq, "Groq", fake_sdk_client(created))
    settings = Settings(
        llm_provider="groq",
        llm_api_key="x",
        llm_model="throttle-test-model",
        llm_tokens_per_minute=8000,
        llm_requests_per_minute=30,
    )
    request = CompletionRequest(prompt_name="p", system="s", user="u" * 300)
    llm_provider_from_settings(settings).complete(request)
    shared = shared_limiter("groq:throttle-test-model", 8000, 30)
    assert created and [e.tokens for e in shared._events] == [50]
    unthrottled = settings.model_copy(
        update={"llm_tokens_per_minute": None, "llm_requests_per_minute": None}
    )
    llm_provider_from_settings(unthrottled).complete(request)
    assert len(created) == 2


def test_openai_compatible_provider_reserves_and_settles_per_base_url(monkeypatch):
    """Covers OpenAI-compatible endpoints selected via llm_base_url (e.g. z.ai)."""
    import openai

    created = []
    monkeypatch.setattr(openai, "OpenAI", fake_sdk_client(created))
    settings = Settings(
        llm_provider="openai",
        llm_api_key="x",
        llm_model="glm-4.7-flashx",
        llm_base_url="https://api.z.ai/api/paas/v4/",
        llm_tokens_per_minute=8000,
        llm_requests_per_minute=30,
    )
    request = CompletionRequest(prompt_name="p", system="s", user="u" * 300)
    llm_provider_from_settings(settings).complete(request)
    key = "openai:https://api.z.ai/api/paas/v4/:glm-4.7-flashx"
    shared = shared_limiter(key, 8000, 30)
    assert created and [e.tokens for e in shared._events] == [50]
    other_host = settings.model_copy(
        update={"llm_base_url": "https://api.openai.com/v1"}
    )
    llm_provider_from_settings(other_host).complete(request)
    assert shared is not shared_limiter(
        "openai:https://api.openai.com/v1:glm-4.7-flashx", 8000, 30
    )
