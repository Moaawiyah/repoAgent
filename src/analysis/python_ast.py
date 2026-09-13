"""Single-file Python static analysis using the built-in ast module."""

import ast
from pathlib import Path, PurePosixPath

from repoagent.analysis.results import FileAnalysis, FileError
from repoagent.analysis.symbols import ModuleVisitor

MAX_SOURCE_BYTES = 1_000_000


def module_name(relative_path: str) -> str:
    """Derive the dotted module name from a repository-relative path."""
    parts = PurePosixPath(relative_path).with_suffix("").parts
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts) if parts else "__init__"


class PythonAnalyzer:
    """Parses one Python file into symbols and imports without executing it.

    A malformed, unreadable, oversized, or non-UTF-8 file produces a
    recorded per-file error instead of aborting the repository analysis.
    """

    def analyze(self, relative_path: str, path: Path) -> FileAnalysis:
        name = module_name(relative_path)
        if isinstance(source := self._read(relative_path, path), FileError):
            return FileAnalysis(path=relative_path, module_name=name, error=source)
        tree = self._parse(relative_path, source)
        if isinstance(tree, FileError):
            return FileAnalysis(path=relative_path, module_name=name, error=tree)
        visitor = ModuleVisitor(name, relative_path, len(source.splitlines()))
        visitor.visit(tree)
        return FileAnalysis(
            path=relative_path,
            module_name=name,
            line_count=len(source.splitlines()),
            symbols=visitor.symbols,
            imports=visitor.imports,
        )

    @staticmethod
    def _read(relative_path: str, path: Path) -> str | FileError:
        try:
            if path.stat().st_size > MAX_SOURCE_BYTES:
                return FileError(
                    path=relative_path,
                    error_type="too_large",
                    message="Source file exceeds the analysis size limit",
                )
            return path.read_text(encoding="utf-8")
        except UnicodeError:
            return FileError(
                path=relative_path,
                error_type="encoding",
                message="Source file is not valid UTF-8 text",
            )
        except OSError:
            return FileError(
                path=relative_path,
                error_type="unreadable",
                message="Source file could not be read",
            )

    @staticmethod
    def _parse(relative_path: str, source: str) -> ast.Module | FileError:
        try:
            return ast.parse(source, filename=relative_path)
        except (SyntaxError, ValueError, RecursionError):
            return FileError(
                path=relative_path,
                error_type="syntax",
                message="Source file contains invalid Python syntax",
            )
