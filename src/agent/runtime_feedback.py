"""Bounded feedback passed from a failed attempt to Developer or Investigator."""

from repoagent.domain.investigation import Issue
from repoagent.domain.repair_execution import FailureAnalysis, RepairAttempt

MAX_PREVIOUS_DIFF = 4000


def developer_feedback(attempts: list[RepairAttempt]) -> dict:
    """Latest failure in detail; earlier attempts only as one-line summaries."""
    latest = attempts[-1]
    validation, analysis = latest.validation, latest.failure_analysis
    tests = validation.tests
    comparison = validation.comparison
    return {
        "attempt": latest.number,
        "previous_diff": latest.proposal.unified_diff[:MAX_PREVIOUS_DIFF],
        "validation_summary": validation.summary,
        "failed_tests": [
            {"test_id": item.test_id, "message": item.message}
            for item in (tests.failures[:8] if tests else [])
        ],
        "new_lint": comparison.new_lint[:10] if comparison else [],
        "analysis": analysis.model_dump(mode="json", exclude={"source"})
        if analysis
        else None,
        "earlier_attempts": [
            {
                "attempt": item.number,
                "reason": item.failure_analysis.likely_reason[:200],
            }
            for item in attempts[:-1][-3:]
            if item.failure_analysis
        ],
    }


def reinvestigation_issue(issue: Issue, analysis: FailureAnalysis) -> Issue:
    """Augment the original issue with the runtime observation (not a new task)."""
    observed = (
        "A patch based on the previous root-cause hypothesis failed sandbox "
        f"validation: {analysis.likely_reason}"
    )
    if analysis.evidence_needed:
        observed += " Evidence needed: " + "; ".join(analysis.evidence_needed)
    return Issue.model_validate(
        {
            **issue.model_dump(),
            "observed_behavior": observed[:2000],
        }
    )
