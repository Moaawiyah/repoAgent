"""Graph builder behavior on the synthetic RAG fixture."""

from pathlib import Path

from repoagent.analysis.analyzer import RepositoryAnalyzer
from repoagent.domain.repository import RepositorySpec
from repoagent.graph.builder import RepositoryGraphBuilder
from repoagent.graph.models import EdgeType, NodeType
from repoagent.retrieval.chunking import CodeChunker

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "rag_repo"


def build(chunks=None):
    analysis = RepositoryAnalyzer().analyze(RepositorySpec(source=str(FIXTURE)))
    return RepositoryGraphBuilder(chunks).build(analysis)


def has_edge(store, source, target, edge_type):
    return any(
        edge.source == source and edge.target == target and edge.edge_type is edge_type
        for edge in store.to_snapshot().edges
    )


def test_nodes_cover_modules_classes_functions_methods():
    store = build()
    assert store.has_node("auth.service")
    assert store.has_node("auth.service.AuthService")
    assert store.has_node("auth.tokens.issue_token")
    assert store.has_node("auth.service.AuthService.verify_password")
    assert store.get_node("auth.service").node_type is NodeType.MODULE
    assert store.get_node("auth.service.AuthService").node_type is NodeType.CLASS


def test_containment_and_definition_edges():
    store = build()
    assert has_edge(store, "auth.service", "auth.service.AuthService", EdgeType.DEFINES)
    assert has_edge(
        store,
        "auth.service.AuthService",
        "auth.service.AuthService.verify_password",
        EdgeType.CONTAINS,
    )


def test_internal_import_edges_exclude_external():
    store = build()
    assert has_edge(store, "auth.service", "auth.tokens", EdgeType.IMPORTS)
    all_edges = store.to_snapshot().edges
    assert not any(
        edge.edge_type is EdgeType.IMPORTS and edge.target == "requests"
        for edge in all_edges
    )


def test_self_calls_resolve_fully():
    store = build()
    assert has_edge(
        store,
        "auth.service.AuthService.authenticate",
        "auth.service.AuthService.verify_password",
        EdgeType.CALLS,
    )


def test_attribute_calls_stay_partially_resolved():
    store = build()
    snapshot = store.to_snapshot()
    candidates = [
        edge
        for edge in snapshot.edges
        if edge.source == "auth.controller.AuthController.login"
        and edge.edge_type is EdgeType.CALLS
    ]
    assert [(edge.target, edge.resolved) for edge in candidates] == [
        ("auth.service.AuthService.authenticate", False)
    ]


def test_unresolved_calls_create_no_edges():
    store = build()
    snapshot = store.to_snapshot()
    targets = {
        edge.target
        for edge in snapshot.edges
        if edge.source == "storage.blob_cache.BlobCacheStore.fetch_or_download"
        and edge.edge_type is EdgeType.CALLS
    }
    assert targets == {"storage.blob_cache.BlobCacheStore._download"}
    dynamic = {
        edge.target
        for edge in snapshot.edges
        if edge.source == "web.routes.login_route" and edge.edge_type is EdgeType.CALLS
    }
    assert "auth.service.AuthService.verify_password" in dynamic


def test_chunk_ids_link_nodes_to_chunks():
    analysis = RepositoryAnalyzer().analyze(RepositorySpec(source=str(FIXTURE)))
    repo_id = "rag_repo-test"
    chunks = CodeChunker(repo_id).chunk(analysis, FIXTURE.resolve())
    store = RepositoryGraphBuilder(chunks).build(analysis)
    verify = store.get_node("auth.service.AuthService.verify_password")
    assert verify.chunk_id is not None
    assert verify.chunk_id in {chunk.chunk_id for chunk in chunks}
    bare = RepositoryGraphBuilder().build(analysis)
    assert bare.get_node("auth.service").chunk_id is None
