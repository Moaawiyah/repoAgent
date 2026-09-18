"""DiscoveryGraph: deterministic detection first, LLM verification last.

    START → load_repository → analyze_repository → static_detectors
          → graph_detectors → deduplicate → [candidates?] → enrich_evidence
          → verify → results → END            (no candidates → results)

Every finding ends VERIFIED / UNCERTAIN / REJECTED with confidence and
evidence. Discovery never repairs anything; a VERIFIED finding can later be
handed to ``RepairGraph`` explicitly.
"""

from collections.abc import Callable

from langgraph.graph import END, START, StateGraph

from repoagent.domain.audit_report import AuditMetrics, AuditReport
from repoagent.domain.workflow import StageStatus
from repoagent.workflows.discovery_nodes import (
    DiscoveryDeps,
    DiscoveryNodes,
    DiscoveryState,
)
from repoagent.workflows.progress import StageSink, ignore_stage

STAGES = {
    "load_repository": "repository",
    "analyze_repository": "analysis",
    "static_detectors": "static_detectors",
    "graph_detectors": "graph_detectors",
    "deduplicate": "deduplicate",
    "enrich_evidence": "evidence",
    "verify": "verifier",
    "results": "report",
}


def _describe(node: str, state: DiscoveryState, update: dict) -> str:
    if node == "load_repository":
        handle = update["handle"]
        return f"{handle.name} @ {handle.commit[:12] if handle.commit else 'local'}"
    if node == "analyze_repository":
        analysis = update["context"].analysis
        return f"{analysis.python_files} Python files, {len(analysis.symbols)} symbols"
    if node in ("static_detectors", "graph_detectors"):
        found = update.get(node.replace("detectors", "candidates"), [])
        return f"{len(found)} candidates"
    if node == "deduplicate":
        return f"{len(update['candidates'])} kept, {update['removed']} merged"
    if node == "verify":
        m: AuditMetrics = update["metrics"]
        return f"{m.verified} verified, {m.uncertain} uncertain, {m.rejected} rejected"
    return f"{len(update.get('candidates', state.candidates))} findings"


class DiscoveryGraph:
    def __init__(self, deps: DiscoveryDeps, sink: StageSink = ignore_stage) -> None:
        self._nodes, self._sink = DiscoveryNodes(deps), sink
        self._graph = self._build()

    def _observed(self, node: str, action: Callable[[DiscoveryState], dict]):
        def run(state: DiscoveryState) -> dict:
            self._sink(STAGES[node], StageStatus.RUNNING, "")
            update = action(state)
            detail = _describe(node, state, update)
            self._sink(STAGES[node], StageStatus.DONE, detail)
            return update

        return run

    @staticmethod
    def _after_dedupe(state: DiscoveryState) -> str:
        return "enrich_evidence" if state.candidates else "results"

    @staticmethod
    def _results(state: DiscoveryState) -> dict:
        if state.metrics is not None:
            return {"metrics": state.metrics}
        empty = AuditMetrics(
            candidates_by_source=state.by_source,
            duplicate_findings_removed=state.removed,
        )
        return {"metrics": empty}

    def _build(self):
        nodes = self._nodes
        actions = {
            "load_repository": nodes.load,
            "analyze_repository": nodes.analyze,
            "static_detectors": nodes.static_detectors,
            "graph_detectors": nodes.graph_detectors,
            "deduplicate": nodes.deduplicate,
            "enrich_evidence": nodes.enrich,
            "verify": nodes.verify,
            "results": self._results,
        }
        graph = StateGraph(DiscoveryState)
        for name, action in actions.items():
            graph.add_node(name, self._observed(name, action))
        linear = list(actions)[:5]
        graph.add_edge(START, linear[0])
        for source, target in zip(linear, linear[1:], strict=False):
            graph.add_edge(source, target)
        graph.add_conditional_edges(
            "deduplicate",
            self._after_dedupe,
            {"enrich_evidence": "enrich_evidence", "results": "results"},
        )
        graph.add_edge("enrich_evidence", "verify")
        graph.add_edge("verify", "results")
        graph.add_edge("results", END)
        return graph.compile()

    def run(self, source: str, limit: int | None = None) -> DiscoveryState:
        final = self._graph.invoke(DiscoveryState(source=source, limit=limit))
        return DiscoveryState.model_validate(final)

    @staticmethod
    def report(state: DiscoveryState, repository: str) -> AuditReport:
        analysis = state.context.analysis
        return AuditReport(
            repository=repository,
            files_scanned=analysis.python_files,
            symbols_scanned=len(analysis.symbols),
            candidates=state.candidates,
            metrics=state.metrics or AuditMetrics(),
        )
