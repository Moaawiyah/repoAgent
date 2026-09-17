"""Evidence enrichment attaches bounded, provenance-backed snippets."""

from pathlib import Path

import pytest

from repoagent.adapters.index_store import JsonIndexStore
from repoagent.application.indexing import IndexService
from repoagent.application.searching import SearchService
from repoagent.audit.evidence import enrich
from repoagent.domain.audit import (
    CandidateIssue,
    DetectionSource,
    IssueCategory,
    Severity,
    stable_candidate_id,
)
from repoagent.domain.evidence import MAX_SNIPPET_CHARS
from repoagent.domain.repository import RepositorySpec
from repoagent.graph.store import store_from_snapshot
from repoagent.retrieval.embeddings import HashingEmbeddingProvider
from repoagent.tools.repository import RepositoryToolkit

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "audit_repo"


@pytest.fixture(scope="module")
def toolkit(tmp_path_factory):
    base = tmp_path_factory.mktemp("audit-evidence")
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
        top_k=3,
        chunks=snapshot.chunks,
        max_calls=10,
    )


def _candidate() -> CandidateIssue:
    return CandidateIssue(
        id=stable_candidate_id(IssueCategory.RESOURCE_HANDLING, "risky.py", 12, "x"),
        category=IssueCategory.RESOURCE_HANDLING,
        title="Possible resource leak",
        description="handle = open(...) is never closed.",
        confidence=0.65,
        severity=Severity.HIGH,
        file="risky.py",
        symbol="risky.read_all",
        start_line=12,
        end_line=12,
        detection_source=DetectionSource.AST_RESOURCE,
    )


def test_enrich_attaches_bounded_evidence_not_whole_files(toolkit):
    enriched = enrich([_candidate()], toolkit)
    assert len(enriched) == 1
    evidence = enriched[0].evidence
    assert evidence
    assert len(evidence) <= 3
    for item in evidence:
        assert len(item.snippet) <= MAX_SNIPPET_CHARS
        assert item.file_path


def test_enrich_is_a_noop_for_empty_input(toolkit):
    assert enrich([], toolkit) == []
