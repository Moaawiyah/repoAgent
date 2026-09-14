"""Validated investigation state; domain values remain framework-independent."""

from pydantic import BaseModel, Field

from repoagent.ai.models import IssueAnalysis
from repoagent.domain.evidence import EvidenceItem
from repoagent.domain.investigation import (
    InvestigationLimits,
    InvestigationReport,
    InvestigationTraceEntry,
    Issue,
    LLMUsage,
    RootCauseHypothesis,
)


class InvestigationState(BaseModel):
    repository: str
    task_id: str
    issue: Issue
    limits: InvestigationLimits
    top_k: int = Field(ge=1, le=10)
    issue_analysis: IssueAnalysis | None = None
    pending_queries: list[str] = Field(default_factory=list)
    next_queries: list[str] = Field(default_factory=list)
    executed_queries: list[str] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    hypotheses: list[RootCauseHypothesis] = Field(default_factory=list)
    current_iteration: int = 0
    confidence: float = 0.0
    enough_evidence: bool = False
    primary_hypothesis_id: str | None = None
    termination: str | None = None
    report: InvestigationReport | None = None
    error: str | None = None
    usage: LLMUsage = Field(default_factory=LLMUsage)
    trace: list[InvestigationTraceEntry] = Field(default_factory=list)
    tool_calls: int = 0
