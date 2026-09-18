"""Framework-free workflow stage models shared by jobs, SDK and web UI.

A stage is an observable, user-facing step of a LangGraph workflow. Stage
status is derived from real node execution; it never claims work that did
not happen.
"""

from enum import StrEnum

from pydantic import Field

from repoagent.analysis.models import AnalysisModel


class WorkflowKind(StrEnum):
    REPAIR = "repair"
    DISCOVER = "discover"


class StageStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


class WorkflowStage(AnalysisModel):
    """One observable stage; ``visits`` counts loop re-entries."""

    key: str = Field(pattern=r"^[a-z_]{1,40}$")
    label: str = Field(max_length=80)
    status: StageStatus = StageStatus.PENDING
    visits: int = Field(default=0, ge=0)
    detail: str = Field(default="", max_length=300)


def _stages(*pairs: tuple[str, str]) -> tuple[WorkflowStage, ...]:
    return tuple(WorkflowStage(key=key, label=label) for key, label in pairs)


REPAIR_STAGES = _stages(
    ("repository", "Repository loaded"),
    ("analysis", "Static analysis"),
    ("graph", "Knowledge graph"),
    ("retrieval", "Retrieval"),
    ("investigator", "Investigator"),
    ("developer", "Developer"),
    ("static_validation", "Static validation"),
    ("reviewer", "Reviewer"),
    ("docker_validation", "Docker validation"),
    ("failure_analysis", "Failure analyzer"),
    ("report", "Report"),
)

DISCOVERY_STAGES = _stages(
    ("repository", "Repository loaded"),
    ("analysis", "Repository analysis"),
    ("static_detectors", "Static detectors"),
    ("graph_detectors", "Graph detectors"),
    ("deduplicate", "Deduplicate candidates"),
    ("evidence", "RAG evidence enrichment"),
    ("verifier", "Issue verifier"),
    ("report", "Results"),
)


def initial_stages(kind: WorkflowKind) -> list[WorkflowStage]:
    stages = REPAIR_STAGES if kind == WorkflowKind.REPAIR else DISCOVERY_STAGES
    return [stage.model_copy() for stage in stages]


def advance(
    stages: list[WorkflowStage], key: str, status: StageStatus, detail: str = ""
) -> list[WorkflowStage]:
    """Return updated stages; entering a stage completes any other running one.

    Workflows execute one node at a time, so a new running stage means the
    previously running stage finished (loops re-enter and bump ``visits``).
    """
    updated = []
    for stage in stages:
        if stage.key == key:
            visits = stage.visits + (1 if status == StageStatus.RUNNING else 0)
            stage = stage.model_copy(
                update={
                    "status": status,
                    "visits": visits,
                    "detail": detail[:300] or stage.detail,
                }
            )
        elif status == StageStatus.RUNNING and stage.status == StageStatus.RUNNING:
            stage = stage.model_copy(update={"status": StageStatus.DONE})
        updated.append(stage)
    return updated


def settle(stages: list[WorkflowStage], succeeded: bool) -> list[WorkflowStage]:
    """Close a finished workflow: running → done/failed, pending → skipped."""
    finished = StageStatus.DONE if succeeded else StageStatus.FAILED
    closing = {StageStatus.RUNNING: finished, StageStatus.PENDING: StageStatus.SKIPPED}
    return [
        stage.model_copy(update={"status": closing[stage.status]})
        if stage.status in closing
        else stage
        for stage in stages
    ]
