"""RepairGraph: the top-level LangGraph repair workflow.

    START → load_repository → analyze_repository → repair → finalize → END

``repair`` delegates to the existing, already-bounded LangGraph subgraphs —
the Investigator (retrieve ⇄ refine until enough evidence), the M6
Developer → static validator → Reviewer loop (REVISE → Developer, REJECT →
end), and the M7 sandbox loop (Docker PASS → VALIDATED, FAIL → Failure
Analyzer → Developer retry). No repair logic is duplicated here; this graph
adds repository loading, analysis, progress, and truthful stage outcomes.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from repoagent.domain.errors import RepoAgentError
from repoagent.domain.github import RepositoryHandle
from repoagent.domain.investigation import Issue
from repoagent.domain.repair import RepairReport
from repoagent.domain.repair_execution import ValidatedRepairReport
from repoagent.domain.workflow import StageStatus
from repoagent.retrieval.persistence import IndexSummary
from repoagent.workflows.guards import required
from repoagent.workflows.outcomes import CURRENT, repair_outcomes
from repoagent.workflows.progress import (
    REPAIR_NODE_STAGES,
    StageSink,
    WorkflowProgressHandler,
    ignore_stage,
)

AnyRepairReport = ValidatedRepairReport | RepairReport
NODES = {
    **REPAIR_NODE_STAGES,
    "load_repository": "repository",
    "analyze_repository": "analysis",
    "finalize": "report",
}


@dataclass(frozen=True)
class RepairPorts:
    """Existing capabilities the workflow composes (wired by the SDK)."""

    load: Callable[[str], RepositoryHandle]
    index: Callable[[Path], IndexSummary]
    repair: Callable[[Path, Issue, bool], AnyRepairReport]


class RepairWorkflowState(BaseModel):
    source: str
    issue: Issue
    execute: bool
    handle: RepositoryHandle | None = None
    index: IndexSummary | None = None
    report: AnyRepairReport | None = None


class RepairGraph:
    def __init__(self, ports: RepairPorts, sink: StageSink = ignore_stage) -> None:
        self._ports, self._sink = ports, sink
        self._current = "repository"
        self._graph = self._build()

    def _record(self, key: str, status: StageStatus, detail: str = "") -> None:
        if status == StageStatus.RUNNING and key != "report":
            self._current = key
        self._sink(key, status, detail)

    def _load(self, state: RepairWorkflowState) -> dict:
        handle = self._ports.load(state.source)
        revision = handle.commit[:12] if handle.commit else "local snapshot"
        self._record("repository", StageStatus.DONE, f"{handle.name} @ {revision}")
        return {"handle": handle}

    def _analyze(self, state: RepairWorkflowState) -> dict:
        summary = self._ports.index(Path(required(state.handle, "handle").path))
        files = f"{summary.python_files} Python files, {summary.chunk_count} chunks"
        self._record("analysis", StageStatus.DONE, files)
        edges = f"{summary.node_count} nodes, {summary.edge_count} edges"
        self._record("graph", StageStatus.DONE, edges)
        return {"index": summary}

    def _repair(self, state: RepairWorkflowState) -> dict:
        path = Path(required(state.handle, "handle").path)
        return {"report": self._ports.repair(path, state.issue, state.execute)}

    def _finalize(self, state: RepairWorkflowState) -> dict:
        report = state.report
        if report is None:
            raise RepoAgentError("Workflow state is missing report")
        for key, status, detail in repair_outcomes(report):
            self._record(self._current if key == CURRENT else key, status, detail)
        self._record("report", StageStatus.DONE, report.status.value)
        return {}

    def _build(self):
        graph = StateGraph(RepairWorkflowState)
        graph.add_node("load_repository", self._load)
        graph.add_node("analyze_repository", self._analyze)
        graph.add_node("repair", self._repair)
        graph.add_node("finalize", self._finalize)
        graph.add_edge(START, "load_repository")
        graph.add_edge("load_repository", "analyze_repository")
        graph.add_edge("analyze_repository", "repair")
        graph.add_edge("repair", "finalize")
        graph.add_edge("finalize", END)
        return graph.compile()

    def run(self, source: str, issue: Issue, execute: bool) -> RepairWorkflowState:
        handler = WorkflowProgressHandler(NODES, self._record)
        state = RepairWorkflowState(source=source, issue=issue, execute=execute)
        final = self._graph.invoke(state, config={"callbacks": [handler]})
        return RepairWorkflowState.model_validate(final)
