"""Serializable state for the M7 sandboxed repair loop."""

from pydantic import BaseModel, Field

from repoagent.domain.investigation import InvestigationReport
from repoagent.domain.repair import RepairReport
from repoagent.domain.repair_execution import (
    ExecutionStatus,
    RepairAttempt,
    ValidatedRepairReport,
)
from repoagent.domain.sandbox import ValidationPlan
from repoagent.domain.validation import ValidationResult


class RepairLoopLimits(BaseModel):
    """Hard bounds that guarantee the repair loop terminates."""

    max_attempts: int = Field(default=3, ge=1, le=10)
    max_revisions: int = Field(default=2, ge=0, le=5)
    max_reinvestigations: int = Field(default=1, ge=0, le=3)

    @property
    def recursion_limit(self) -> int:
        per_attempt = 5 + self.max_reinvestigations
        return 10 + per_attempt * self.max_attempts


class ExecutionRepairState(BaseModel):
    """Graph state; a set ``status`` means the loop has reached a terminal."""

    task_id: str
    repository: str
    investigation: InvestigationReport
    plan: ValidationPlan
    limits: RepairLoopLimits
    baseline: ValidationResult | None = None
    proposal_report: RepairReport | None = None
    attempts: list[RepairAttempt] = Field(default_factory=list)
    runtime: dict | None = None
    reinvestigations: int = 0
    retrieval_calls: int = 0
    investigations: int = 1
    status: ExecutionStatus | None = None
    error: str | None = None
    report: ValidatedRepairReport | None = None
