"""Final M6 report construction with explicit unvalidated status."""

from repoagent.agent.repair_state import RepairState
from repoagent.domain.repair import RepairReport, RepairStatus


def build_repair_report(state: RepairState) -> dict:
    """Convert terminal repair state to a typed result without applying a patch."""
    review = state.reviews[-1] if state.reviews else None
    if state.error:
        status = RepairStatus.PROVIDER_ERROR
    elif review and review.decision == "approve":
        status = RepairStatus.APPROVED_FOR_RUNTIME_VALIDATION
    elif review and review.decision == "reject":
        status = RepairStatus.REJECTED
    else:
        status = RepairStatus.MAX_REVISIONS
    return {
        "report": RepairReport(
            investigation=state.investigation,
            status=status,
            proposal=state.proposal,
            validation=state.validation,
            reviews=state.reviews,
            revisions=state.revisions,
            error=state.error,
        )
    }
