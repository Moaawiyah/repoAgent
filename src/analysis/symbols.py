"""AST visitor producing typed code symbols and structural imports."""

import ast

from repoagent.analysis.models import (
    CallSite,
    CodeSymbol,
    ImportedName,
    ImportInfo,
    SymbolType,
)
from repoagent.analysis.params import decorators, extract_parameters, unparse


class ModuleVisitor(ast.NodeVisitor):
    """Extracts symbols and imports from one parsed module."""

    def __init__(self, module: str, file_path: str, total_lines: int) -> None:
        self._module = module
        self._file_path = file_path
        self._total_lines = total_lines
        self._stack: list[CodeSymbol] = []
        self.symbols: list[CodeSymbol] = []
        self.imports: list[ImportInfo] = []
        self.calls: list[CallSite] = []

    def visit_Module(self, node: ast.Module) -> None:
        self.symbols.append(
            CodeSymbol(
                name=self._module,
                qualified_name=self._module,
                file_path=self._file_path,
                symbol_type=SymbolType.MODULE,
                start_line=1,
                end_line=max(self._total_lines, 1),
                docstring=ast.get_docstring(node, clean=True),
            )
        )
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        symbol = self._symbol(SymbolType.CLASS, node).model_copy(
            update={
                "bases": [unparse(base) for base in node.bases],
                "decorators": decorators(node),
            }
        )
        self._enter(symbol, node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._function(node, is_async=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._function(node, is_async=True)

    def visit_Import(self, node: ast.Import) -> None:
        self.imports.extend(
            ImportInfo(module=alias.name, line=node.lineno) for alias in node.names
        )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self.imports.append(
            ImportInfo(
                module="." * node.level + (node.module or ""),
                line=node.lineno,
                names=[
                    ImportedName(name=alias.name, alias=alias.asname)
                    for alias in node.names
                ],
            )
        )

    def visit_Call(self, node: ast.Call) -> None:
        try:
            expression = ast.unparse(node.func)
        except (ValueError, AttributeError):
            expression = ""
        if expression:
            caller = self._stack[-1].qualified_name if self._stack else self._module
            self.calls.append(
                CallSite(caller=caller, expression=expression, line=node.lineno)
            )
        self.generic_visit(node)

    def _function(self, node, *, is_async: bool) -> None:
        symbol_type = SymbolType.METHOD if self._in_class() else SymbolType.FUNCTION
        symbol = self._symbol(symbol_type, node).model_copy(
            update={
                "is_async": is_async,
                "parameters": extract_parameters(node),
                "return_annotation": unparse(node.returns),
                "decorators": decorators(node),
            }
        )
        self._enter(symbol, node)

    def _enter(self, symbol: CodeSymbol, node) -> None:
        self.symbols.append(symbol)
        self._stack.append(symbol)
        try:
            self.generic_visit(node)
        finally:
            self._stack.pop()

    def _symbol(self, symbol_type: SymbolType, node) -> CodeSymbol:
        parent = self._stack[-1] if self._stack else None
        return CodeSymbol(
            name=node.name,
            qualified_name=self._qualified(node.name),
            file_path=self._file_path,
            symbol_type=symbol_type,
            start_line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            parent=parent.qualified_name if parent else None,
            docstring=ast.get_docstring(node, clean=True),
        )

    def _qualified(self, name: str) -> str:
        prefix = self._stack[-1].qualified_name if self._stack else self._module
        return f"{prefix}.{name}"

    def _in_class(self) -> bool:
        return bool(self._stack) and self._stack[-1].symbol_type is SymbolType.CLASS
