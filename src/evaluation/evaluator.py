"""Strategy-comparison evaluation over labeled retrieval cases."""

import logging

from repoagent.application.searching import SearchService
from repoagent.evaluation.models import (
    EvaluationReport,
    RetrievalCase,
    StrategyMetrics,
    aggregate,
    case_metrics,
    ndcg_at_k,
)
from repoagent.retrieval.models import RetrievalStrategy, SearchRequest

DEFAULT_STRATEGIES = (
    RetrievalStrategy.BM25,
    RetrievalStrategy.VECTOR,
    RetrievalStrategy.HYBRID,
    RetrievalStrategy.HYBRID_GRAPH,
)


class RetrievalEvaluator:
    """Runs real searches per strategy and computes Recall@K and MRR.

    Every reported metric derives from actual retrieval results; nothing
    is hardcoded or estimated.
    """

    def __init__(
        self, service: SearchService, repository: str, rerank: bool = False
    ) -> None:
        self._service = service
        self._repository = repository
        self._rerank = rerank

    def evaluate(
        self,
        cases: list[RetrievalCase],
        k: int = 5,
        strategies: tuple[RetrievalStrategy, ...] | None = None,
    ) -> EvaluationReport:
        rows = [
            self._evaluate_strategy(strategy, cases, k)
            for strategy in (strategies or DEFAULT_STRATEGIES)
        ]
        logging.getLogger(__name__).info(
            "Evaluation completed", extra={"event": "evaluation_completed"}
        )
        return EvaluationReport(repository=self._repository, k=k, rows=rows)

    def _evaluate_strategy(
        self, strategy: RetrievalStrategy, cases: list[RetrievalCase], k: int
    ) -> StrategyMetrics:
        runs = [(case, self._search(case.query, strategy, k)) for case in cases]
        metrics = [case_metrics(case, results, k) for case, results in runs]
        ndcgs = [ndcg_at_k(case, results, k) for case, results in runs]
        return aggregate(strategy, metrics, k, ndcgs)

    def _search(self, query: str, strategy: RetrievalStrategy, k: int) -> list:
        request = SearchRequest(
            repository=self._repository,
            query=query,
            strategy=strategy,
            top_k=k,
            rerank=self._rerank,
        )
        return self._service.search(request).results
