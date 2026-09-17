"""Wires the existing index/search stack to enrich audit candidates.

Indexing an unseen repository here is what lets `repoagent audit <repo>`
work without a separate `repoagent index` step first — the same snapshot
then also serves any later `investigate`/`search` on that repository.
"""

from pathlib import Path

from repoagent.application.indexing import IndexService
from repoagent.application.searching import SearchService
from repoagent.audit.evidence import enrich
from repoagent.domain.audit import CandidateIssue
from repoagent.domain.repository import RepositorySpec
from repoagent.graph.store import GraphStore
from repoagent.ports.index_store import IndexStore
from repoagent.retrieval.embeddings import EmbeddingProvider
from repoagent.retrieval.models import RetrievalStrategy
from repoagent.tools.repository import RepositoryToolkit

EVIDENCE_TOP_K = 3


def attach_evidence(
    store: IndexStore,
    embedding: EmbeddingProvider,
    repository: str,
    root: Path,
    graph_store: GraphStore,
    candidates: list[CandidateIssue],
) -> list[CandidateIssue]:
    """Attach bounded, provenance-carrying evidence to each candidate."""
    if not candidates:
        return candidates
    IndexService(store, embedding).index(RepositorySpec(source=repository))
    search = SearchService(store, embedding)
    snapshot = search.snapshot(repository)
    toolkit = RepositoryToolkit(
        repository,
        search,
        graph_store,
        root,
        top_k=EVIDENCE_TOP_K,
        strategy=RetrievalStrategy.HYBRID_GRAPH,
        chunks=snapshot.chunks,
        max_calls=len(candidates) + 1,
    )
    return enrich(candidates, toolkit)
