"""Experiment configuration: benchmark mode plus ablation feature flags."""

from enum import StrEnum

from pydantic import Field

from repoagent.analysis.models import AnalysisModel
from repoagent.domain.features import RepairFeatures
from repoagent.graph.policy import GRAPH_POLICIES
from repoagent.retrieval.configured import RERANKERS
from repoagent.retrieval.models import RetrievalStrategy

ABLATIONS: dict[str, RepairFeatures] = {
    "full": RepairFeatures(),
    "no_graph": RepairFeatures(graph_retrieval=False),
    "no_reviewer": RepairFeatures(reviewer=False),
    "single_pass": RepairFeatures(single_retrieval_pass=True),
    "no_retry": RepairFeatures(failure_retry=False),
    "best_hypothesis": RepairFeatures(require_confident_root_cause=False),
}

_GRAPH_ONLY = [RetrievalStrategy.HYBRID_GRAPH]
_RERANKED = [RetrievalStrategy.BM25, RetrievalStrategy.HYBRID, *_GRAPH_ONLY]
RERANK_POOL = 20
# LLM-free retrieval arms (``rerank_llm`` aside): graph-policy ablations
# score hybrid_graph only; rerankers rerank a 20-candidate pool, while
# ``rerank_keyword_topk`` is the agent's own rerank-within-top-k default.
RETRIEVAL_ABLATIONS: dict[str, dict] = {
    "full": {},
    **{
        f"graph_{name}": {"graph_policy": name, "strategies": _GRAPH_ONLY}
        for name in GRAPH_POLICIES
    },
    **{
        f"rerank_{name}": {
            "reranker": name,
            "rerank_candidates": RERANK_POOL,
            "strategies": _RERANKED,
        }
        for name in RERANKERS
    },
    "rerank_keyword_topk": {"reranker": "keyword", "strategies": _RERANKED},
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
    graph_policy: str | None = None
    reranker: str | None = None
    rerank_candidates: int | None = Field(default=None, ge=1, le=100)
    max_attempts: int = Field(default=3, ge=1, le=10)
    timeout_seconds: int = Field(default=300, ge=1, le=3600)


def ablation_names(mode: BenchmarkMode) -> list[str]:
    return list(RETRIEVAL_ABLATIONS if mode == BenchmarkMode.RETRIEVAL else ABLATIONS)


def experiments(mode: BenchmarkMode, names: list[str], **options) -> list:
    """Build experiment arms from ablation names; unknown names are rejected.

    Retrieval mode uses retrieval arms (graph policy / reranker); LLM modes
    use the repair feature-flag ablations.
    """
    unknown = [name for name in names if name not in ablation_names(mode)]
    if unknown:
        raise ValueError(f"Unknown ablation(s): {', '.join(unknown)}")
    if mode == BenchmarkMode.RETRIEVAL:
        return [
            ExperimentConfig(
                name=name, mode=mode, **options | RETRIEVAL_ABLATIONS[name]
            )
            for name in names or ["full"]
        ]
    return [
        ExperimentConfig(name=name, mode=mode, features=ABLATIONS[name], **options)
        for name in names or ["full"]
    ]
