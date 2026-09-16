"""graph.json persistence: schema, round trip, and malformed input."""

from pathlib import Path

import pytest

from repoagent.analysis.analyzer import RepositoryAnalyzer
from repoagent.domain.errors import GraphError
from repoagent.domain.repository import RepositorySpec
from repoagent.graph.builder import RepositoryGraphBuilder
from repoagent.graph.serializer import (
    GRAPH_SCHEMA_VERSION,
    build_document,
    document_to_snapshot,
    read_graph_json,
    write_graph_json,
)

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "rag_repo"


@pytest.fixture(scope="module")
def document():
    analysis = RepositoryAnalyzer().analyze(RepositorySpec(source=str(FIXTURE)))
    snapshot = RepositoryGraphBuilder().build(analysis).to_snapshot()
    return build_document(
        snapshot,
        repository=analysis.repository_name,
        files=analysis.python_files,
        symbols=len(analysis.symbols),
    )


def test_document_carries_schema_version_and_metadata(document):
    assert document.schema_version == GRAPH_SCHEMA_VERSION
    assert document.repository == "rag_repo"
    assert document.metadata.files > 0
    assert document.metadata.symbols == len(document.nodes)
    assert document.metadata.relationships == len(document.edges)


def test_write_then_read_round_trips(document, tmp_path):
    path = tmp_path / "artifacts" / "graph.json"
    write_graph_json(document, path)
    assert path.is_file()
    loaded = read_graph_json(path)
    assert loaded == document
    snapshot = document_to_snapshot(loaded)
    assert len(snapshot.nodes) == len(document.nodes)
    assert len(snapshot.edges) == len(document.edges)


def test_write_is_deterministic(document, tmp_path):
    first = tmp_path / "a.json"
    second = tmp_path / "b.json"
    write_graph_json(document, first)
    write_graph_json(document, second)
    assert first.read_bytes() == second.read_bytes()


def test_write_wraps_filesystem_failures(document, tmp_path):
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("occupied", encoding="utf-8")
    with pytest.raises(GraphError):
        write_graph_json(document, blocker / "graph.json")


def test_read_rejects_missing_file(tmp_path):
    with pytest.raises(GraphError):
        read_graph_json(tmp_path / "missing.json")


def test_read_rejects_invalid_json(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(GraphError):
        read_graph_json(path)


def test_read_rejects_unsupported_schema_version(document, tmp_path):
    path = tmp_path / "graph.json"
    write_graph_json(document, path)
    stale = path.read_text(encoding="utf-8").replace(
        f'"schema_version": "{GRAPH_SCHEMA_VERSION}"', '"schema_version": "99.0"'
    )
    path.write_text(stale, encoding="utf-8")
    with pytest.raises(GraphError, match="schema version"):
        read_graph_json(path)


def test_read_rejects_structurally_invalid_document(document, tmp_path):
    path = tmp_path / "graph.json"
    write_graph_json(document, path)
    broken = path.read_text(encoding="utf-8").replace('"metadata"', '"metadata_typo"')
    path.write_text(broken, encoding="utf-8")
    with pytest.raises(GraphError):
        read_graph_json(path)
