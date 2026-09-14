"""LangGraph Investigator: stateful, iterative, read-only (M5).

LangGraph owns orchestration only; nodes, state, routing, and domain
models stay framework-independent so the workflow remains testable and
portable. The graph loops retrieve → assess → refine and hypothesize →
evaluate → investigate-more under hard iteration/query/evidence limits.
"""

from langgraph.graph import END, START, StateGraph

from repoagent.agent.discovery import DiscoveryNodes
from repoagent.agent.evaluation import EvaluationNode
from repoagent.agent.evidence import EvidenceNodes
from repoagent.agent.reasoning import ReasoningNodes
from repoagent.agent.reporting import build_report
from repoagent.agent.routing import (
    route_after_analysis,
    route_after_assessment,
    route_after_evaluation,
    route_after_hypothesis,
    route_after_plan,
)
from repoagent.agent.state import InvestigationState
from repoagent.ai.provider import LLMProvider
from repoagent.domain.investigation import (
    InvestigationLimits,
    InvestigationReport,
    Issue,
)
from repoagent.tools.repository import RepositoryToolkit


class InvestigatorAgent:
    """Compiles and runs the investigation workflow."""

    def __init__(
        self,
        toolkit: RepositoryToolkit,
        provider: LLMProvider,
        limits: InvestigationLimits | None = None,
    ) -> None:
        self._toolkit = toolkit
        self._provider = provider
        self._limits = limits or InvestigationLimits()
        self._graph = self._build()

    def _build(self):
        discovery = DiscoveryNodes(self._provider)
        evidence = EvidenceNodes(self._provider, self._toolkit)
        reasoning = ReasoningNodes(self._provider)
        graph = StateGraph(InvestigationState)
        graph.add_node("analyze_issue", discovery.analyze_issue)
        graph.add_node("plan_search", discovery.plan_search)
        graph.add_node("retrieve", evidence.retrieve)
        graph.add_node("assess_evidence", evidence.assess_evidence)
        graph.add_node("hypothesize", reasoning.hypothesize)
        graph.add_node("evaluate", EvaluationNode(self._provider).evaluate)
        graph.add_node("refine", discovery.refine)
        graph.add_node("report", build_report)
        graph.add_edge(START, "analyze_issue")
        graph.add_conditional_edges(
            "analyze_issue",
            route_after_analysis,
            {"plan_search": "plan_search", "report": "report"},
        )
        graph.add_conditional_edges(
            "plan_search",
            route_after_plan,
            {"retrieve": "retrieve", "report": "report"},
        )
        graph.add_edge("refine", "retrieve")
        graph.add_edge("retrieve", "assess_evidence")
        graph.add_conditional_edges(
            "assess_evidence",
            route_after_assessment,
            {
                "hypothesize": "hypothesize",
                "refine": "refine",
                "report": "report",
            },
        )
        graph.add_conditional_edges(
            "hypothesize",
            route_after_hypothesis,
            {"evaluate": "evaluate", "report": "report"},
        )
        graph.add_conditional_edges(
            "evaluate",
            route_after_evaluation,
            {"refine": "refine", "report": "report"},
        )
        graph.add_edge("report", END)
        return graph.compile()

    def run(self, repository: str, task_id: str, issue: Issue) -> InvestigationReport:
        """Investigate one issue and return the typed report."""
        state = InvestigationState(
            repository=repository,
            task_id=task_id,
            issue=issue,
            limits=self._limits,
            top_k=self._toolkit.top_k,
        )
        final = self._graph.invoke(
            state,
            config={"recursion_limit": 20 + self._limits.max_iterations * 6},
        )
        return InvestigationReport.model_validate(final["report"])
