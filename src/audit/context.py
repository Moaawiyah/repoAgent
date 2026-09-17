"""Shared, read-only context for audit detectors.

Detectors never open target files directly; this class centralizes the one
safe re-read/re-parse path (mirroring ``analysis.python_ast.parse_untrusted``)
and caches results so N detectors over M files never re-parse M*N times.
"""

import ast
from pathlib import Path

from repoagent.analysis.models import CodeSymbol, SymbolType
from repoagent.analysis.python_ast import parse_untrusted
from repoagent.analysis.results import FileAnalysis, RepositoryAnalysis
from repoagent.graph.store import GraphStore

_INNERMOST_FIRST = (SymbolType.METHOD, SymbolType.FUNCTION, SymbolType.CLASS)

MAX_SOURCE_BYTES = 1_000_000


class AuditContext:
    """Analysis, graph, and cached AST/source access for one repository."""

    def __init__(
        self, analysis: RepositoryAnalysis, root: Path, graph: GraphStore
    ) -> None:
        self.analysis = analysis
        self.root = root
        self.graph = graph
        self._source: dict[str, str | None] = {}
        self._tree: dict[str, ast.Module | None] = {}

    def files(self) -> list[FileAnalysis]:
        """Successfully analyzed files only."""
        return [file for file in self.analysis.files if file.error is None]

    def source(self, relative_path: str) -> str | None:
        if relative_path not in self._source:
            self._source[relative_path] = self._read(relative_path)
        return self._source[relative_path]

    def tree(self, relative_path: str) -> ast.Module | None:
        if relative_path not in self._tree:
            source = self.source(relative_path)
            self._tree[relative_path] = self._parse(relative_path, source)
        return self._tree[relative_path]

    def symbol_at(self, file: FileAnalysis, line: int) -> CodeSymbol | None:
        """The narrowest enclosing function/method (or class) containing ``line``."""
        candidates = [s for s in file.symbols if s.start_line <= line <= s.end_line]
        for kind in _INNERMOST_FIRST:
            narrowed = [s for s in candidates if s.symbol_type is kind]
            if narrowed:
                return min(narrowed, key=lambda s: s.end_line - s.start_line)
        return None

    def _read(self, relative_path: str) -> str | None:
        path = self.root / relative_path
        try:
            if path.is_symlink() or path.stat().st_size > MAX_SOURCE_BYTES:
                return None
            return path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            return None

    @staticmethod
    def _parse(relative_path: str, source: str | None) -> ast.Module | None:
        if not source:
            return None
        try:
            return parse_untrusted(source, relative_path)
        except (SyntaxError, ValueError, RecursionError):
            return None
