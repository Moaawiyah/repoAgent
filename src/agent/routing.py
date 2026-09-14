"""Conditional edges and deterministic budget exhaustion reasons."""

from repoagent.agent.state import InvestigationState


def exhausted(state: InvestigationState) -> str | None:
    if state.tool_calls >= state.limits.max_tool_calls:
        return "max_tool_calls"
    if len(state.evidence) >= state.limits.max_evidence:
        return "max_evidence"
    if len(state.executed_queries) >= state.limits.max_queries:
        return "max_queries"
    if state.current_iteration >= state.limits.max_iterations:
        return "max_iterations"
    return None


def route_after_analysis(state: InvestigationState) -> str:
    return "report" if state.termination else "plan_search"


def route_after_plan(state: InvestigationState) -> str:
    return "report" if state.termination or not state.pending_queries else "retrieve"


def route_after_assessment(state: InvestigationState) -> str:
    if state.termination:
        return "report"
    if state.enough_evidence:
        return "hypothesize"
    if state.next_queries and not exhausted(state):
        return "refine"
    if any(e.relevance == "relevant" for e in state.evidence):
        return "hypothesize"
    return "report"


def route_after_hypothesis(state: InvestigationState) -> str:
    return "report" if state.termination or not state.hypotheses else "evaluate"


def route_after_evaluation(state: InvestigationState) -> str:
    if state.termination:
        return "report"
    return "refine" if state.next_queries and not exhausted(state) else "report"
