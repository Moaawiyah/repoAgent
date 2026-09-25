"""Selective graph expansion: policies, uncertain edges, gating, weighted RRF."""

import pytest

from repoagent.config import Settings
from repoagent.graph.models import EdgeType, GraphEdge, GraphNode, NodeType
from repoagent.graph.policy import (
    DEFAULT_GRAPH_POLICY,
    GRAPH_POLICIES,
    GraphPolicy,
    graph_policy,
)
from repoagent.graph.scoring import ScoringConfig
from repoagent.graph.store import InMemoryGraphStore
from repoagent.graph.traversal import TraversalConfig, traverse
from repoagent.retrieval.configured import graph_policy_from_settings
from repoagent.retrieval.fusion import rrf_fuse
from repoagent.retrieval.graph import HybridGraphRetriever
from repoagent.retrieval.models import Evidence, RetrievalResult, RetrievalSource
from tests.unit.test_retrieval_models import make_chunk


def store_with(*edges):
    store = InMemoryGraphStore()
    for name in "abcd":
        store.add_node(
            GraphNode(
                node_id=name,
                node_type=NodeType.FUNCTION,
                name=name,
                file_path="m.py",
                start_line=1,
                end_line=2,
                module="m",
            )
        )
    for source, target, resolved in edges:
        store.add_edge(
            GraphEdge(
                source=source,
                target=target,
                edge_type=EdgeType.CALLS,
                resolved=resolved,
            )
        )
    return store


def test_unresolved_edges_can_be_excluded_from_traversal():
    store = store_with(("a", "b", True), ("a", "c", False))
    everything = {v.node_id for v in traverse(store, ["a"])}
    resolved = {
        v.node_id
        for v in traverse(store, ["a"], TraversalConfig(include_unresolved=False))
    }
    assert everything == {"b", "c"} and resolved == {"b"}
    none_allowed = TraversalConfig(allowed_edge_types=frozenset())
    assert traverse(store, ["a"], none_allowed) == []


def test_unresolved_hops_are_down_weighted():
    scoring = ScoringConfig(unresolved_weight=0.3)
    certain = scoring.score(1, 1, [EdgeType.CALLS])
    uncertain = scoring.score(1, 1, [EdgeType.CALLS], unresolved_hops=1)
    assert uncertain == pytest.approx(certain * 0.3)


def test_policy_derives_traversal_and_scoring():
    policy = graph_policy("calls_inherits", unresolved_weight=0.0, max_depth=1)
    traversal = policy.traversal()
    assert traversal.allowed_edge_types == {EdgeType.CALLS, EdgeType.INHERITS}
    assert not traversal.include_unresolved and traversal.max_depth == 1
    assert policy.scoring().unresolved_weight == 0.0
    tuned = graph_policy("seeds5_gated", edge_weights={"imports": 0.0})
    assert EdgeType.IMPORTS not in tuned.traversal().allowed_edge_types
    assert GRAPH_POLICIES["legacy"] == GraphPolicy()
    assert Settings().graph_policy == DEFAULT_GRAPH_POLICY == "calls_inherits"
    with pytest.raises(ValueError):
        graph_policy("bogus")


def test_settings_select_and_validate_graph_policy():
    settings = Settings(graph_policy="seeds5_gated", graph_edge_weights={"calls": 0.4})
    policy = graph_policy_from_settings(settings)
    assert policy.name == "seeds5_gated" and policy.edge_weights[EdgeType.CALLS] == 0.4
    assert graph_policy_from_settings(settings, "legacy").name == "legacy"
    with pytest.raises(ValueError):
        Settings(graph_policy="bogus")
    with pytest.raises(ValueError):
        Settings(graph_edge_weights={"teleports": 1.0})
    with pytest.raises(ValueError):
        Settings(graph_edge_weights={"calls": 2.0})


def result(name, rank, *ranks):
    evidence = [Evidence(kind=f"r{i}", rank=r) for i, r in enumerate(ranks)]
    return RetrievalResult(
        rank=rank,
        score=1.0,
        source=RetrievalSource.HYBRID,
        chunk=make_chunk(name).model_copy(update={"qualified_name": name}),
        evidence=evidence,
    )


def test_weighted_rrf_scales_each_list():
    first, second = [result("a", 1)], [result("b", 1)]
    fused = rrf_fuse([first, second], weights=[1.0, 0.5])
    assert [r.chunk.qualified_name for r in fused] == ["a", "b"]
    assert fused[1].score == pytest.approx(fused[0].score / 2)


class Seeds:
    def __init__(self, seeds):
        self.seeds = seeds

    def search(self, query, top_k):
        return self.seeds[:top_k]


class RecordingExpander:
    def __init__(self):
        self.expanded = []

    def expand(self, seeds, top_k):
        self.expanded.append([s.chunk.qualified_name for s in seeds])
        return [result("graph_only", 1)]


def graph_weight(seeds, policy):
    expander = RecordingExpander()
    found = HybridGraphRetriever(Seeds(seeds), expander, policy=policy)
    results = found.search("q", 5)
    return expander.expanded[0], {r.chunk.qualified_name: r.score for r in results}


def test_confident_seeds_down_weight_graph_and_seed_cap_applies():
    policy = GraphPolicy(max_seeds=1, confident_weight=0.5)
    agreed = [result("top", 1, 1, 1), result("next", 2, 2, 3)]
    expanded, scores = graph_weight(agreed, policy)
    assert expanded == ["top"]
    assert scores["graph_only"] == pytest.approx(0.5 / 61)
    disagreed = [result("top", 1, 1, 4), result("next", 2, 2, 1)]
    _, scores = graph_weight(disagreed, policy)
    assert scores["graph_only"] == pytest.approx(1 / 61)
