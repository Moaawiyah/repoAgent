"""Analysis model behavior: immutability, strictness, computed summaries."""

import pytest
from pydantic import ValidationError

from repoagent.analysis.models import (
    CodeSymbol,
    ImportedName,
    ImportInfo,
    ImportOrigin,
    RelationKind,
    Relationship,
    SymbolType,
)
from repoagent.analysis.results import FileAnalysis, FileError, RepositoryAnalysis


def make_symbol(**overrides):
    data = {
        "name": "authenticate",
        "qualified_name": "app.UserService.authenticate",
        "file_path": "app/service.py",
        "symbol_type": SymbolType.METHOD,
        "start_line": 5,
        "end_line": 9,
        "parent": "app.UserService",
    }
    data.update(overrides)
    return CodeSymbol(**data)


def make_analysis(**overrides):
    module = make_symbol(
        name="app",
        qualified_name="app",
        file_path="app/__init__.py",
        symbol_type=SymbolType.MODULE,
        start_line=1,
        end_line=4,
        parent=None,
    )
    data = {
        "repository_name": "repo",
        "repository_root": "/tmp/repo",
        "discovered_files": 7,
        "python_files": 2,
        "config_files": ["pyproject.toml"],
        "test_files": ["tests/test_a.py"],
        "modules": ["app/__init__.py", "app/service.py"],
        "files": [
            FileAnalysis(path="app/__init__.py", module_name="app", symbols=[module]),
            FileAnalysis(
                path="app/service.py",
                module_name="app.service",
                symbols=[make_symbol()],
            ),
        ],
        "relationships": [
            Relationship(
                kind=RelationKind.CONTAINS,
                source="app.UserService",
                target="app.UserService.authenticate",
                resolved=True,
            )
        ],
    }
    data.update(overrides)
    return RepositoryAnalysis(**data)


def test_symbols_and_imports_are_frozen_and_strict():
    with pytest.raises(ValidationError):
        make_symbol().model_copy().name = "other"
    with pytest.raises(ValidationError):
        make_symbol(unknown_field=True)
    with pytest.raises(ValidationError):
        ImportInfo(module="os", line=1, origin="elsewhere")


def test_import_info_defaults_and_names():
    info = ImportInfo(module="os", line=3)
    assert info.names == [] and info.origin is ImportOrigin.UNKNOWN
    named = ImportInfo(
        module="collections", line=4, names=[ImportedName(name="y", alias="z")]
    )
    assert named.names[0].name == "y" and named.names[0].alias == "z"


def test_computed_summary_counts_and_serialization():
    analysis = make_analysis()
    assert analysis.module_count == 1
    assert analysis.class_count == 0
    assert analysis.function_count == 0
    assert analysis.method_count == 1
    assert analysis.test_count == 1
    assert analysis.errors == []
    data = analysis.model_dump(mode="json")
    assert data["method_count"] == 1
    assert data["relationships"][0]["kind"] == "contains"
    assert [s["qualified_name"] for s in data["symbols"]] == [
        "app",
        "app.UserService.authenticate",
    ]


def test_error_files_surface_in_summary():
    failed = FileAnalysis(
        path="broken.py",
        module_name="broken",
        error=FileError(path="broken.py", error_type="syntax", message="bad"),
    )
    analysis = make_analysis(files=[failed])
    assert [error.error_type for error in analysis.errors] == ["syntax"]
    assert analysis.method_count == 0
