"""Relationship extraction across analyzed files."""

from repoagent.analysis.models import (
    CodeSymbol,
    ImportInfo,
    ImportOrigin,
    RelationKind,
    SymbolType,
)
from repoagent.analysis.relations import RelationshipBuilder
from repoagent.analysis.results import FileAnalysis, FileError


def make_file(module, symbols, imports=()):
    return FileAnalysis(
        path=module.replace(".", "/") + ".py",
        module_name=module,
        symbols=list(symbols),
        imports=list(imports),
    )


def make_symbol(name, qualified, kind, parent=None, bases=()):
    return CodeSymbol(
        name=name,
        qualified_name=qualified,
        file_path="f.py",
        symbol_type=kind,
        start_line=1,
        end_line=2,
        parent=parent,
        bases=list(bases),
    )


def pairs(edges):
    return {(edge.kind, edge.source, edge.target, edge.resolved) for edge in edges}


def test_inheritance_containment_and_definitions():
    base = make_symbol("BaseService", "app.base.BaseService", SymbolType.CLASS)
    user = make_symbol(
        "UserService",
        "app.svc.UserService",
        SymbolType.CLASS,
        bases=["BaseService"],
    )
    method = make_symbol(
        "authenticate",
        "app.svc.UserService.authenticate",
        SymbolType.METHOD,
        parent="app.svc.UserService",
    )
    function = make_symbol("create", "app.svc.create", SymbolType.FUNCTION)
    edges = RelationshipBuilder({"app.svc", "app.base"}).build(
        [
            make_file("app.svc", [user, method, function]),
            make_file("app.base", [base]),
        ]
    )
    assert pairs(edges) == {
        (
            RelationKind.INHERITS,
            "app.svc.UserService",
            "app.base.BaseService",
            True,
        ),
        (
            RelationKind.CONTAINS,
            "app.svc.UserService",
            "app.svc.UserService.authenticate",
            True,
        ),
        (RelationKind.DEFINES, "app.svc", "app.svc.UserService", True),
        (RelationKind.DEFINES, "app.svc", "app.svc.create", True),
        (RelationKind.DEFINES, "app.base", "app.base.BaseService", True),
    }


def test_import_edges_resolve_internal_targets_only():
    module = make_symbol("app.svc", "app.svc", SymbolType.MODULE)
    internal = ImportInfo(module="app.base", line=1, origin=ImportOrigin.INTERNAL)
    external = ImportInfo(module="requests", line=2, origin=ImportOrigin.EXTERNAL)
    edges = RelationshipBuilder({"app.svc", "app.base"}).build(
        [make_file("app.svc", [module], [internal, external])]
    )
    assert pairs(edges) == {
        (RelationKind.IMPORTS, "app.svc", "app.base", True),
        (RelationKind.IMPORTS, "app.svc", "requests", False),
    }


def test_ambiguous_base_names_stay_unresolved():
    first = make_symbol("Base", "a.Base", SymbolType.CLASS)
    second = make_symbol("Base", "b.Base", SymbolType.CLASS)
    child = make_symbol("C", "c.C", SymbolType.CLASS, bases=["Base"])
    edges = RelationshipBuilder(set()).build(
        [make_file("a", [first]), make_file("b", [second]), make_file("c", [child])]
    )
    inherited = next(e for e in edges if e.kind is RelationKind.INHERITS)
    assert (inherited.target, inherited.resolved) == ("Base", False)


def test_edges_are_sorted_and_error_files_contribute_nothing():
    failed = FileAnalysis(
        path="bad.py",
        module_name="bad",
        error=FileError(path="bad.py", error_type="syntax", message="bad"),
    )
    module = make_symbol("ok", "ok", SymbolType.MODULE)
    edges = RelationshipBuilder({"ok"}).build([make_file("ok", [module]), failed])
    assert edges == []
    ordered = RelationshipBuilder({"ok"}).build(
        [
            make_file("ok", [module]),
            make_file(
                "ok2",
                [
                    make_symbol("A", "ok2.A", SymbolType.CLASS),
                    make_symbol("B", "ok2.B", SymbolType.CLASS),
                ],
            ),
        ]
    )
    kinds = [(edge.kind.value, edge.source, edge.target) for edge in ordered]
    assert kinds == sorted(kinds)
