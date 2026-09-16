"""Duplicate qualified names (property overloads, conditional defs) must
not silently collapse into one graph node."""

from repoagent.analysis.analyzer import RepositoryAnalyzer
from repoagent.domain.repository import RepositorySpec
from repoagent.graph.builder import RepositoryGraphBuilder
from repoagent.graph.models import EdgeType

SOURCE = """
class Container:
    if True:
        def helper(self):
            return call_a()
    else:
        def helper(self):
            return call_b()


def call_a():
    return 1


def call_b():
    return 2
"""


def build(tmp_path):
    (tmp_path / "mod.py").write_text(SOURCE, encoding="utf-8")
    analysis = RepositoryAnalyzer().analyze(RepositorySpec(source=str(tmp_path)))
    return RepositoryGraphBuilder().build(analysis)


def test_no_symbol_is_silently_dropped(tmp_path):
    store = build(tmp_path)
    snapshot = store.to_snapshot()
    assert len(snapshot.nodes) == len(
        {n.node_id for n in snapshot.nodes}
    )  # every ID is unique
    assert store.has_node("mod.Container.helper")
    assert store.has_node("mod.Container.helper#2")


def test_both_duplicates_get_contains_edges(tmp_path):
    store = build(tmp_path)
    for node_id in ("mod.Container.helper", "mod.Container.helper#2"):
        incoming = store.incoming(node_id, {EdgeType.CONTAINS})
        assert [e.source for e in incoming] == ["mod.Container"]


def test_calls_are_attributed_by_line_range(tmp_path):
    store = build(tmp_path)
    first = [e.target for e in store.outgoing("mod.Container.helper", {EdgeType.CALLS})]
    second = [
        e.target for e in store.outgoing("mod.Container.helper#2", {EdgeType.CALLS})
    ]
    assert first == ["mod.call_a"]
    assert second == ["mod.call_b"]
