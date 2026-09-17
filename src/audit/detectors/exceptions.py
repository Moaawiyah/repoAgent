"""Detects broad exception handlers that silently swallow errors.

Flags only the precise anti-pattern: a bare/broad ``except`` whose entire
body is ``pass``, ``continue``, or ``...`` — no logging, no re-raise, no
other statement. Anything else (logging, cleanup, re-raise) is left alone to
avoid noisy false positives.
"""

import ast

from repoagent.analysis.results import FileAnalysis
from repoagent.audit.context import AuditContext
from repoagent.domain.audit import (
    CandidateIssue,
    DetectionSource,
    IssueCategory,
    Severity,
    stable_candidate_id,
)

_BROAD_NAMES = {"Exception", "BaseException"}
_SWALLOW_TYPES = (ast.Pass, ast.Continue)


def _is_broad(handler: ast.ExceptHandler) -> bool:
    if handler.type is None:
        return True
    return isinstance(handler.type, ast.Name) and handler.type.id in _BROAD_NAMES


def _swallows(body: list[ast.stmt]) -> bool:
    if len(body) != 1:
        return False
    statement = body[0]
    if isinstance(statement, _SWALLOW_TYPES):
        return True
    return (
        isinstance(statement, ast.Expr)
        and isinstance(statement.value, ast.Constant)
        and statement.value.value is Ellipsis
    )


class BroadExceptionDetector:
    """Detects bare/broad ``except`` blocks that swallow all errors."""

    name = "broad_exception"

    def detect(self, context: AuditContext) -> list[CandidateIssue]:
        candidates = []
        for file in context.files():
            tree = context.tree(file.path)
            if tree is None:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ExceptHandler) and _is_broad(node):
                    if _swallows(node.body):
                        candidates.append(self._candidate(file, node, context))
        return candidates

    @staticmethod
    def _candidate(
        file: FileAnalysis, node: ast.ExceptHandler, context: AuditContext
    ) -> CandidateIssue:
        symbol = context.symbol_at(file, node.lineno)
        end_line = getattr(node, "end_lineno", None) or node.lineno
        detail = f"except:{node.lineno}"
        return CandidateIssue(
            id=stable_candidate_id(
                IssueCategory.EXCEPTION_HANDLING, file.path, node.lineno, detail
            ),
            category=IssueCategory.EXCEPTION_HANDLING,
            title="Broad exception handler swallows errors",
            description=(
                "A bare or broad `except` block silently discards the error "
                "(body is only `pass`/`continue`/`...`), hiding failures."
            ),
            confidence=0.8,
            severity=Severity.MEDIUM,
            file=file.path,
            symbol=symbol.qualified_name if symbol else None,
            start_line=node.lineno,
            end_line=end_line,
            detection_source=DetectionSource.AST_EXCEPTION,
        )
