"""Graph model and in-memory store behavior."""

import pytest
from pydantic import ValidationError

from repoagent.graph.models import (
    EdgeType,
    GraphEdge,
    GraphNode,
    GraphSnapshot,
    NodeType,
)
from repoagent.graph.store import InMemoryGraphStore, store_from_snapshot


def node(node_id, node_type=NodeType.FUNCTION, name=None, parent=None):
    return GraphNode(
        node_id=node_id,
        node_type=node_type,
        name=name or node_id.split(".")[-1],
        file_path=f"{node_id.replace('.', '/')}.py",
        start_line=1,
        end_line=2,
        parent=parent,
        module=node_id.rsplit(".", 1)[0],
    )


def edge(source, target, edge_type=EdgeType.CALLS, resolved=True):
    return GraphEdge(
        source=source, target=target, edge_type=edge_type, resolved=resolved
    )


def build_store():
    store = InMemoryGraphStore()
    store.add_node(node("mod.Class", NodeType.CLASS))
    store.add_node(node("mod.Class.method", NodeType.METHOD, parent="mod.Class"))
    store.add_node(node("mod.helper"))
    store.add_edge(edge("mod.Class", "mod.Class.method", EdgeType.CONTAINS))
    store.add_edge(edge("mod.Class.method", "mod.helper"))
    return store


def test_node_identity_is_deterministic_qualified_name():
    first = node("mod.func")
    second = node("mod.func")
    assert first.node_id == second.node_id == "mod.func"
    with pytest.raises(ValidationError):
        GraphNode(
            node_id="mod.func",
            node_type="galaxy",
            name="func",
            file_path="f.py",
            start_line=1,
            end_line=1,
            module="mod",
        )


def test_store_lookups_and_indexes():
    store = build_store()
    assert store.has_node("mod.helper")
    assert store.get_node("missing") is None
    methods = store.nodes_by_type(NodeType.METHOD)
    assert [item.node_id for item in methods] == ["mod.Class.method"]
    assert store.nodes_by_simple_name("helper") == ["mod.helper"]


def test_duplicate_edges_collapse():
    store = build_store()
    store.add_edge(edge("mod.Class.method", "mod.helper"))
    assert len(store.outgoing("mod.Class.method")) == 1


def test_neighbors_follow_only_existing_targets():
    store = build_store()
    store.add_edge(edge("mod.helper", "external.thing"))
    neighbors = store.neighbors("mod.helper")
    assert neighbors == []
    assert len(store.outgoing("mod.helper")) == 1


def test_incoming_and_edge_type_filters():
    store = build_store()
    store.add_edge(edge("mod.other", "mod.helper", resolved=False))
    incoming = store.incoming("mod.helper")
    assert [(e.source, e.resolved) for e in incoming] == [
        ("mod.Class.method", True),
        ("mod.other", False),
    ]
    calls = store.incoming("mod.Class.method", {EdgeType.CALLS})
    assert calls == []


def test_snapshot_roundtrip_preserves_sorted_content():
    store = build_store()
    snapshot = store.to_snapshot()
    assert [n.node_id for n in snapshot.nodes] == sorted(
        n.node_id for n in snapshot.nodes
    )
    rebuilt = store_from_snapshot(snapshot)
    assert rebuilt.to_snapshot() == snapshot


def test_snapshot_model_is_json_serializable():
    snapshot = build_store().to_snapshot()
    data = snapshot.model_dump(mode="json")
    assert data["nodes"][0]["node_type"] in {"module", "class", "function", "method"}
    assert GraphSnapshot.model_validate(data) == snapshot
