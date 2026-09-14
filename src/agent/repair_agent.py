"""LangGraph Developer → Validator → Reviewer workflow for M6."""

from langgraph.graph import END, START, StateGraph

from repoagent.adapters.patch_validator import StaticPatchValidator
from repoagent.agent.developer import DeveloperAgent
from repoagent.agent.repair_reporting import build_repair_report
from repoagent.agent.repair_state import RepairState
from repoagent.agent.reviewer import ReviewerAgent
from repoagent.ai.provider import LLMProvider
from repoagent.domain.errors import LLMError
from repoagent.domain.investigation import InvestigationReport
from repoagent.domain.repair import RepairReport


class RepairAgent:
    """Composes a bounded, read-only patch generation and review graph."""

    def __init__(
        self, repository: str, provider: LLMProvider, max_revisions: int
    ) -> None:
        self._developer, self._reviewer = (
            DeveloperAgent(provider),
            ReviewerAgent(provider),
        )
        self._validator = StaticPatchValidator(repository)
        self._max_revisions = max_revisions
        self._graph = self._build()

    def _develop(self, state: RepairState) -> dict:
        try:
            return {
                "proposal": self._developer.propose(state.investigation, state.feedback)
            }
        except LLMError:
            return {"error": "Developer output failed validation"}

    def _validate(self, state: RepairState) -> dict:
        if state.proposal is None:
            return {"error": "Developer produced no proposal"}
        return {"validation": self._validator.validate(state.proposal.unified_diff)}

    def _review(self, state: RepairState) -> dict:
        if state.proposal is None or state.validation is None:
            return {"error": "Patch validation is unavailable"}
        try:
            review = self._reviewer.review(
                state.investigation, state.proposal, state.validation
            )
        except LLMError:
            return {"error": "Reviewer output failed validation"}
        return {"reviews": [*state.reviews, review], "feedback": review.rationale}

    def _route(self, state: RepairState) -> str:
        if state.error:
            return "report"
        review = state.reviews[-1]
        if review.decision != "revise":
            return "report"
        return "develop" if state.revisions < state.max_revisions else "report"

    @staticmethod
    def _revision(state: RepairState) -> dict:
        return {"revisions": state.revisions + 1}

    def _build(self):
        graph = StateGraph(RepairState)
        graph.add_node("develop", self._develop)
        graph.add_node("validate", self._validate)
        graph.add_node("review", self._review)
        graph.add_node("revision", self._revision)
        graph.add_node("report", build_repair_report)
        graph.add_edge(START, "develop")
        graph.add_edge("develop", "validate")
        graph.add_edge("validate", "review")
        graph.add_conditional_edges(
            "review", self._route, {"develop": "revision", "report": "report"}
        )
        graph.add_edge("revision", "develop")
        graph.add_edge("report", END)
        return graph.compile()

    def run(self, report: InvestigationReport) -> RepairReport:
        """Return a patch proposal/review only; do not mutate the repository."""
        state = RepairState(
            repository=report.repository,
            investigation=report,
            max_revisions=self._max_revisions,
        )
        result = self._graph.invoke(
            state, config={"recursion_limit": 20 + 5 * self._max_revisions}
        )
        return RepairReport.model_validate(result["report"])
