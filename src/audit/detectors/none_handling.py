"""Flags a None-defaulted parameter used before any None guard.

Heuristic, line-order based: if the first attribute/subscript/method access
on the parameter happens on an earlier line than the first ``is None``/
``is not None`` check, the access is unguarded. Deliberately conservative to
avoid false positives on more complex control flow.
"""

import ast

from repoagent.analysis.models import CodeSymbol, SymbolType
from repoagent.analysis.results import FileAnalysis
from repoagent.audit.context import AuditContext
from repoagent.domain.audit import (
    CandidateIssue,
    DetectionSource,
    IssueCategory,
    Severity,
    stable_candidate_id,
)

_FUNCTION_TYPES = (SymbolType.FUNCTION, SymbolType.METHOD)


def _guard_lines(tree: ast.AST, target: str) -> list[int]:
    lines = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Compare) and len(node.ops) == 1):
            continue
        names = [node.left, *node.comparators]
        has_target = any(isinstance(n, ast.Name) and n.id == target for n in names)
        has_none = any(isinstance(n, ast.Constant) and n.value is None for n in names)
        if has_target and has_none and isinstance(node.ops[0], ast.Is | ast.IsNot):
            lines.append(node.lineno)
    return lines


def _access_lines(tree: ast.AST, target: str) -> list[int]:
    lines = []
    for node in ast.walk(tree):
        owner = None
        if isinstance(node, ast.Attribute | ast.Subscript):
            owner = node.value
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            owner = node.func.value
        if isinstance(owner, ast.Name) and owner.id == target:
            lines.append(owner.lineno)
    return lines


def _function_node(tree: ast.AST, symbol: CodeSymbol) -> ast.AST | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and (
            node.name == symbol.name
            and symbol.start_line <= node.lineno <= symbol.end_line
        ):
            return node
    return None


class NoneDefaultAccessDetector:
    """Flags a ``None``-defaulted parameter accessed before any None guard."""

    name = "none_default_access"

    def detect(self, context: AuditContext) -> list[CandidateIssue]:
        candidates = []
        for file in context.files():
            tree = context.tree(file.path)
            if tree is None:
                continue
            for symbol in file.symbols:
                if symbol.symbol_type in _FUNCTION_TYPES:
                    candidates.extend(self._check_symbol(file, symbol, tree))
        return candidates

    def _check_symbol(
        self, file: FileAnalysis, symbol: CodeSymbol, tree: ast.AST
    ) -> list[CandidateIssue]:
        candidates = []
        for param in symbol.parameters:
            if param.default != "None":
                continue
            node = _function_node(tree, symbol)
            if node is None:
                continue
            accesses = sorted(_access_lines(node, param.name))
            if not accesses:
                continue
            guards = sorted(_guard_lines(node, param.name))
            if not guards or accesses[0] < guards[0]:
                candidates.append(self._candidate(symbol, param.name, accesses[0]))
        return candidates

    @staticmethod
    def _candidate(symbol: CodeSymbol, param_name: str, line: int) -> CandidateIssue:
        return CandidateIssue(
            id=stable_candidate_id(
                IssueCategory.NONE_HANDLING, symbol.file_path, line, param_name
            ),
            category=IssueCategory.NONE_HANDLING,
            title="Unguarded access on a None-defaulted parameter",
            description=(
                f"`{param_name}` of `{symbol.qualified_name}` defaults to `None` "
                "and is used before any `is None` guard."
            ),
            confidence=0.55,
            severity=Severity.MEDIUM,
            file=symbol.file_path,
            symbol=symbol.qualified_name,
            start_line=line,
            end_line=line,
            detection_source=DetectionSource.AST_NONE_HANDLING,
        )
