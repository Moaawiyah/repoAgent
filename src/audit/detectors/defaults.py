"""Mutable default argument detector.

Reads already-extracted ``Parameter.default`` text (an ``ast.unparse``
rendering); no re-parse needed for this check.
"""

import re

from repoagent.analysis.models import CodeSymbol, SymbolType
from repoagent.audit.context import AuditContext
from repoagent.domain.audit import (
    CandidateIssue,
    DetectionSource,
    IssueCategory,
    Severity,
    stable_candidate_id,
)

_MUTABLE = re.compile(r"^(\[|\{|list\(|dict\(|set\()")
_FUNCTION_TYPES = (SymbolType.FUNCTION, SymbolType.METHOD)


class MutableDefaultDetector:
    """Detects ``def f(x=[])``-style mutable default arguments."""

    name = "mutable_default"

    def detect(self, context: AuditContext) -> list[CandidateIssue]:
        candidates = []
        for symbol in context.analysis.symbols:
            if symbol.symbol_type not in _FUNCTION_TYPES:
                continue
            for param in symbol.parameters:
                if param.default and _MUTABLE.match(param.default):
                    candidates.append(self._candidate(symbol, param.name))
        return candidates

    @staticmethod
    def _candidate(symbol: CodeSymbol, param_name: str) -> CandidateIssue:
        return CandidateIssue(
            id=stable_candidate_id(
                IssueCategory.MUTABLE_DEFAULT,
                symbol.file_path,
                symbol.start_line,
                param_name,
            ),
            category=IssueCategory.MUTABLE_DEFAULT,
            title="Mutable default argument",
            description=(
                f"Parameter `{param_name}` of `{symbol.qualified_name}` defaults "
                "to a mutable literal, which is shared and mutated across calls."
            ),
            confidence=0.9,
            severity=Severity.MEDIUM,
            file=symbol.file_path,
            symbol=symbol.qualified_name,
            start_line=symbol.start_line,
            end_line=symbol.end_line,
            detection_source=DetectionSource.AST_MUTABLE_DEFAULT,
        )
