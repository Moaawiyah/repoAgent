"""Score one task's retrieval under one experiment arm (labels used only here)."""

from pathlib import Path

from repoagent.ai.provider import LLMProvider
from repoagent.benchmark.experiment import ExperimentConfig
from repoagent.benchmark.models import BenchmarkTask
from repoagent.benchmark.results import RetrievalScore, TokenUsage
from repoagent.config import Settings
from repoagent.evaluation.models import EvaluationReport, RetrievalCase
from repoagent.retrieval.configured import build_reranker
from repoagent.retrieval.embeddings import provider_from_settings
from repoagent.retrieval.model_rerank import LLMReranker


def retrieval_fields(
    client,
    settings: Settings,
    llm: LLMProvider | None,
    task: BenchmarkTask,
    path: Path,
    config: ExperimentConfig,
) -> dict:
    """Evaluate the arm's strategies, graph policy, and reranker on one task."""
    case = RetrievalCase(
        query=task.issue,
        expected_files=task.expected_files,
        expected_symbols=task.expected_symbols,
    )
    reranker = None
    if config.reranker:
        embedding = provider_from_settings(settings)
        reranker = build_reranker(config.reranker, embedding, llm)
    report = client.retrieval().evaluate(
        path,
        [case],
        k=config.k,
        strategies=config.strategies,
        graph_policy=config.graph_policy,
        reranker=reranker,
        rerank_candidates=config.rerank_candidates,
    )
    fields: dict = {"retrieval": _scores(report)}
    if isinstance(reranker, LLMReranker):
        fields["tokens"] = TokenUsage(
            llm_calls=reranker.calls,
            input_tokens=reranker.input_tokens,
            output_tokens=reranker.output_tokens,
        )
    return fields


def _scores(report: EvaluationReport) -> dict[str, RetrievalScore]:
    return {
        row.strategy.value: RetrievalScore(
            recall_at_k=row.recall_at_k,
            mrr=row.mrr,
            hit_at_k=row.hit_rate_at_k,
            ndcg_at_k=row.ndcg_at_k,
        )
        for row in report.rows
    }
