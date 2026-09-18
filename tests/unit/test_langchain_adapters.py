"""LangChain adapters: chat provider, retriever/tool and embeddings bridges."""

import json

import pytest
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from repoagent import RepoAgent, Settings
from repoagent.ai.audit_models import VerifierOutput
from repoagent.ai.langchain_chat import LangChainChatProvider
from repoagent.ai.provider import CompletionRequest
from repoagent.ai.structured import structured_generate
from repoagent.domain.errors import LLMError
from repoagent.retrieval.embeddings import HashingEmbeddingProvider
from repoagent.retrieval.langchain_adapters import (
    LangChainEmbeddingProvider,
    LangChainEmbeddings,
    search_code_tool,
)
from tests.support.api import AUTH

VERDICT = {"status": "verified", "reasoning": "Evidence confirms it.", "confidence": 1}


def chat(*texts, usage=None):
    messages = [AIMessage(content=t, usage_metadata=usage) for t in texts]
    return GenericFakeChatModel(messages=iter(messages))


def test_chat_provider_validates_through_repoagent_structured_output():
    usage = {"input_tokens": 12, "output_tokens": 5, "total_tokens": 17}
    provider = LangChainChatProvider(chat(json.dumps(VERDICT), usage=usage))
    result, output = structured_generate(
        provider, "audit_verification", "sys", "data", VerifierOutput
    )
    assert output.status == "verified"
    assert result.usage.input_tokens == 12 and result.usage.output_tokens == 5
    assert provider.name.startswith("langchain:")


def test_schema_is_inlined_as_instructions_for_plain_chat_models():
    seen = []

    class Recording(GenericFakeChatModel):
        def invoke(self, messages, *args, **kwargs):
            seen.extend(messages)
            return super().invoke(messages, *args, **kwargs)

    model = Recording(messages=iter([AIMessage(content="{}")]))
    request = CompletionRequest(
        prompt_name="p", system="sys", user="u", output_schema={"type": "object"}
    )
    LangChainChatProvider(model, name="custom").complete(request)
    assert "JSON schema" in seen[0].content and seen[1].content == "u"


def test_native_structured_output_mode():
    class Structured(GenericFakeChatModel):
        def with_structured_output(self, schema, include_raw=False, **kwargs):
            assert schema["additionalProperties"] is False
            usage = {"input_tokens": 3, "output_tokens": 2, "total_tokens": 5}
            raw = AIMessage(content="", usage_metadata=usage)
            return RunnableLambda(lambda _: {"raw": raw, "parsed": VERDICT})

    provider = LangChainChatProvider(Structured(messages=iter([])), structured=True)
    _, output = structured_generate(provider, "v", "sys", "data", VerifierOutput)
    assert output.confidence == 1


def test_vendor_failures_become_typed_llm_errors():
    class Broken(GenericFakeChatModel):
        def invoke(self, *args, **kwargs):
            raise ConnectionError("secret-bearing vendor text")

    provider = LangChainChatProvider(Broken(messages=iter([])))
    request = CompletionRequest(prompt_name="p", system="s", user="u")
    with pytest.raises(LLMError, match="ConnectionError") as caught:
        provider.complete(request)
    assert "secret" not in str(caught.value)


def test_retriever_and_tool_expose_existing_hybrid_graph_search(tmp_path):
    client = RepoAgent(settings=Settings(data_dir=tmp_path))
    client.index(AUTH)
    retriever = client.langchain_retriever(AUTH, top_k=3)
    documents = retriever.invoke("email lookup login")
    assert 0 < len(documents) <= 3
    metadata = documents[0].metadata
    assert metadata["rank"] == 1 and metadata["file_path"].endswith(".py")
    assert metadata["start_line"] <= metadata["end_line"]
    assert metadata["retrieval_source"] and isinstance(metadata["evidence"], list)
    tool = search_code_tool(retriever)
    assert tool.name == "search_code"
    assert "def" in tool.invoke({"query": "find user by email"})


def test_embedding_bridges_in_both_directions(tmp_path):
    native = HashingEmbeddingProvider(32)
    exposed = LangChainEmbeddings(native)
    assert exposed.embed_query("login") == native.embed(["login"])[0]
    assert len(exposed.embed_documents(["a", "b"])) == 2
    wrapped = LangChainEmbeddingProvider(
        DeterministicFakeEmbedding(size=16), name="fake-lc", dimension=16
    )
    assert wrapped.embed([]) == [] and len(wrapped.embed(["x"])[0]) == 16
    client = RepoAgent(settings=Settings(data_dir=tmp_path), embedding_provider=wrapped)
    summary = client.index(AUTH)
    assert summary.embedding_provider == "fake-lc" and summary.embedding_dimension == 16
