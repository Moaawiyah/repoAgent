"""Scans source text for TODO/FIXME/XXX/HACK markers.

Purely textual: the marker's presence on a `#` comment line is itself the
evidence, so confidence is fixed at 1.0 (this is a fact, not an inference).
Marker text is repository content and is never treated as an instruction.
"""

import re

from repoagent.audit.context import AuditContext
from repoagent.domain.audit import (
    CandidateIssue,
    DetectionSource,
    IssueCategory,
    Severity,
    stable_candidate_id,
)

_MARKER = re.compile(r"#.*\b(TODO|FIXME|XXX|HACK)\b[:\s]*(.*)")
MAX_NOTE_CHARS = 200


class TodoMarkerDetector:
    """Flags TODO/FIXME/XXX/HACK comments as tracked follow-up debt."""

    name = "todo_marker"

    def detect(self, context: AuditContext) -> list[CandidateIssue]:
        candidates = []
        for file in context.files():
            source = context.source(file.path)
            if not source:
                continue
            for line_number, line in enumerate(source.splitlines(), start=1):
                match = _MARKER.search(line)
                if match:
                    candidates.append(self._candidate(file.path, line_number, match))
        return candidates

    @staticmethod
    def _candidate(
        file_path: str, line_number: int, match: re.Match[str]
    ) -> CandidateIssue:
        marker, note = match.group(1), match.group(2).strip()[:MAX_NOTE_CHARS]
        return CandidateIssue(
            id=stable_candidate_id(
                IssueCategory.TODO_MARKER, file_path, line_number, marker
            ),
            category=IssueCategory.TODO_MARKER,
            title=f"{marker} marker",
            description=f"Unresolved `{marker}` comment: {note or '(no note)'}",
            confidence=1.0,
            severity=Severity.LOW,
            file=file_path,
            symbol=None,
            start_line=line_number,
            end_line=line_number,
            detection_source=DetectionSource.AST_TODO,
        )
