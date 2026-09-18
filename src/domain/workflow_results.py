"""Typed results of the web-facing repair and discovery workflows."""

from typing import Literal

from pydantic import Field

from repoagent.analysis.models import AnalysisModel
from repoagent.domain.audit_report import AuditReport
from repoagent.domain.github import RepositoryHandle
from repoagent.domain.investigation import Issue
from repoagent.domain.limits import WorkflowLimits
from repoagent.domain.repair import RepairReport
from repoagent.domain.repair_execution import ValidatedRepairReport
from repoagent.retrieval.persistence import IndexSummary


class WorkflowUsage(AnalysisModel):
    """Provider-reported totals across the whole workflow (0 = not reported)."""

    llm_calls: int = 0
    tokens: int = 0


class RepairWorkflowResult(AnalysisModel):
    workflow: Literal["repair"] = "repair"
    repository: RepositoryHandle
    issue: Issue
    sandbox_validation: bool
    index: IndexSummary | None = None
    report: ValidatedRepairReport | RepairReport
    source_finding: str | None = Field(default=None, max_length=64)
    limits: WorkflowLimits
    usage: WorkflowUsage = Field(default_factory=WorkflowUsage)


class DiscoveryWorkflowResult(AnalysisModel):
    workflow: Literal["discover"] = "discover"
    repository: RepositoryHandle
    report: AuditReport
    limits: WorkflowLimits
    usage: WorkflowUsage = Field(default_factory=WorkflowUsage)
