"""Detects statements that can never execute after an unconditional exit.

Only flags a statement immediately following a bare `return`/`raise`/
`break`/`continue` within the very same statement block — Python guarantees
these never fall through, so this is a near-certain finding, not a heuristic.
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

_EXIT_TYPES = (ast.Return, ast.Raise, ast.Break, ast.Continue)


def _blocks(node: ast.AST):
    for child in ast.iter_child_nodes(node):
        for field in ("body", "orelse", "finalbody"):
            block = getattr(child, field, None)
            if isinstance(block, list) and block and isinstance(block[0], ast.stmt):
                yield block
        yield from _blocks(child)


class DeadCodeDetector:
    """Flags unreachable statements after an unconditional block exit."""

    name = "dead_code"

    def detect(self, context: AuditContext) -> list[CandidateIssue]:
        candidates = []
        for file in context.files():
            tree = context.tree(file.path)
            if tree is None:
                continue
            for block in _blocks(tree):
                for index, statement in enumerate(block[:-1]):
                    if isinstance(statement, _EXIT_TYPES):
                        dead = block[index + 1]
                        candidates.append(self._candidate(context, file, dead))
        return candidates

    @staticmethod
    def _candidate(
        context: AuditContext, file: FileAnalysis, node: ast.stmt
    ) -> CandidateIssue:
        symbol = context.symbol_at(file, node.lineno)
        return CandidateIssue(
            id=stable_candidate_id(
                IssueCategory.DEAD_CODE, file.path, node.lineno, "unreachable"
            ),
            category=IssueCategory.DEAD_CODE,
            title="Unreachable code",
            description=(
                "This statement follows an unconditional return/raise/break/"
                "continue in the same block and can never execute."
            ),
            confidence=0.9,
            severity=Severity.LOW,
            file=file.path,
            symbol=symbol.qualified_name if symbol else None,
            start_line=node.lineno,
            end_line=getattr(node, "end_lineno", None) or node.lineno,
            detection_source=DetectionSource.AST_DEAD_CODE,
        )
