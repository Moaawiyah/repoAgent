"""Serializable state used exclusively by the M6 repair graph."""

from pydantic import BaseModel, Field

from repoagent.domain.investigation import InvestigationReport
from repoagent.domain.repair import (
    PatchProposal,
    PatchReview,
    RepairReport,
    StaticValidation,
)


class RepairState(BaseModel):
    """Mutable graph state; domain report types remain LangGraph-free."""

    repository: str
    investigation: InvestigationReport
    max_revisions: int = Field(ge=0, le=5)
    proposal: PatchProposal | None = None
    validation: StaticValidation | None = None
    reviews: list[PatchReview] = Field(default_factory=list)
    feedback: str = ""
    revisions: int = 0
    report: RepairReport | None = None
    error: str | None = None
