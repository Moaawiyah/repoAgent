"""LangGraph M7 loop: baseline → propose → sandbox → analyze → retry.

Every loop edge is bounded by ``RepairLoopLimits``; a terminal ``status`` in
state always routes to the report node, so the graph cannot spin forever.
"""

from langgraph.graph import END, START, StateGraph

from repoagent.agent.execution_reporting import ExecutionReporter
from repoagent.agent.execution_state import ExecutionRepairState, RepairLoopLimits
from repoagent.agent.revision_nodes import Reinvestigator, RevisionNodes
from repoagent.agent.sandbox_nodes import SandboxNodes
from repoagent.ai.counting import CountingProvider
from repoagent.domain.investigation import InvestigationReport
from repoagent.domain.repair_execution import ValidatedRepairReport
from repoagent.domain.sandbox import ValidationPlan
from repoagent.ports.sandbox import SandboxSession


class ExecutionRepairAgent:
    """Composes sandbox and revision nodes around the reused M6 graph."""

    def __init__(
        self,
        provider: CountingProvider,
        session: SandboxSession,
        reinvestigate: Reinvestigator,
        limits: RepairLoopLimits,
    ) -> None:
        self._provider, self._limits = provider, limits
        self._sandbox = SandboxNodes(session)
        self._revision = RevisionNodes(provider, reinvestigate)
        self._graph = self._build()

    @staticmethod
    def _terminal_or(next_node: str):
        def route(state: ExecutionRepairState) -> str:
            return "report" if state.status is not None else next_node

        return route

    def _after_analysis(self, state: ExecutionRepairState) -> str:
        if state.status is not None:
            return "report"
        if self._revision.wants_reinvestigation(state):
            return "reinvestigate"
        return "propose"

    def _build(self):
        graph = StateGraph(ExecutionRepairState)
        reporter = ExecutionReporter(self._provider)
        graph.add_node("baseline", self._sandbox.baseline)
        graph.add_node("propose", self._revision.propose)
        graph.add_node("execute", self._sandbox.execute)
        graph.add_node("analyze", self._revision.analyze)
        graph.add_node("reinvestigate", self._revision.reinvestigate)
        graph.add_node("report", reporter.report)
        graph.add_edge(START, "baseline")
        routes = {
            "baseline": "propose",
            "propose": "execute",
            "execute": "analyze",
            "reinvestigate": "propose",
        }
        for source, target in routes.items():
            graph.add_conditional_edges(
                source,
                self._terminal_or(target),
                {target: target, "report": "report"},
            )
        graph.add_conditional_edges(
            "analyze",
            self._after_analysis,
            {n: n for n in ("report", "reinvestigate", "propose")},
        )
        graph.add_edge("report", END)
        return graph.compile()

    def run(
        self,
        task_id: str,
        investigation: InvestigationReport,
        plan: ValidationPlan,
    ) -> ValidatedRepairReport:
        state = ExecutionRepairState(
            task_id=task_id,
            repository=investigation.repository,
            investigation=investigation,
            plan=plan,
            limits=self._limits,
            retrieval_calls=investigation.tool_calls,
        )
        result = self._graph.invoke(
            state, config={"recursion_limit": self._limits.recursion_limit}
        )
        return ValidatedRepairReport.model_validate(result["report"])
