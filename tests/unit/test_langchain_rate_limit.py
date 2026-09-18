"""LangChainChatProvider must go through the same rate-limit gatekeeper as
GroqProvider/OpenAIChatProvider (ai/throttle.SlidingWindowLimiter), not
bypass it."""

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from repoagent.ai.langchain_chat import LangChainChatProvider
from repoagent.ai.provider import CompletionRequest
from repoagent.ai.throttle import SlidingWindowLimiter

REQUEST = CompletionRequest(prompt_name="p", system="s", user="u")


def chat(*texts):
    return GenericFakeChatModel(messages=iter(AIMessage(content=t) for t in texts))


def test_provider_blocks_on_the_shared_sliding_window_limiter():
    now = [0.0]
    waited = []

    def sleep(seconds: float) -> None:
        waited.append(seconds)
        now[0] += seconds + 1  # simulate real time passing past the window

    limiter = SlidingWindowLimiter(
        tokens_per_minute=None,
        requests_per_minute=1,
        clock=lambda: now[0],
        sleep=sleep,
    )
    provider = LangChainChatProvider(chat("{}", "{}"), limiter=limiter)
    first = provider.complete(REQUEST)
    second = provider.complete(REQUEST)
    assert waited == [60.0]  # the second call had to wait a full window
    assert first.text == second.text == "{}"


def test_no_rate_limit_configured_means_no_throttling():
    provider = LangChainChatProvider(chat("{}", "{}"))
    assert provider._limiter is None
    provider.complete(REQUEST)
    provider.complete(REQUEST)  # both return immediately, no waiting


def test_tokens_per_minute_creates_a_shared_named_limiter():
    provider = LangChainChatProvider(
        chat("{}"), name="test-model", tokens_per_minute=1000, requests_per_minute=10
    )
    assert isinstance(provider._limiter, SlidingWindowLimiter)
    again = LangChainChatProvider(
        chat("{}"), name="test-model", tokens_per_minute=1000, requests_per_minute=10
    )
    # Same key/budget across provider instances shares one limiter (quotas
    # are per account/model, not per client object), mirroring Groq/OpenAI.
    assert provider._limiter is again._limiter
