"""Vault-wide filename uniqueness for the Obsidian exporter."""

from repoagent.export.notes import build_filenames, safe_name
from repoagent.export.obsidian import ObsidianExporter
from repoagent.graph.models import GraphEdge, GraphNode, GraphSnapshot, NodeType


def node(node_id: str, name: str, node_type: NodeType = NodeType.FUNCTION) -> GraphNode:
    return GraphNode(
        node_id=node_id,
        node_type=node_type,
        name=name,
        file_path="pkg/mod.py",
        start_line=1,
        end_line=2,
        module="pkg.mod",
    )


def test_distinct_ids_sanitizing_alike_get_distinct_filenames():
    """Two different symbols whose sanitized names collide must not merge."""
    nodes = [node("pkg.a$b", "b"), node("pkg.a#b", "b")]
    assert safe_name(nodes[0].node_id) == safe_name(nodes[1].node_id) == "pkg.a_b"
    filenames = build_filenames(nodes)
    assert filenames["pkg.a$b"] == "pkg.a_b"
    assert filenames["pkg.a#b"] == "pkg.a_b-2"
    assert len(set(filenames.values())) == 2


def test_filename_assignment_is_deterministic():
    nodes = [node("pkg.a$b", "b"), node("pkg.a#b", "b"), node("pkg.a%b", "b")]
    first = build_filenames(nodes)
    second = build_filenames(nodes)
    assert first == second


def test_duplicate_simple_names_keep_separate_notes():
    """Same simple ``name`` in different modules: distinct IDs, no collision."""
    nodes = [node("pkg.mod_a.helper", "helper"), node("pkg.mod_b.helper", "helper")]
    filenames = build_filenames(nodes)
    assert filenames["pkg.mod_a.helper"] == "pkg.mod_a.helper"
    assert filenames["pkg.mod_b.helper"] == "pkg.mod_b.helper"


def test_colliding_nodes_both_get_notes_and_valid_wikilinks(tmp_path):
    caller = node("pkg.caller", "caller")
    first = node("pkg.a$b", "b")
    second = node("pkg.a#b", "b")
    edges = [
        GraphEdge(source="pkg.caller", target="pkg.a$b", edge_type="calls"),
        GraphEdge(source="pkg.caller", target="pkg.a#b", edge_type="calls"),
    ]
    snapshot = GraphSnapshot(nodes=[caller, first, second], edges=edges)
    exporter = ObsidianExporter(tmp_path)
    summary = exporter.export(snapshot, tmp_path / "vault")
    assert summary.notes == 4  # 3 nodes + Repository.md
    functions = sorted(p.name for p in (tmp_path / "vault" / "Functions").iterdir())
    assert functions == ["pkg.a_b-2.md", "pkg.a_b.md", "pkg.caller.md"]
    caller_note = (tmp_path / "vault" / "Functions" / "pkg.caller.md").read_text(
        encoding="utf-8"
    )
    assert "[[pkg.a_b]]" in caller_note
    assert "[[pkg.a_b-2]]" in caller_note
