"""Issue analysis and focused search planning nodes."""

from repoagent.agent.shared import failure, fresh_queries, generate, trace
from repoagent.agent.state import InvestigationState
from repoagent.ai.models import IssueAnalysis, SearchPlan
from repoagent.ai.provider import LLMProvider
from repoagent.domain.errors import LLMError


class DiscoveryNodes:
    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    def analyze_issue(self, state: InvestigationState) -> dict:
        try:
            analysis, usage = generate(
                state, self._provider, "issue_analysis", IssueAnalysis
            )
        except LLMError as error:
            return failure(state, "issue_analyzed", str(error))
        return {
            "issue_analysis": analysis,
            "usage": usage,
            "trace": trace(state, "issue_analyzed", "continue"),
        }

    def plan_search(self, state: InvestigationState) -> dict:
        try:
            plan, usage = generate(state, self._provider, "search_plan", SearchPlan)
        except LLMError as error:
            return failure(state, "search_planned", str(error))
        queries = fresh_queries(state, plan.queries)
        return {
            "pending_queries": queries,
            "usage": usage,
            "trace": trace(
                state, "search_planned", "continue", query="; ".join(queries)
            ),
        }

    def refine(self, state: InvestigationState) -> dict:
        queries = fresh_queries(state, state.next_queries)
        return {
            "pending_queries": queries,
            "next_queries": [],
            "trace": trace(
                state, "query_refined", "continue", query="; ".join(queries)
            ),
        }
