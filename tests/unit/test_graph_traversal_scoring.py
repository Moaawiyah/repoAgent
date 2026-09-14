"""Bounded traversal and deterministic graph scoring."""

from repoagent.graph.models import EdgeType, GraphEdge, GraphNode, NodeType
from repoagent.graph.scoring import ScoringConfig
from repoagent.graph.store import InMemoryGraphStore
from repoagent.graph.traversal import TraversalConfig, traverse


def node(node_id, node_type=NodeType.FUNCTION):
    return GraphNode(
        node_id=node_id,
        node_type=node_type,
        name=node_id.split(".")[-1],
        file_path=f"{node_id}.py",
        start_line=1,
        end_line=1,
        module="mod",
    )


def build_chain():
    """a -> b -> c -> a (cycle), plus a -> d (import)."""
    store = InMemoryGraphStore()
    for node_id in ("a", "b", "c", "d"):
        store.add_node(node(node_id))
    store.add_edge(GraphEdge(source="a", target="b", edge_type=EdgeType.CALLS))
    store.add_edge(GraphEdge(source="b", target="c", edge_type=EdgeType.CALLS))
    store.add_edge(GraphEdge(source="c", target="a", edge_type=EdgeType.CALLS))
    store.add_edge(GraphEdge(source="a", target="d", edge_type=EdgeType.IMPORTS))
    return store


def test_traversal_respects_max_depth():
    found = traverse(build_chain(), ["a"], TraversalConfig(max_depth=1))
    assert [item.node_id for item in found] == ["b", "d"]
    deeper = traverse(build_chain(), ["a"], TraversalConfig(max_depth=2))
    assert [item.node_id for item in deeper] == ["b", "d", "c"]


def test_traversal_survives_cycles_and_is_bounded():
    config = TraversalConfig(max_depth=10, max_nodes=50)
    found = traverse(build_chain(), ["a"], config)
    assert len(found) == 3
    assert [item.node_id for item in found] == ["b", "d", "c"]


def test_traversal_caps_node_count():
    found = traverse(build_chain(), ["a"], TraversalConfig(max_nodes=1))
    assert [item.node_id for item in found] == ["b"]


def test_traversal_filters_edge_types():
    config = TraversalConfig(
        max_depth=2, allowed_edge_types=frozenset({EdgeType.CALLS})
    )
    found = traverse(build_chain(), ["a"], config)
    assert [item.node_id for item in found] == ["b", "c"]


def test_traversal_records_distances_and_paths():
    found = traverse(build_chain(), ["a"], TraversalConfig(max_depth=2))
    by_id = {item.node_id: item for item in found}
    assert by_id["b"].distance == 1
    assert by_id["c"].distance == 2
    path = by_id["c"].path
    assert [(hop.source, hop.target) for hop in path] == [("a", "b"), ("b", "c")]


def test_scoring_prefers_closer_and_stronger_relations():
    config = ScoringConfig()
    close = config.score(1, 1, [EdgeType.CALLS])
    far = config.score(1, 3, [EdgeType.CALLS])
    weak = config.score(1, 1, [EdgeType.IMPORTS])
    assert close > far
    assert close > weak
    strong_seed = config.score(1, 1, [EdgeType.CALLS])
    weak_seed = config.score(5, 1, [EdgeType.CALLS])
    assert strong_seed > weak_seed


def test_scoring_is_deterministic_and_rejects_invalid():
    config = ScoringConfig()
    assert config.score(2, 1, [EdgeType.CALLS]) == config.score(2, 1, [EdgeType.CALLS])
    assert config.score(0, 1, [EdgeType.CALLS]) == 0.0
    assert config.score(1, 0, [EdgeType.CALLS]) == 0.0
