"""Assemble honest, serializable reports with bounded confidence."""

from repoagent.agent.routing import exhausted
from repoagent.agent.shared import trace
from repoagent.agent.state import InvestigationState
from repoagent.domain.investigation import InvestigationReport, TerminationReason


def build_report(state: InvestigationState) -> dict:
    reason = state.termination or exhausted(state) or "insufficient_evidence"
    confidence = (
        state.confidence
        if reason == "confident_root_cause"
        else min(state.confidence, 0.6)
    )
    relevant = [e for e in state.evidence if e.relevance == "relevant"]
    report = InvestigationReport(
        task_id=state.task_id,
        repository=state.repository,
        issue=state.issue,
        issue_summary=(
            state.issue_analysis.observed_behavior if state.issue_analysis else ""
        )
        or state.issue.description[:300],
        likely_affected_area=state.issue_analysis.likely_subsystem
        if state.issue_analysis
        else "",
        issue_analysis=state.issue_analysis,
        evidence=state.evidence,
        hypotheses=state.hypotheses,
        primary_hypothesis_id=state.primary_hypothesis_id,
        confidence=confidence,
        open_questions=list(
            dict.fromkeys(q for h in state.hypotheses for q in h.open_questions)
        ),
        relevant_files=sorted({e.file_path for e in relevant}),
        relevant_symbols=sorted({e.qualified_name for e in relevant}),
        graph_paths=[e.graph_path for e in relevant if e.graph_path],
        termination_reason=TerminationReason(reason),
        trace=trace(state, "investigation_completed", "stop", reason),
        iterations=state.current_iteration,
        usage=state.usage,
        queries=state.executed_queries,
        tool_calls=state.tool_calls,
        error=state.error,
    )
    return {"report": report, "termination": reason}
