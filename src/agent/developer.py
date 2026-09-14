"""Developer node that creates a structured, minimal patch proposal."""

from repoagent.agent.repair_context import SYSTEM, repair_context
from repoagent.ai.provider import LLMProvider
from repoagent.ai.repair_models import DeveloperOutput
from repoagent.ai.structured import structured_generate
from repoagent.domain.errors import LLMError
from repoagent.domain.investigation import InvestigationReport
from repoagent.domain.repair import PatchProposal


class DeveloperAgent:
    """Produces a candidate patch without filesystem mutation."""

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    def propose(self, report: InvestigationReport, feedback: str = "") -> PatchProposal:
        """Generate exactly one bounded proposal from evidence-backed context."""
        try:
            _, output = structured_generate(
                self._provider,
                "patch_proposal",
                SYSTEM,
                repair_context(report, feedback),
                DeveloperOutput,
            )
        except LLMError:
            raise
        return PatchProposal(plan=output.plan, unified_diff=output.unified_diff)
