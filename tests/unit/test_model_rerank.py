"""Model-backed rerankers, NDCG, rerank pool, and retrieval benchmark arms."""

import json

import pytest

from repoagent.benchmark.experiment import BenchmarkMode, experiments
from repoagent.domain.errors import LLMError, LLMOutputError
from repoagent.evaluation.models import RetrievalCase, ndcg_at_k
from repoagent.retrieval.configured import build_reranker
from repoagent.retrieval.embeddings import HashingEmbeddingProvider
from repoagent.retrieval.model_rerank import LLMReranker, SemanticReranker
from repoagent.retrieval.models import RetrievalResult, RetrievalSource
from repoagent.retrieval.rerank import KeywordOverlapReranker
from tests.support.scripted import ScriptedLLMProvider
from tests.unit.test_retrieval_models import make_chunk


def candidates(*sources):
    return [
        RetrievalResult(
            rank=rank,
            score=1.0,
            source=RetrievalSource.HYBRID,
            chunk=make_chunk(source).model_copy(
                update={"qualified_name": f"m.f{rank}", "file_path": f"f{rank}.py"}
            ),
        )
        for rank, source in enumerate(sources, start=1)
    ]


def names(results):
    return [r.chunk.qualified_name for r in results]


def test_semantic_reranker_promotes_similar_code_but_keeps_rank_prior():
    pool = candidates("render html page", "parse email address", "open socket")
    reranked = SemanticReranker(HashingEmbeddingProvider(64)).rerank(
        "email address parsing", pool, top_k=2
    )
    assert names(reranked) == ["m.f2", "m.f1"]
    assert [r.rank for r in reranked] == [1, 2]
    assert SemanticReranker(HashingEmbeddingProvider()).rerank("q", [], 3) == []


def test_llm_reranker_orders_by_model_and_keeps_omitted_candidates():
    provider = ScriptedLLMProvider([{"ranked_ids": ["c3", "c9", "c3", "c1"]}])
    reranker = LLMReranker(provider, snippet_chars=5)
    reranked = reranker.rerank("issue", candidates("aaaaaaaa", "b", "c"), top_k=3)
    assert names(reranked) == ["m.f3", "m.f1", "m.f2"]
    sent = json.loads(provider.requests[0].user)
    assert sent["candidates"][0] == {
        "id": "c1",
        "file": "f1.py",
        "symbol": "m.f1",
        "code": "aaaaa",
    }
    assert reranker.calls == 1
    single = candidates("only")
    assert names(reranker.rerank("q", single, 5)) == ["m.f1"]


def test_llm_reranker_rejects_invalid_output():
    with pytest.raises(LLMOutputError):
        LLMReranker(ScriptedLLMProvider(["nope"])).rerank("q", candidates("a", "b"), 2)


def test_build_reranker_by_name():
    embedding = HashingEmbeddingProvider()
    assert isinstance(build_reranker("keyword", embedding), KeywordOverlapReranker)
    assert isinstance(build_reranker("semantic", embedding), SemanticReranker)
    llm = build_reranker("llm", embedding, ScriptedLLMProvider([]))
    assert isinstance(llm, LLMReranker)
    with pytest.raises(LLMError):
        build_reranker("llm", embedding, None)
    with pytest.raises(ValueError):
        build_reranker("bogus", embedding)


def test_ndcg_rewards_early_distinct_hits():
    case = RetrievalCase(query="q", expected_files=["f1.py", "f3.py"])
    perfect = candidates("a", "b", "c")
    swapped = [perfect[0], perfect[2], perfect[1]]
    assert ndcg_at_k(case, swapped, 3) == pytest.approx(1.0)
    assert 0 < ndcg_at_k(case, perfect, 3) < 1.0
    assert ndcg_at_k(RetrievalCase(query="q"), perfect, 3) == 0.0


def test_retrieval_arms_carry_graph_policy_and_reranker():
    arms = experiments(
        BenchmarkMode.RETRIEVAL, ["full", "graph_seeds5_gated", "rerank_llm"], k=5
    )
    full, graph, rerank = arms
    assert full.graph_policy is None and full.reranker is None
    assert graph.graph_policy == "seeds5_gated"
    assert [s.value for s in graph.strategies] == ["hybrid_graph"]
    assert rerank.reranker == "llm" and rerank.rerank_candidates == 20
    with pytest.raises(ValueError):
        experiments(BenchmarkMode.RETRIEVAL, ["no_reviewer"])
