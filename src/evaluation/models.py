"""Retrieval evaluation cases and metric computation."""

from pydantic import Field, field_validator

from repoagent.analysis.models import AnalysisModel
from repoagent.retrieval.models import RetrievalResult, RetrievalStrategy


class RetrievalCase(AnalysisModel):
    """One labeled evaluation query with expected files and symbols."""

    query: str
    expected_files: list[str] = Field(default_factory=list)
    expected_symbols: list[str] = Field(default_factory=list)

    @field_validator("query")
    @classmethod
    def _require_query(cls, value: str) -> str:
        query = value.strip()
        if not query:
            raise ValueError("A nonempty query is required")
        return query

    @property
    def expected(self) -> set[str]:
        return {*self.expected_files, *self.expected_symbols}

    def matched_items(self, result: RetrievalResult) -> set[str]:
        """Return expected items this result's provenance satisfies."""
        chunk = result.chunk
        found = {item for item in self.expected_files if item == chunk.file_path}
        found |= {
            item for item in self.expected_symbols if item == chunk.qualified_name
        }
        return found


class StrategyMetrics(AnalysisModel):
    """Averaged metrics for one strategy over all cases."""

    strategy: RetrievalStrategy
    queries: int
    k: int
    recall_at_k: float
    mrr: float
    hit_rate_at_k: float
    precision_at_k: float


class EvaluationReport(AnalysisModel):
    """Strategy comparison produced from actual retrieval runs."""

    repository: str
    k: int
    rows: list[StrategyMetrics]


def case_metrics(
    case: RetrievalCase, results: list[RetrievalResult], k: int
) -> tuple[float, float, float, float]:
    """Return (recall@k, MRR, hit_rate@k, precision@k) for one case.

    Recall counts distinct expected items satisfied within the top k;
    MRR uses the first relevant rank; precision divides relevant hits by
    k. Cases without expectations score zero.
    """
    matched: set[str] = set()
    relevant_hits = 0
    first_rank = 0
    for rank, result in enumerate(results[:k], start=1):
        found = case.matched_items(result)
        if found:
            relevant_hits += 1
            matched |= found
            if not first_rank:
                first_rank = rank
    expected = case.expected
    if not expected:
        return 0.0, 0.0, 0.0, 0.0
    recall = len(matched) / len(expected)
    mrr = 1.0 / first_rank if first_rank else 0.0
    hit_rate = 1.0 if relevant_hits else 0.0
    precision = relevant_hits / k if k else 0.0
    return recall, mrr, hit_rate, precision


def aggregate(
    strategy: RetrievalStrategy,
    metrics: list[tuple[float, float, float, float]],
    k: int,
) -> StrategyMetrics:
    """Average per-case metrics into one strategy row."""
    total = len(metrics) or 1
    if metrics:
        recalls, mrrs, hits, precisions = zip(*metrics, strict=True)
    else:
        recalls, mrrs, hits, precisions = (), (), (), ()
    queries = len(metrics)
    return StrategyMetrics(
        strategy=strategy,
        queries=queries,
        k=k,
        recall_at_k=sum(recalls) / total,
        mrr=sum(mrrs) / total,
        hit_rate_at_k=sum(hits) / total,
        precision_at_k=sum(precisions) / total,
    )
