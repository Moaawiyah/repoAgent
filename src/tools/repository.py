"""Small read-only toolkit over the application search boundary and snapshot."""

from pathlib import Path

from pydantic import Field, validate_call

from repoagent.application.searching import SearchService
from repoagent.domain.errors import InvestigationError
from repoagent.domain.evidence import MAX_SNIPPET_CHARS, EvidenceItem
from repoagent.graph.models import GraphInspection
from repoagent.graph.store import GraphStore
from repoagent.retrieval.models import CodeChunk, RetrievalStrategy, SearchRequest
from repoagent.tools.inspection import SnapshotInspection
from repoagent.tools.models import (
    FileInput,
    FileInspection,
    NeighborReport,
    SearchCodeInput,
)


class RepositoryToolkit:
    def __init__(
        self,
        repository: str,
        search: SearchService,
        graph: GraphStore | None,
        root: Path,
        top_k: int = 5,
        strategy: RetrievalStrategy = RetrievalStrategy.HYBRID_GRAPH,
        *,
        chunks: list[CodeChunk] | None = None,
        max_calls: int = 30,
    ) -> None:
        SearchCodeInput(query="validate", top_k=top_k)
        self._repository, self._search = repository, search
        self._top_k, self._strategy = top_k, strategy
        self._inspection = SnapshotInspection(graph, chunks or [])
        self.calls, self.max_calls = 0, max_calls

    @property
    def top_k(self) -> int:
        return self._top_k

    @property
    def strategy_name(self) -> str:
        return self._strategy.value

    def _count(self) -> None:
        if self.calls >= self.max_calls:
            raise InvestigationError("Tool-call budget exhausted")
        self.calls += 1

    def search_code(self, query: str, top_k: int | None = None) -> list[EvidenceItem]:
        request = SearchCodeInput(
            query=query, top_k=top_k if top_k is not None else self.top_k
        )
        self._count()
        response = self._search.search(
            SearchRequest(
                repository=self._repository,
                query=request.query,
                top_k=request.top_k,
                strategy=self._strategy,
                rerank=True,
            )
        )
        items = []
        for hit in response.results:
            chunk = hit.chunk
            path = next(
                (
                    note.path
                    for note in hit.evidence
                    if note.kind == "graph" and note.path
                ),
                [],
            )
            items.append(
                EvidenceItem(
                    evidence_id=chunk.chunk_id,
                    repository_id=chunk.repository_id,
                    chunk_id=chunk.chunk_id,
                    query=query,
                    retrieval_source=hit.source.value,
                    file_path=chunk.file_path,
                    symbol_name=chunk.symbol_name,
                    qualified_name=chunk.qualified_name,
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                    snippet=chunk.source[:MAX_SNIPPET_CHARS],
                    rank=hit.rank,
                    confidence=0.0,
                    graph_path=path,
                )
            )
        return items

    @validate_call
    def inspect_symbol(self, qualified_name: str) -> GraphInspection:
        self._count()
        return self._inspection.symbol(qualified_name)

    @validate_call
    def inspect_neighbors(
        self, qualified_name: str, max_nodes: int = Field(default=10, ge=1, le=20)
    ) -> list[NeighborReport]:
        self._count()
        return self._inspection.neighbors(qualified_name, max_nodes)

    def inspect_file(
        self, path: str, start_line: int = 1, end_line: int | None = None
    ) -> FileInspection:
        request = FileInput(path=path, start_line=start_line, end_line=end_line)
        self._count()
        return self._inspection.file(request)
