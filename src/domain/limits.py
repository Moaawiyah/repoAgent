"""One consolidated, deterministic view of every workflow bound.

These are hard limits enforced by code (graph recursion limits, loop
counters, the budgeted provider, sandbox limits) — there is no LLM
"watchdog" agent deciding when to stop.
"""

from pydantic import Field

from repoagent.analysis.models import AnalysisModel
from repoagent.config import Settings


class WorkflowLimits(AnalysisModel):
    investigation_iterations: int = Field(ge=1, le=10)
    repair_attempts: int = Field(ge=1, le=10)
    review_revisions: int = Field(ge=0, le=5)
    reinvestigations: int = Field(ge=0, le=3)
    discovery_candidates: int = Field(ge=1, le=200)
    llm_calls: int = Field(ge=1, le=5000)
    tokens: int | None = Field(default=None, ge=1000)
    sandbox_timeout_seconds: int = Field(gt=0)
    sandbox_output_bytes: int = Field(ge=1024)
    task_timeout_seconds: int = Field(ge=30)

    @classmethod
    def from_settings(cls, settings: Settings) -> "WorkflowLimits":
        return cls(
            investigation_iterations=settings.investigation_max_iterations,
            repair_attempts=settings.repair_max_attempts,
            review_revisions=settings.repair_max_revisions,
            reinvestigations=settings.repair_max_reinvestigations,
            discovery_candidates=settings.discovery_max_candidates,
            llm_calls=settings.workflow_max_llm_calls,
            tokens=settings.workflow_max_tokens,
            sandbox_timeout_seconds=settings.execution_timeout,
            sandbox_output_bytes=settings.sandbox_max_output_bytes,
            task_timeout_seconds=settings.workflow_task_timeout,
        )
