"""Read-only agent tools against an indexed fixture repository."""

from pathlib import Path

import pytest

from repoagent.adapters.index_store import JsonIndexStore
from repoagent.application.indexing import IndexService
from repoagent.application.searching import SearchService
from repoagent.domain.errors import InvestigationError
from repoagent.domain.repository import RepositorySpec
from repoagent.graph.store import store_from_snapshot
from repoagent.retrieval.embeddings import HashingEmbeddingProvider
from repoagent.tools.repository import RepositoryToolkit

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "auth_bug"


@pytest.fixture(scope="module")
def toolkit(tmp_path_factory):
    base = tmp_path_factory.mktemp("tools")
    store = JsonIndexStore(base / "idx")
    embedding = HashingEmbeddingProvider(64)
    IndexService(store, embedding).index(RepositorySpec(source=str(FIXTURE)))
    search = SearchService(store, embedding)
    snapshot = search.snapshot(str(FIXTURE))
    graph = store_from_snapshot(snapshot.graph)
    return RepositoryToolkit(
        str(FIXTURE),
        search,
        graph,
        Path(snapshot.repository_root),
        top_k=5,
        chunks=snapshot.chunks,
    )


def test_search_code_returns_provenance_backed_evidence(toolkit):
    items = toolkit.search_code("email lookup")
    assert items
    for item in items:
        assert item.file_path.endswith(".py")
        assert item.qualified_name
        assert item.start_line >= 1
        assert item.snippet
        assert item.retrieval_source == "hybrid_graph"
        assert 0.0 <= item.confidence <= 1.0
    assert toolkit.calls == 1


def test_search_code_rejects_empty_query(toolkit):
    with pytest.raises(ValueError):
        toolkit.search_code("   ")


def test_inspect_symbol_returns_relationships(toolkit):
    inspection = toolkit.inspect_symbol(
        "app.users.repository.UserRepository.find_by_email"
    )
    assert inspection.node is not None
    assert inspection.node.file_path == "app/users/repository.py"
    assert any(
        edge.source == "app.auth.service.AuthService.login"
        for edge in inspection.incoming
    )


def test_inspect_symbol_unknown_returns_empty(toolkit):
    empty = toolkit.inspect_symbol("no.Such.symbol")
    assert empty.node is None and empty.outgoing == []


def test_inspect_neighbors_follows_calls(toolkit):
    neighbors = toolkit.inspect_neighbors("app.auth.service.AuthService.login")
    ids = [neighbor.node_id for neighbor in neighbors]
    assert "app.users.repository.UserRepository.find_by_email" in ids
    report = next(
        n
        for n in neighbors
        if n.node_id == "app.users.repository.UserRepository.find_by_email"
    )
    assert report.relation == "calls"


def test_inspect_file_bounded_and_safe(toolkit):
    inspection = toolkit.inspect_file("app/users/repository.py")
    assert inspection.exists
    assert inspection.content
    assert inspection.end_line - inspection.start_line < 400
    missing = toolkit.inspect_file("nope/missing.py")
    assert not missing.exists
    with pytest.raises(InvestigationError):
        toolkit.inspect_file("../outside.py")
    with pytest.raises(InvestigationError):
        toolkit.inspect_file("/absolute/path.py")
