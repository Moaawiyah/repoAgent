"""Deterministic relationship extraction across analyzed files."""

from repoagent.analysis.models import (
    CodeSymbol,
    ImportOrigin,
    RelationKind,
    Relationship,
    SymbolType,
)
from repoagent.analysis.results import FileAnalysis


class RelationshipBuilder:
    """Builds import, inheritance, containment, and definition edges.

    Only statically verifiable relations are produced. Inheritance targets
    resolve to internal classes when the reference is unambiguous; other
    targets are preserved unresolved rather than guessed.
    """

    def __init__(self, internal_modules: set[str]) -> None:
        self._modules = frozenset(internal_modules)
        self._classes: frozenset[str] = frozenset()
        self._simple: dict[str, list[str]] = {}

    def build(self, files: list[FileAnalysis]) -> list[Relationship]:
        self._index(files)
        edges: list[Relationship] = []
        for file in files:
            edges.extend(self._file_edges(file))
        return sorted(
            edges, key=lambda edge: (edge.kind.value, edge.source, edge.target)
        )

    def _index(self, files: list[FileAnalysis]) -> None:
        self._classes = frozenset(
            symbol.qualified_name
            for file in files
            for symbol in file.symbols
            if symbol.symbol_type is SymbolType.CLASS
        )
        self._simple = {}
        for qualified in sorted(self._classes):
            simple = qualified.rsplit(".", 1)[-1]
            self._simple.setdefault(simple, []).append(qualified)

    def _file_edges(self, file: FileAnalysis) -> list[Relationship]:
        edges: list[Relationship] = []
        for symbol in file.symbols:
            if symbol.symbol_type is SymbolType.MODULE:
                edges.extend(self._import_edges(file, symbol))
            elif symbol.symbol_type is SymbolType.CLASS:
                edges.extend(self._inherit_edges(symbol))
                if symbol.parent is None:
                    edges.append(self._defines(file, symbol))
            elif symbol.symbol_type is SymbolType.METHOD:
                edges.append(self._contains(symbol))
            elif symbol.parent is None:
                edges.append(self._defines(file, symbol))
        return edges

    def _import_edges(
        self, file: FileAnalysis, module: CodeSymbol
    ) -> list[Relationship]:
        return [
            Relationship(
                kind=RelationKind.IMPORTS,
                source=module.qualified_name,
                target=imp.module,
                resolved=imp.origin is ImportOrigin.INTERNAL,
            )
            for imp in file.imports
        ]

    def _inherit_edges(self, symbol: CodeSymbol) -> list[Relationship]:
        edges = []
        for base in symbol.bases:
            target, resolved = self._resolve_base(base)
            edges.append(
                Relationship(
                    kind=RelationKind.INHERITS,
                    source=symbol.qualified_name,
                    target=target,
                    resolved=resolved,
                )
            )
        return edges

    def _resolve_base(self, base: str) -> tuple[str, bool]:
        if base in self._classes:
            return base, True
        candidates = self._simple.get(base, [])
        if len(candidates) == 1:
            return candidates[0], True
        return base, False

    @staticmethod
    def _contains(symbol: CodeSymbol) -> Relationship:
        return Relationship(
            kind=RelationKind.CONTAINS,
            source=symbol.parent or "",
            target=symbol.qualified_name,
            resolved=True,
        )

    @staticmethod
    def _defines(file: FileAnalysis, symbol: CodeSymbol) -> Relationship:
        return Relationship(
            kind=RelationKind.DEFINES,
            source=file.module_name,
            target=symbol.qualified_name,
            resolved=True,
        )
