"""Detects `open()` results that are never closed and never used as a context.

Heuristic: an `open(...)` call assigned to a plain name, outside a `with`
statement, where no `.close()` call on that name appears anywhere in the
same file. Calls passed directly to another expression (not assigned to a
name) are skipped rather than guessed at.
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


def _with_safe_ids(tree: ast.AST) -> set[int]:
    safe: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.With | ast.AsyncWith):
            safe.update(id(item.context_expr) for item in node.items)
    return safe


def _is_open_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "open"
    )


def _closed_names(tree: ast.AST) -> set[str]:
    names = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "close"
            and isinstance(node.func.value, ast.Name)
        ):
            names.add(node.func.value.id)
    return names


class ResourceHandlingDetector:
    """Detects `open()` calls that are neither a context manager nor closed."""

    name = "resource_handling"

    def detect(self, context: AuditContext) -> list[CandidateIssue]:
        candidates = []
        for file in context.files():
            tree = context.tree(file.path)
            if tree is None:
                continue
            safe = _with_safe_ids(tree)
            closed = _closed_names(tree)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Assign) or id(node.value) in safe:
                    continue
                if not _is_open_call(node.value) or len(node.targets) != 1:
                    continue
                target = node.targets[0]
                if isinstance(target, ast.Name) and target.id not in closed:
                    candidates.append(self._candidate(context, file, node, target.id))
        return candidates

    @staticmethod
    def _candidate(
        context: AuditContext, file: FileAnalysis, node: ast.Assign, name: str
    ) -> CandidateIssue:
        symbol = context.symbol_at(file, node.lineno)
        return CandidateIssue(
            id=stable_candidate_id(
                IssueCategory.RESOURCE_HANDLING, file.path, node.lineno, name
            ),
            category=IssueCategory.RESOURCE_HANDLING,
            title="Possible resource leak",
            description=(
                f"`{name} = open(...)` is never used as a context manager and "
                f"no `{name}.close()` call was found in this file."
            ),
            confidence=0.65,
            severity=Severity.HIGH,
            file=file.path,
            symbol=symbol.qualified_name if symbol else None,
            start_line=node.lineno,
            end_line=getattr(node, "end_lineno", None) or node.lineno,
            detection_source=DetectionSource.AST_RESOURCE,
        )
