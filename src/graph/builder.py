"""Builds the repository graph from M2 analysis and chunks."""

from repoagent.analysis.models import RelationKind, SymbolType
from repoagent.analysis.results import RepositoryAnalysis
from repoagent.graph.models import (
    EdgeType,
    GraphEdge,
    GraphNode,
    NodeType,
)
from repoagent.graph.resolver import CallResolver
from repoagent.graph.store import InMemoryGraphStore
from repoagent.retrieval.models import CodeChunk

_TYPE_BY_SYMBOL = {
    SymbolType.MODULE: NodeType.MODULE,
    SymbolType.CLASS: NodeType.CLASS,
    SymbolType.FUNCTION: NodeType.FUNCTION,
    SymbolType.METHOD: NodeType.METHOD,
}


class RepositoryGraphBuilder:
    """Transforms analysis output into a queryable repository graph.

    DEFINES/CONTAINS/IMPORTS/INHERITS reuse the M2 relationship builder
    verbatim; CALLS edges are produced by resolving raw call sites with
    :class:`CallResolver`. Chunk IDs are attached when chunks are supplied
    so retrieval can map graph nodes back to code chunks.
    """

    def __init__(self, chunks: list[CodeChunk] | None = None) -> None:
        self._chunk_ids = (
            {chunk.qualified_name: chunk.chunk_id for chunk in chunks} if chunks else {}
        )

    def build(self, analysis: RepositoryAnalysis) -> InMemoryGraphStore:
        store = InMemoryGraphStore()
        self._add_nodes(store, analysis)
        self._add_relation_edges(store, analysis)
        self._add_call_edges(store, analysis)
        return store

    def _add_nodes(
        self, store: InMemoryGraphStore, analysis: RepositoryAnalysis
    ) -> None:
        for file in analysis.files:
            if file.error is not None:
                continue
            for symbol in file.symbols:
                store.add_node(
                    GraphNode(
                        node_id=symbol.qualified_name,
                        node_type=_TYPE_BY_SYMBOL[symbol.symbol_type],
                        name=symbol.name,
                        file_path=file.path,
                        start_line=symbol.start_line,
                        end_line=symbol.end_line,
                        parent=symbol.parent,
                        module=file.module_name,
                        chunk_id=self._chunk_ids.get(symbol.qualified_name),
                    )
                )

    def _add_relation_edges(
        self, store: InMemoryGraphStore, analysis: RepositoryAnalysis
    ) -> None:
        for relation in analysis.relationships:
            if relation.kind is RelationKind.IMPORTS and not relation.resolved:
                continue
            if not store.has_node(relation.source):
                continue
            store.add_edge(
                GraphEdge(
                    source=relation.source,
                    target=relation.target,
                    edge_type=relation.kind,
                    resolved=relation.resolved and store.has_node(relation.target),
                )
            )

    def _add_call_edges(
        self, store: InMemoryGraphStore, analysis: RepositoryAnalysis
    ) -> None:
        resolver = CallResolver(store)
        for file in analysis.files:
            for site in file.calls:
                caller = store.get_node(site.caller)
                if caller is None:
                    continue
                resolved = resolver.resolve(caller, site.expression)
                if resolved is None:
                    continue
                target, exact = resolved
                store.add_edge(
                    GraphEdge(
                        source=site.caller,
                        target=target,
                        edge_type=EdgeType.CALLS,
                        line=site.line,
                        resolved=exact,
                    )
                )
