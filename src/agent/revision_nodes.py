"""Developer/Reviewer proposal, failure analysis, and bounded re-investigation."""

from collections.abc import Callable

from repoagent.agent.execution_state import ExecutionRepairState
from repoagent.agent.failure_analyzer import FailureAnalyzerAgent
from repoagent.agent.repair_agent import RepairAgent
from repoagent.agent.runtime_feedback import developer_feedback, reinvestigation_issue
from repoagent.ai.provider import LLMProvider
from repoagent.domain.errors import LLMError
from repoagent.domain.investigation import InvestigationReport, Issue, TerminationReason
from repoagent.domain.repair import RepairStatus
from repoagent.domain.repair_execution import ExecutionStatus, NextAction

Reinvestigator = Callable[[Issue], InvestigationReport]
_PROPOSAL_FAILURES = {
    RepairStatus.PROVIDER_ERROR: ExecutionStatus.PROVIDER_ERROR,
    RepairStatus.REJECTED: ExecutionStatus.REVIEW_REJECTED,
    RepairStatus.MAX_REVISIONS: ExecutionStatus.REVIEW_REJECTED,
}


class RevisionNodes:
    def __init__(
        self,
        provider: LLMProvider,
        reinvestigate: Reinvestigator,
        reviewer: bool = True,
    ) -> None:
        self._provider, self._reviewer = provider, reviewer
        self._analyzer = FailureAnalyzerAgent(provider)
        self._reinvestigate = reinvestigate

    def propose(self, state: ExecutionRepairState) -> dict:
        """Reuse the complete M6 Developer → static validator → Reviewer graph."""
        agent = RepairAgent(
            state.repository,
            self._provider,
            state.limits.max_revisions,
            reviewer=self._reviewer,
        )
        report = agent.run(state.investigation, state.runtime)
        status = _PROPOSAL_FAILURES.get(report.status)
        update: dict = {"proposal_report": report}
        if status is not None:
            reason = report.reviews[-1].rationale if report.reviews else report.error
            update |= {"status": status, "error": reason or report.status.value}
        return update

    def analyze(self, state: ExecutionRepairState) -> dict:
        """Deterministic triage result if present, otherwise one LLM analysis."""
        attempt = state.attempts[-1]
        analysis = attempt.failure_analysis
        if analysis is None:
            try:
                analysis = self._analyzer.analyze(
                    state.investigation,
                    attempt.proposal,
                    attempt.validation,
                    state.attempts[:-1],
                )
            except LLMError:
                return {
                    "status": ExecutionStatus.PROVIDER_ERROR,
                    "error": "Failure Analyzer output failed validation",
                }
            attempt = attempt.model_copy(update={"failure_analysis": analysis})
        attempts = [*state.attempts[:-1], attempt]
        update: dict = {"attempts": attempts}
        if analysis.next_action == NextAction.STOP:
            return update | {
                "status": ExecutionStatus.VALIDATION_FAILED,
                "error": analysis.likely_reason,
            }
        return update | {"runtime": developer_feedback(attempts)}

    def reinvestigate(self, state: ExecutionRepairState) -> dict:
        """Collect new evidence when runtime facts contradict the hypothesis."""
        analysis = state.attempts[-1].failure_analysis
        if analysis is None:
            return {"status": ExecutionStatus.SANDBOX_FAILED, "error": "No analysis"}
        issue = reinvestigation_issue(state.investigation.issue, analysis)
        try:
            report = self._reinvestigate(issue)
        except LLMError:
            return {"status": ExecutionStatus.PROVIDER_ERROR, "error": "Investigator"}
        update: dict = {
            "reinvestigations": state.reinvestigations + 1,
            "investigations": state.investigations + 1,
            "retrieval_calls": state.retrieval_calls + report.tool_calls,
        }
        if report.termination_reason == TerminationReason.PROVIDER_ERROR:
            return update | {
                "status": ExecutionStatus.PROVIDER_ERROR,
                "error": report.error or "Investigator provider failed",
            }
        if report.termination_reason != TerminationReason.CONFIDENT_ROOT_CAUSE:
            return update | {
                "status": ExecutionStatus.INSUFFICIENT_EVIDENCE,
                "error": "Re-investigation did not reach a confident root cause",
            }
        return update | {"investigation": report}

    @staticmethod
    def wants_reinvestigation(state: ExecutionRepairState) -> bool:
        analysis = state.attempts[-1].failure_analysis if state.attempts else None
        return bool(
            analysis
            and analysis.next_action == NextAction.REINVESTIGATE
            and state.reinvestigations < state.limits.max_reinvestigations
        )
