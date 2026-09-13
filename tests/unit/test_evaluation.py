"""Evaluation metric correctness on known rankings."""

import pytest
from pydantic import ValidationError

from repoagent.evaluation.models import (
    RetrievalCase,
    aggregate,
    case_metrics,
)
from repoagent.retrieval.models import RetrievalStrategy


def make_result(file_path, qualified):
    from repoagent.retrieval.models import (
        CodeChunk,
        RetrievalResult,
        RetrievalSource,
        SymbolType,
    )

    chunk = CodeChunk(
        chunk_id=qualified,
        repository_id="r",
        file_path=file_path,
        language="python",
        symbol_name=qualified.split(".")[-1],
        qualified_name=qualified,
        symbol_type=SymbolType.FUNCTION,
        start_line=1,
        end_line=1,
        source="x = 1",
    )
    return RetrievalResult(rank=0, score=1.0, source=RetrievalSource.BM25, chunk=chunk)


CASE = RetrievalCase(
    query="q",
    expected_files=["a.py"],
    expected_symbols=["mod.auth_sym"],
)


def test_metrics_on_known_ranking():
    results = [
        make_result("b.py", "mod.other"),
        make_result("a.py", "mod.unrelated"),
        make_result("c.py", "mod.auth_sym"),
    ]
    recall, mrr, hit, precision = case_metrics(CASE, results, k=2)
    assert recall == pytest.approx(0.5)
    assert mrr == pytest.approx(0.5)
    assert hit == 1.0
    assert precision == pytest.approx(0.5)


def test_full_match_at_k_three():
    results = [
        make_result("b.py", "mod.other"),
        make_result("a.py", "mod.unrelated"),
        make_result("c.py", "mod.auth_sym"),
    ]
    recall, mrr, _, precision = case_metrics(CASE, results, k=3)
    assert recall == pytest.approx(1.0)
    assert mrr == pytest.approx(0.5)
    assert precision == pytest.approx(2 / 3)


def test_no_relevant_results_score_zero():
    results = [make_result("b.py", "mod.other")]
    recall, mrr, hit, precision = case_metrics(CASE, results, k=1)
    assert (recall, mrr, hit, precision) == (0.0, 0.0, 0.0, 0.0)


def test_case_without_expectations_scores_zero():
    empty = RetrievalCase(query="q")
    values = case_metrics(empty, [make_result("a.py", "mod.auth_sym")], 5)
    assert values == (0.0, 0.0, 0.0, 0.0)


def test_aggregate_averages_cases():
    rows = [
        (1.0, 1.0, 1.0, 0.5),
        (0.0, 0.0, 0.0, 0.0),
    ]
    metrics = aggregate(RetrievalStrategy.HYBRID, rows, k=5)
    assert metrics.queries == 2
    assert metrics.recall_at_k == pytest.approx(0.5)
    assert metrics.mrr == pytest.approx(0.5)
    assert metrics.hit_rate_at_k == pytest.approx(0.5)
    assert metrics.precision_at_k == pytest.approx(0.25)


def test_aggregate_without_cases_is_zeroed():
    metrics = aggregate(RetrievalStrategy.BM25, [], k=5)
    assert metrics.queries == 0
    assert metrics.recall_at_k == 0.0


def test_cases_require_a_query():
    with pytest.raises(ValidationError):
        RetrievalCase(query="   ")
