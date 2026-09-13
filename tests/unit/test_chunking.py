"""Structure-aware chunking over M2 analysis output."""

from pathlib import Path

from repoagent.analysis.analyzer import RepositoryAnalyzer
from repoagent.domain.repository import RepositorySpec
from repoagent.retrieval.chunking import CodeChunker
from repoagent.retrieval.models import SymbolType

SOURCE = '''\
"""Module docs."""

import os

MAX = 4


class Greeter(Base):
    """Greets people."""

    prefix = "hello"

    def greet(self, name: str) -> str:
        return f"{self.prefix} {name}"

    async def shout(self, name: str) -> str:
        return self.greet(name).upper() + "!"


def make_greeter() -> Greeter:
    """Factory."""
    return Greeter()
'''


def build_chunks(tmp_path, source=SOURCE, name="svc.py"):
    (tmp_path / name).write_text(source)
    analysis = RepositoryAnalyzer().analyze(RepositorySpec(source=str(tmp_path)))
    return CodeChunker("repo-x").chunk(analysis, Path(analysis.repository_root))


def find(chunks, qualified):
    return next(chunk for chunk in chunks if chunk.qualified_name == qualified)


def test_functions_methods_and_module_become_chunks(tmp_path):
    chunks = build_chunks(tmp_path)
    qualified = {chunk.qualified_name for chunk in chunks}
    assert qualified == {
        "svc",
        "svc.Greeter",
        "svc.Greeter.greet",
        "svc.Greeter.shout",
        "svc.make_greeter",
    }
    assert find(chunks, "svc").symbol_type is SymbolType.MODULE
    assert find(chunks, "svc.Greeter.greet").symbol_type is SymbolType.METHOD
    assert find(chunks, "svc.make_greeter").symbol_type is SymbolType.FUNCTION


def test_symbol_chunks_preserve_parent_spans_and_source(tmp_path):
    chunks = build_chunks(tmp_path)
    lines = SOURCE.splitlines()
    for chunk in chunks:
        if chunk.symbol_type in (SymbolType.METHOD, SymbolType.FUNCTION):
            assert (
                chunk.source.splitlines()
                == lines[chunk.start_line - 1 : chunk.end_line]
            )
    greet = find(chunks, "svc.Greeter.greet")
    assert (greet.start_line, greet.end_line) == (13, 14)
    assert greet.parent == "svc.Greeter"


def test_class_chunk_keeps_preamble_without_method_bodies(tmp_path):
    greeter = find(build_chunks(tmp_path), "svc.Greeter")
    assert (greeter.start_line, greeter.end_line) == (8, 15)
    assert "class Greeter(Base):" in greeter.source
    assert '"""Greets people."""' in greeter.source
    assert 'prefix = "hello"' in greeter.source
    assert "def greet" not in greeter.source
    assert greeter.docstring == "Greets people."


def test_module_chunk_holds_residual_lines_only(tmp_path):
    module = find(build_chunks(tmp_path), "svc")
    assert module.start_line == 1
    assert "import os" in module.source
    assert "MAX = 4" in module.source
    assert "def greet" not in module.source


def test_chunk_ids_are_deterministic_and_content_sensitive(tmp_path):
    first = {chunk.qualified_name: chunk.chunk_id for chunk in build_chunks(tmp_path)}
    second = {chunk.qualified_name: chunk.chunk_id for chunk in build_chunks(tmp_path)}
    assert first == second
    changed = build_chunks(tmp_path, source=SOURCE.replace("MAX = 4", "MAX = 5"))
    assert {chunk.chunk_id for chunk in changed} != set(first.values())


def test_chunks_carry_import_metadata_and_provenance(tmp_path):
    for chunk in build_chunks(tmp_path):
        assert chunk.imports == ["os"]
        assert chunk.repository_id == "repo-x"
        assert chunk.language == "python"
        assert chunk.file_path == "svc.py"


def test_unreadable_sources_are_skipped(tmp_path):
    (tmp_path / "svc.py").write_text(SOURCE)
    analysis = RepositoryAnalyzer().analyze(RepositorySpec(source=str(tmp_path)))
    (tmp_path / "svc.py").unlink()
    assert CodeChunker("repo-x").chunk(analysis, tmp_path) == []


def test_repository_without_python_files_yields_no_chunks(tmp_path):
    analysis = RepositoryAnalyzer().analyze(RepositorySpec(source=str(tmp_path)))
    assert CodeChunker("repo-x").chunk(analysis, tmp_path) == []
