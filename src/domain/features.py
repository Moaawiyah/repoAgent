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

    @property
    def name(self) -> str:
        disabled = [
            label
            for label, enabled in (
                ("no_graph", self.graph_retrieval),
                ("no_reviewer", self.reviewer),
                ("single_pass", not self.single_retrieval_pass),
                ("no_retry", self.failure_retry),
            )
            if not enabled
        ]
        return "+".join(disabled) or "full"
