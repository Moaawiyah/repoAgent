"""Python AST extraction: symbols, methods, async, imports, and errors."""

import pytest

from repoagent.analysis import python_ast
from repoagent.analysis.models import SymbolType
from repoagent.analysis.python_ast import PythonAnalyzer, module_name

SOURCE = '''\
"""Module documentation."""

import os
from collections import OrderedDict


class UserService(BaseService):
    """Manage users."""

    def authenticate(self, username: str, password: str = "x") -> bool:
        """Check credentials."""
        return True

    async def load(self, *args, **kwargs):
        pass


@staticmethod
def helper(a, /, b: int = 2, *, c: str):
    """Helper."""
    return c
'''


def analyze(tmp_path, source, name="sample.py", **kwargs):
    path = tmp_path / name
    path.write_text(source, **kwargs)
    return PythonAnalyzer().analyze(name, path)


def by_name(analysis, name):
    return next(s for s in analysis.symbols if s.name == name)


def test_module_symbol_and_docstring(tmp_path):
    analysis = analyze(tmp_path, SOURCE)
    module = analysis.symbols[0]
    assert module.symbol_type is SymbolType.MODULE
    assert module.qualified_name == "sample"
    assert module.start_line == 1 and module.end_line == 21
    assert module.docstring == "Module documentation."
    assert analysis.line_count == 21


def test_class_extraction_with_bases_and_lines(tmp_path):
    service = by_name(analyze(tmp_path, SOURCE), "UserService")
    assert service.symbol_type is SymbolType.CLASS
    assert service.qualified_name == "sample.UserService"
    assert service.bases == ["BaseService"]
    assert service.start_line == 7 and service.end_line == 15
    assert service.parent is None


def test_method_parameters_annotations_and_defaults(tmp_path):
    method = by_name(analyze(tmp_path, SOURCE), "authenticate")
    assert method.symbol_type is SymbolType.METHOD
    assert method.parent == "sample.UserService"
    assert method.return_annotation == "bool"
    assert method.docstring == "Check credentials."
    assert [(p.name, p.annotation, p.default, p.kind) for p in method.parameters] == [
        ("self", None, None, "positional_or_keyword"),
        ("username", "str", None, "positional_or_keyword"),
        ("password", "str", "'x'", "positional_or_keyword"),
    ]
    assert method.start_line == 10 and method.end_line == 12


def test_async_method_and_variadic_parameters(tmp_path):
    load = by_name(analyze(tmp_path, SOURCE), "load")
    assert load.symbol_type is SymbolType.METHOD and load.is_async
    kinds = {p.name: p.kind for p in load.parameters}
    assert kinds == {
        "self": "positional_or_keyword",
        "args": "var_positional",
        "kwargs": "var_keyword",
    }


def test_positional_only_keyword_only_and_decorators(tmp_path):
    helper = by_name(analyze(tmp_path, SOURCE), "helper")
    assert helper.symbol_type is SymbolType.FUNCTION
    assert helper.decorators == ["staticmethod"]
    assert [(p.name, p.default, p.kind) for p in helper.parameters] == [
        ("a", None, "positional_only"),
        ("b", "2", "positional_or_keyword"),
        ("c", None, "keyword_only"),
    ]


def test_import_statements_are_structural(tmp_path):
    imports = {imp.module: imp for imp in analyze(tmp_path, SOURCE).imports}
    assert imports["os"].names == []
    assert [n.name for n in imports["collections"].names] == ["OrderedDict"]
    assert imports["os"].line == 3


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("app/__init__.py", "app"),
        ("app/sub/service.py", "app.sub.service"),
        ("tool.py", "tool"),
        ("__init__.py", "__init__"),
    ],
)
def test_module_names(path, expected):
    assert module_name(path) == expected


def test_syntax_error_is_recorded_without_raising(tmp_path):
    analysis = analyze(tmp_path, "def broken(:\n    pass\n", name="bad.py")
    assert analysis.symbols == [] and analysis.imports == []
    assert analysis.error.error_type == "syntax"
    assert analysis.error.path == "bad.py"


def test_encoding_and_unreadable_errors(tmp_path):
    analysis = analyze(tmp_path, "", name="raw.py")
    (tmp_path / "raw.py").write_bytes(b"# \xff\xfe\n")
    encoding = PythonAnalyzer().analyze("raw.py", tmp_path / "raw.py")
    assert encoding.error.error_type == "encoding"
    unreadable = PythonAnalyzer().analyze("directory.py", tmp_path)
    assert unreadable.error.error_type == "unreadable"
    assert analysis is not None


def test_oversized_files_are_skipped(tmp_path, monkeypatch):
    monkeypatch.setattr(python_ast, "MAX_SOURCE_BYTES", 4)
    analysis = analyze(tmp_path, "value = 12345\n")
    assert analysis.error.error_type == "too_large"


def test_target_syntax_warnings_are_not_emitted(recwarn, capsys):
    from repoagent.analysis.python_ast import parse_untrusted

    module = parse_untrusted('PATTERN = "\\d+"\n', "requests/api.py")
    assert module.body and not recwarn.list
    assert "SyntaxWarning" not in capsys.readouterr().err
