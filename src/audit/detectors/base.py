"""Detector interface shared by every deterministic audit detector."""

from typing import Protocol

from repoagent.audit.context import AuditContext
from repoagent.domain.audit import CandidateIssue


class Detector(Protocol):
    """One focused, independently testable detection rule."""

    name: str

    def detect(self, context: AuditContext) -> list[CandidateIssue]:
        """Return candidates backed by concrete repository evidence."""
        ...
