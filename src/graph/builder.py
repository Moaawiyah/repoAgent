"""Builds the repository graph from M2 analysis and chunks."""

from repoagent.analysis.models import CallSite, RelationKind, SymbolType
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

    M2 symbol/relationship identity is the qualified name, but real Python
    allows two distinct symbols to share one (property getter/setter/
    deleter, a conditionally redefined function). Rather than silently
    dropping every occurrence but the last, each qualified name becomes a
    "family" of node IDs (the bare name, then ``#2``, ``#3``, ...); every
    family member is a real node, gets its own DEFINES/CONTAINS edges, and
    call sites are attributed to the specific family member whose line
    range contains the call — never guessed when that is ambiguous.
    """

    def __init__(self, chunks: list[CodeChunk] | None = None) -> None:
        self._chunk_ids = (
            {chunk.qualified_name: chunk.chunk_id for chunk in chunks} if chunks else {}
        )

    def build(self, analysis: RepositoryAnalysis) -> InMemoryGraphStore:
        store = InMemoryGraphStore()
        families = self._add_nodes(store, analysis)
        self._add_relation_edges(store, analysis, families)
        self._add_call_edges(store, analysis, families)
        return store

    def _add_nodes(
        self, store: InMemoryGraphStore, analysis: RepositoryAnalysis
    ) -> dict[str, list[str]]:
        families: dict[str, list[str]] = {}
        for file in analysis.files:
            if file.error is not None:
                continue
            seen: dict[str, int] = {}
            for symbol in file.symbols:
                base = symbol.qualified_name
                count = seen[base] = seen.get(base, 0) + 1
                node_id = base if count == 1 else f"{base}#{count}"
                families.setdefault(base, []).append(node_id)
                store.add_node(
                    GraphNode(
                        node_id=node_id,
                        node_type=_TYPE_BY_SYMBOL[symbol.symbol_type],
                        name=symbol.name,
                        file_path=file.path,
                        start_line=symbol.start_line,
                        end_line=symbol.end_line,
                        parent=symbol.parent,
                        module=file.module_name,
                        chunk_id=self._chunk_ids.get(base),
                    )
                )
        return families

    def _add_relation_edges(
        self,
        store: InMemoryGraphStore,
        analysis: RepositoryAnalysis,
        families: dict[str, list[str]],
    ) -> None:
        for relation in analysis.relationships:
            if relation.kind is RelationKind.IMPORTS and not relation.resolved:
                continue
            for source_id in families.get(relation.source, [relation.source]):
                if not store.has_node(source_id):
                    continue
                for target_id in families.get(relation.target, [relation.target]):
                    store.add_edge(
                        GraphEdge(
                            source=source_id,
                            target=target_id,
                            edge_type=relation.kind,
                            resolved=relation.resolved and store.has_node(target_id),
                        )
                    )

    def _add_call_edges(
        self,
        store: InMemoryGraphStore,
        analysis: RepositoryAnalysis,
        families: dict[str, list[str]],
    ) -> None:
        resolver = CallResolver(store)
        for file in analysis.files:
            for site in file.calls:
                caller = self._caller_node(store, families, site)
                if caller is None:
                    continue
                resolved = resolver.resolve(caller, site.expression)
                if resolved is None:
                    continue
                target, exact = resolved
                store.add_edge(
                    GraphEdge(
                        source=caller.node_id,
                        target=target,
                        edge_type=EdgeType.CALLS,
                        line=site.line,
                        resolved=exact,
                    )
                )

    @staticmethod
    def _caller_node(
        store: InMemoryGraphStore, families: dict[str, list[str]], site: CallSite
    ) -> GraphNode | None:
        """Pick the family member whose body actually contains this call.

        A unique line-range match is decisive. Otherwise fall back to the
        first-defined member deterministically, rather than guessing.
        """
        ids = families.get(site.caller, [site.caller])
        candidates = [n for n in (store.get_node(i) for i in ids) if n is not None]
        if len(candidates) <= 1:
            return candidates[0] if candidates else None
        matches = [
            node for node in candidates if node.start_line <= site.line <= node.end_line
        ]
        return matches[0] if len(matches) == 1 else candidates[0]
