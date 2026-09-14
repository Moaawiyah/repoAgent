"""Investigation domain models: issue, hypotheses, report, limits.

Framework-free (no LangGraph dependency) so the report remains useful
regardless of orchestration. Evidence lives in ``domain.evidence``.
"""

import hashlib
from enum import StrEnum

from pydantic import Field, field_validator, model_validator

from repoagent.analysis.models import AnalysisModel
from repoagent.domain.evidence import EvidenceItem, EvidenceRelevance
from repoagent.domain.investigation_limits import InvestigationLimits
from repoagent.domain.issue_analysis import IssueAnalysis
from repoagent.retrieval.models import GraphHop

__all__ = ["InvestigationLimits", "EvidenceItem", "EvidenceRelevance", "GraphHop"]


def hypothesis_identifier(statement: str) -> str:
    """Deterministic hypothesis identity derived from the statement."""
    return hashlib.sha256(statement.encode()).hexdigest()[:8]


class TerminationReason(StrEnum):
    """Why an investigation ended."""

    CONFIDENT_ROOT_CAUSE = "confident_root_cause"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    MAX_ITERATIONS = "max_iterations"
    INVALID_ISSUE = "invalid_issue"
    PROVIDER_ERROR = "provider_error"
    MAX_QUERIES = "max_queries"
    MAX_TOOL_CALLS = "max_tool_calls"
    MAX_EVIDENCE = "max_evidence"


class HypothesisStatus(StrEnum):
    """Lifecycle of a root-cause hypothesis."""

    PROPOSED = "proposed"
    EVALUATED = "evaluated"


class Issue(AnalysisModel):
    """A bug report; only free-text description is required."""

    description: str = Field(min_length=1, max_length=6000)
    title: str | None = Field(default=None, max_length=500)
    expected_behavior: str | None = Field(default=None, max_length=2000)
    observed_behavior: str | None = Field(default=None, max_length=2000)
    error_message: str | None = Field(default=None, max_length=2000)
    stack_trace: str | None = Field(default=None, max_length=2000)

    @field_validator("description")
    @classmethod
    def _require_description(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("A nonempty issue description is required")
        return text


class RootCauseHypothesis(AnalysisModel):
    """A root-cause explanation grounded in evidence identifiers."""

    statement: str = Field(max_length=1000)
    hypothesis_id: str = ""
    confidence: float = Field(ge=0.0, le=1.0)
    supporting_evidence: list[str] = Field(default_factory=list)
    contradicting_evidence: list[str] = Field(default_factory=list)
    affected_symbols: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    status: HypothesisStatus = HypothesisStatus.PROPOSED

    @model_validator(mode="before")
    @classmethod
    def _fill_identifier(cls, data):
        if isinstance(data, dict) and not data.get("hypothesis_id"):
            statement = data.get("statement") or ""
            if statement:
                return {**data, "hypothesis_id": hypothesis_identifier(statement)}
        return data


class InvestigationTraceEntry(AnalysisModel):
    """One observable investigation action; no hidden reasoning."""

    iteration: int
    action: str
    query: str | None = None
    found_symbols: list[str] = Field(default_factory=list)
    decision: str
    rationale: str = Field(default="", max_length=500)


class LLMUsage(AnalysisModel):
    """Aggregate provider usage metadata."""

    model: str = ""
    estimated_context_tokens: int = 0
    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0


class InvestigationReport(AnalysisModel):
    """The structured, evidence-grounded investigation outcome."""

    task_id: str
    repository: str
    issue: Issue
    issue_summary: str
    likely_affected_area: str = ""
    evidence: list[EvidenceItem] = Field(default_factory=list)
    hypotheses: list[RootCauseHypothesis] = Field(default_factory=list)
    primary_hypothesis_id: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    open_questions: list[str] = Field(default_factory=list)
    relevant_files: list[str] = Field(default_factory=list)
    relevant_symbols: list[str] = Field(default_factory=list)
    graph_paths: list[list[GraphHop]] = Field(default_factory=list)
    termination_reason: TerminationReason = TerminationReason.INSUFFICIENT_EVIDENCE
    trace: list[InvestigationTraceEntry] = Field(default_factory=list)
    iterations: int = 0
    usage: LLMUsage = Field(default_factory=LLMUsage)
    issue_analysis: IssueAnalysis | None = None
    queries: list[str] = Field(default_factory=list)
    tool_calls: int = 0
    error: str | None = None

    @property
    def primary_hypothesis(self) -> RootCauseHypothesis | None:
        """The ranked-primary hypothesis, if any."""
        return next(
            (
                hypothesis
                for hypothesis in self.hypotheses
                if hypothesis.hypothesis_id == self.primary_hypothesis_id
            ),
            None,
        )
