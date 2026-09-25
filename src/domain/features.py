"""Experiment feature flags around existing components (M8 ablations).

Flags only disable or bound existing behavior; they never add alternative
implementations, so ablations measure the real system.
"""

from repoagent.analysis.models import AnalysisModel


class RepairFeatures(AnalysisModel):
    """Default values describe the full RepoAgent pipeline."""

    graph_retrieval: bool = True
    reviewer: bool = True
    single_retrieval_pass: bool = False
    failure_retry: bool = True
    # False: when the investigation stops on a budget or on insufficient
    # evidence but still ranks a primary hypothesis, hand that hypothesis to
    # the Developer and let sandbox validation (and hidden tests) judge it.
    require_confident_root_cause: bool = True

    @property
    def name(self) -> str:
        disabled = [
            label
            for label, enabled in (
                ("no_graph", self.graph_retrieval),
                ("no_reviewer", self.reviewer),
                ("single_pass", not self.single_retrieval_pass),
                ("no_retry", self.failure_retry),
                ("best_hypothesis", self.require_confident_root_cause),
            )
            if not enabled
        ]
        return "+".join(disabled) or "full"
