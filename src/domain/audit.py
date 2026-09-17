"""Framework-free audit domain models: candidate issues and identities.

Discovery is deterministic (AST/graph detectors); verification is the only
LLM-touched step and lives in ``agent.audit_verifier``. This module never
imports LLM/provider code.
"""

import hashlib
from enum import StrEnum

from pydantic import Field

from repoagent.analysis.models import AnalysisModel
from repoagent.domain.evidence import EvidenceItem
from repoagent.domain.investigation import Issue


class IssueCategory(StrEnum):
    """What kind of problem a candidate represents."""

    EXCEPTION_HANDLING = "exception_handling"
    DEAD_CODE = "dead_code"
    MUTABLE_DEFAULT = "mutable_default"
    RESOURCE_HANDLING = "resource_handling"
    SUBPROCESS_RISK = "subprocess_risk"
    NONE_HANDLING = "none_handling"
    CIRCULAR_DEPENDENCY = "circular_dependency"
    COUPLING = "coupling"
    TODO_MARKER = "todo_marker"
    LINT = "lint"


class DetectionSource(StrEnum):
    """Which detector produced a candidate."""

    AST_EXCEPTION = "ast_exception"
    AST_MUTABLE_DEFAULT = "ast_mutable_default"
    AST_RESOURCE = "ast_resource"
    AST_SUBPROCESS = "ast_subprocess"
    AST_NONE_HANDLING = "ast_none_handling"
    AST_DEAD_CODE = "ast_dead_code"
    AST_TODO = "ast_todo"
    GRAPH_CIRCULAR_DEPENDENCY = "graph_circular_dependency"
    GRAPH_COUPLING = "graph_coupling"
    RUFF = "ruff"


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class VerificationStatus(StrEnum):
    """Lifecycle of a candidate; only the verifier assigns a terminal state."""

    PENDING = "pending"
    VERIFIED = "verified"
    UNCERTAIN = "uncertain"
    REJECTED = "rejected"


def stable_candidate_id(
    category: IssueCategory, file: str, start_line: int, detail: str
) -> str:
    """Deterministic identity so repeated runs report the same candidate."""
    payload = f"{category}:{file}:{start_line}:{detail}"
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


class VerifierFinding(AnalysisModel):
    """Structured verifier output; concise observable rationale only."""

    status: VerificationStatus
    reasoning: str = Field(min_length=1, max_length=800)
    supporting_evidence: list[str] = Field(default_factory=list, max_length=8)
    contradicting_evidence: list[str] = Field(default_factory=list, max_length=8)
    confidence: float = Field(ge=0.0, le=1.0)
    recommended_verification: str = Field(default="", max_length=400)


class CandidateIssue(AnalysisModel):
    """A discovered potential issue with evidence and verification state."""

    id: str
    category: IssueCategory
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2000)
    confidence: float = Field(ge=0.0, le=1.0)
    severity: Severity
    file: str
    symbol: str | None = None
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    detection_source: DetectionSource
    evidence: list[EvidenceItem] = Field(default_factory=list)
    status: VerificationStatus = VerificationStatus.PENDING
    verification: VerifierFinding | None = None

    def to_issue(self) -> Issue:
        """Convert a verified candidate into the existing repair `Issue`."""
        location = f"{self.file}:{self.start_line}-{self.end_line}"
        symbol_note = f" in `{self.symbol}`" if self.symbol else ""
        reasoning = self.verification.reasoning if self.verification else ""
        return Issue(
            title=self.title,
            description=(
                f"{self.description}\n\nLocation: {location}{symbol_note}\n"
                f"Detected by: {self.detection_source}\n"
                f"Verifier reasoning: {reasoning}"
            ),
            observed_behavior=self.description,
        )
