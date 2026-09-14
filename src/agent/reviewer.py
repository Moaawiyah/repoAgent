"""Independent Reviewer node for static patch proposals."""

from repoagent.agent.repair_context import SYSTEM, repair_context
from repoagent.ai.provider import LLMProvider
from repoagent.ai.repair_models import ReviewerOutput
from repoagent.ai.structured import structured_generate
from repoagent.domain.investigation import InvestigationReport
from repoagent.domain.repair import PatchProposal, PatchReview, StaticValidation


class ReviewerAgent:
    """Reviews root-cause alignment and risk after static validation."""

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    def review(
        self,
        report: InvestigationReport,
        proposal: PatchProposal,
        validation: StaticValidation,
    ) -> PatchReview:
        """Review only the supplied proposal; invalid patches cannot be approved."""
        if not validation.valid:
            return PatchReview(
                decision="reject",
                rationale="Static patch validation failed.",
                concerns=validation.errors,
                recommended_tests=proposal.plan.recommended_tests,
            )
        _, output = structured_generate(
            self._provider,
            "patch_review",
            SYSTEM,
            repair_context(report, proposal=proposal, validation=validation),
            ReviewerOutput,
        )
        return PatchReview(**output.model_dump())
