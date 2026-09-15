"""Experiment configuration: benchmark mode plus ablation feature flags."""

from enum import StrEnum

from pydantic import Field

from repoagent.analysis.models import AnalysisModel
from repoagent.domain.features import RepairFeatures
from repoagent.retrieval.models import RetrievalStrategy

ABLATIONS: dict[str, RepairFeatures] = {
    "full": RepairFeatures(),
    "no_graph": RepairFeatures(graph_retrieval=False),
    "no_reviewer": RepairFeatures(reviewer=False),
    "single_pass": RepairFeatures(single_retrieval_pass=True),
    "no_retry": RepairFeatures(failure_retry=False),
}


class BenchmarkMode(StrEnum):
    RETRIEVAL = "retrieval"
    INVESTIGATE = "investigate"
    REPAIR = "repair"


class ExperimentConfig(AnalysisModel):
    """One arm of a benchmark run; ``retrieval`` mode never calls an LLM."""

    name: str = Field(pattern=r"^[a-z0-9_+-]{1,60}$")
    mode: BenchmarkMode = BenchmarkMode.RETRIEVAL
    features: RepairFeatures = RepairFeatures()
    k: int = Field(default=5, ge=1, le=50)
    strategies: list[RetrievalStrategy] = Field(
        default_factory=lambda: list(RetrievalStrategy)
    )
    max_attempts: int = Field(default=3, ge=1, le=10)
    timeout_seconds: int = Field(default=300, ge=1, le=3600)


def experiments(mode: BenchmarkMode, names: list[str], **options) -> list:
    """Build experiment arms from ablation names; unknown names are rejected."""
    unknown = [name for name in names if name not in ABLATIONS]
    if unknown:
        raise ValueError(f"Unknown ablation(s): {', '.join(unknown)}")
    return [
        ExperimentConfig(name=name, mode=mode, features=ABLATIONS[name], **options)
        for name in names or ["full"]
    ]
