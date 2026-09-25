"""Structure-aware chunking built on M2 analysis symbols."""

import logging
from pathlib import Path

from repoagent.analysis.identity import symbol_node_ids
from repoagent.analysis.models import CodeSymbol, SymbolType
from repoagent.analysis.results import FileAnalysis, RepositoryAnalysis
from repoagent.retrieval.models import CodeChunk, make_chunk_id

_TOP_LEVEL = (SymbolType.CLASS, SymbolType.FUNCTION)


class CodeChunker:
    """Splits analyzed files into deterministic, symbol-aligned chunks.

    Functions and methods become full-symbol chunks. Class chunks keep the
    class preamble (header, docstring, attributes) without duplicating
    nested symbol bodies. A module chunk holds residual module-level lines
    such as imports and constants. Chunk sources always match their
    reported line ranges.
    """

    language = "python"

    def __init__(self, repository_id: str, identity_scope: str | None = None) -> None:
        # Chunk IDs use a location-independent scope (the repository name) so
        # identical source keeps identical IDs, and ranking tie-breaks, wherever
        # it is checked out; ``repository_id`` still records the exact index.
        self._repo, self._scope = repository_id, identity_scope or repository_id

    def chunk(self, analysis: RepositoryAnalysis, root: Path) -> list[CodeChunk]:
        """Chunk every analyzed file, reading each file exactly once."""
        chunks: list[CodeChunk] = []
        for file in analysis.files:
            if file.error is not None or not file.symbols:
                continue
            chunks.extend(self._chunk_file(file, root))
        return chunks

    def _chunk_file(self, file: FileAnalysis, root: Path) -> list[CodeChunk]:
        try:
            lines = (root / file.path).read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError):
            logging.getLogger(__name__).warning(
                "Chunk source read failed",
                extra={"event": "chunk_source_unreadable"},
            )
            return []
        module = next(
            symbol for symbol in file.symbols if symbol.symbol_type is SymbolType.MODULE
        )
        chunks: list[CodeChunk] = []
        node_ids = {id(sym): node for sym, node in symbol_node_ids(file.symbols)}
        for symbol in file.symbols:
            if symbol.symbol_type is SymbolType.CLASS:
                body = self._residual(lines, self._nested(symbol, file), symbol)
                chunks.append(self._build(file, module, symbol, body, node_ids))
            elif symbol.symbol_type in (SymbolType.FUNCTION, SymbolType.METHOD):
                body = [
                    (number, lines[number - 1])
                    for number in range(symbol.start_line, symbol.end_line + 1)
                ]
                chunks.append(self._build(file, module, symbol, body, node_ids))
        residual = self._residual(lines, self._top_level(file), None)
        if any(text.strip() for _, text in residual):
            chunks.append(self._build(file, module, module, residual, node_ids))
        return chunks

    @staticmethod
    def _nested(symbol: CodeSymbol, file: FileAnalysis) -> list[CodeSymbol]:
        prefix = symbol.qualified_name + "."
        return [
            nested
            for nested in file.symbols
            if nested.qualified_name.startswith(prefix)
        ]

    @staticmethod
    def _top_level(file: FileAnalysis) -> list[CodeSymbol]:
        return [
            symbol
            for symbol in file.symbols
            if symbol.parent is None and symbol.symbol_type in _TOP_LEVEL
        ]

    @staticmethod
    def _residual(
        lines: list[str], occupied: list[CodeSymbol], within: CodeSymbol | None
    ) -> list[tuple[int, str]]:
        covered = {
            number
            for symbol in occupied
            for number in range(symbol.start_line, symbol.end_line + 1)
        }
        if within is not None:
            numbers = range(within.start_line, within.end_line + 1)
        else:
            numbers = range(1, len(lines) + 1)
        return [
            (number, lines[number - 1]) for number in numbers if number not in covered
        ]

    def _build(
        self,
        file: FileAnalysis,
        module: CodeSymbol,
        symbol: CodeSymbol,
        body: list[tuple[int, str]],
        node_ids: dict[int, str],
    ) -> CodeChunk:
        numbers = [number for number, _ in body]
        source = "\n".join(text for _, text in body)
        symbol_type = SymbolType.MODULE if symbol is module else symbol.symbol_type
        # The node ID equals the qualified name for unique symbols, so chunk
        # IDs only change for duplicates, which now never collide.
        node_id = node_ids[id(symbol)]
        return CodeChunk(
            chunk_id=make_chunk_id(self._scope, file.path, node_id, source),
            node_id=node_id,
            repository_id=self._repo,
            file_path=file.path,
            language=self.language,
            symbol_name=symbol.name,
            qualified_name=symbol.qualified_name,
            symbol_type=symbol_type,
            start_line=min(numbers),
            end_line=max(numbers),
            source=source,
            parent=symbol.parent,
            docstring=symbol.docstring,
            imports=sorted({imp.module for imp in file.imports}),
        )
