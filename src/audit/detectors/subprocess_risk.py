"""Detects risky subprocess/shell usage: `shell=True` or built-up commands."""

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

_SUBPROCESS_FUNCS = {"run", "call", "check_call", "check_output", "Popen"}
_OS_SHELL_FUNCS = {"system", "popen"}


def _target_name(func: ast.expr) -> tuple[str | None, str | None]:
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        return func.value.id, func.attr
    return None, None


def _has_shell_true(call: ast.Call) -> bool:
    return any(
        keyword.arg == "shell"
        and isinstance(keyword.value, ast.Constant)
        and keyword.value.value is True
        for keyword in call.keywords
    )


class SubprocessRiskDetector:
    """Flags `subprocess`/`os` shell execution with `shell=True`."""

    name = "subprocess_risk"

    def detect(self, context: AuditContext) -> list[CandidateIssue]:
        candidates = []
        for file in context.files():
            tree = context.tree(file.path)
            if tree is None:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and self._is_risky(node):
                    candidates.append(self._candidate(context, file, node))
        return candidates

    @staticmethod
    def _is_risky(call: ast.Call) -> bool:
        module, attr = _target_name(call.func)
        if module == "subprocess" and attr in _SUBPROCESS_FUNCS:
            return _has_shell_true(call)
        if module == "os" and attr in _OS_SHELL_FUNCS:
            return True
        return False

    @staticmethod
    def _candidate(
        context: AuditContext, file: FileAnalysis, node: ast.Call
    ) -> CandidateIssue:
        symbol = context.symbol_at(file, node.lineno)
        _, attr = _target_name(node.func)
        return CandidateIssue(
            id=stable_candidate_id(
                IssueCategory.SUBPROCESS_RISK, file.path, node.lineno, attr or ""
            ),
            category=IssueCategory.SUBPROCESS_RISK,
            title="Risky subprocess/shell invocation",
            description=(
                f"Call to `{attr}` executes a shell, which is vulnerable to "
                "command injection if any argument includes untrusted input."
            ),
            confidence=0.8,
            severity=Severity.HIGH,
            file=file.path,
            symbol=symbol.qualified_name if symbol else None,
            start_line=node.lineno,
            end_line=getattr(node, "end_lineno", None) or node.lineno,
            detection_source=DetectionSource.AST_SUBPROCESS,
        )
