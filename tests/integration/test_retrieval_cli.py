"""CLI index/search/evaluate behavior against the RAG fixture."""

import json
from pathlib import Path

from typer.testing import CliRunner

from repoagent.cli.main import app

runner = CliRunner()
FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "rag_repo"
CASES = Path(__file__).resolve().parents[1] / "fixtures" / "rag_cases.json"


def invoke(tmp_path, *args):
    return runner.invoke(app, ["--data-dir", str(tmp_path / "data"), *args])


def test_index_reports_and_persists(tmp_path):
    result = invoke(tmp_path, "index", str(FIXTURE))
    assert result.exit_code == 0, result.output
    assert "RepoAgent Repository Index" in result.output
    assert "Chunks: " in result.output
    data = json.loads(invoke(tmp_path, "index", str(FIXTURE), "--json").stdout)
    assert data["chunk_count"] > 0
    assert data["embedding_provider"] == "hashing"


def test_search_text_output_shows_provenance(tmp_path):
    invoke(tmp_path, "index", str(FIXTURE))
    result = invoke(
        tmp_path,
        "search",
        str(FIXTURE),
        "Where is authentication handled?",
        "--strategy",
        "hybrid",
        "--top-k",
        "5",
    )
    assert result.exit_code == 0, result.output
    assert "RepoAgent Search Results" in result.output
    assert "auth/service.py" in result.output
    assert "lines " in result.output and "[hybrid]" in result.output


def test_search_json_is_machine_readable(tmp_path):
    invoke(tmp_path, "index", str(FIXTURE))
    result = invoke(
        tmp_path,
        "search",
        str(FIXTURE),
        "calculate_invoice_total",
        "--strategy",
        "bm25",
        "--top-k",
        "3",
        "--json",
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert data["strategy"] == "bm25"
    assert len(data["results"]) <= 3
    first = data["results"][0]
    assert first["rank"] == 1
    assert first["chunk"]["file_path"] == "billing/invoice.py"
    assert first["chunk"]["qualified_name"] == "billing.invoice.calculate_invoice_total"
    assert first["chunk"]["start_line"] >= 1
    assert first["source"] == "bm25"


def test_search_strategies_and_rerank_flag(tmp_path):
    invoke(tmp_path, "index", str(FIXTURE))
    for strategy in ("bm25", "vector", "hybrid"):
        result = invoke(
            tmp_path, "search", str(FIXTURE), "cache", "--strategy", strategy, "--json"
        )
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)["strategy"] == strategy
    reranked = invoke(
        tmp_path, "search", str(FIXTURE), "cache eviction", "--rerank", "--json"
    )
    assert json.loads(reranked.stdout)["reranked"] is True


def test_search_before_indexing_is_operational_error(tmp_path):
    result = invoke(tmp_path, "search", str(FIXTURE), "anything")
    assert result.exit_code == 1
    assert "not been indexed" in result.stderr


def test_invalid_search_inputs(tmp_path):
    invoke(tmp_path, "index", str(FIXTURE))
    assert invoke(tmp_path, "search", str(FIXTURE), "   ").exit_code == 2
    assert (
        invoke(tmp_path, "search", str(FIXTURE), "auth", "--top-k", "0").exit_code == 2
    )
    assert (
        invoke(
            tmp_path, "search", str(FIXTURE), "auth", "--strategy", "magic"
        ).exit_code
        != 0
    )
    assert invoke(tmp_path, "index", str(tmp_path / "missing")).exit_code == 2


def test_search_is_deterministic(tmp_path):
    invoke(tmp_path, "index", str(FIXTURE))
    args = ("search", str(FIXTURE), "verify password", "--json")
    first = invoke(tmp_path, *args).stdout
    second = invoke(tmp_path, *args).stdout
    assert json.loads(first) == json.loads(second)


def test_evaluate_compares_strategies(tmp_path):
    invoke(tmp_path, "index", str(FIXTURE))
    result = invoke(tmp_path, "evaluate", str(FIXTURE), "--cases", str(CASES), "--json")
    assert result.exit_code == 0, result.output
    report = json.loads(result.stdout)
    assert [row["strategy"] for row in report["rows"]] == [
        "bm25",
        "vector",
        "hybrid",
    ]
    for row in report["rows"]:
        assert row["queries"] == 7
        assert 0.0 <= row["recall_at_k"] <= 1.0
        assert 0.0 <= row["mrr"] <= 1.0
        assert 0.0 <= row["hit_rate_at_k"] <= 1.0
        assert 0.0 <= row["precision_at_k"] <= 1.0
    single = invoke(
        tmp_path,
        "evaluate",
        str(FIXTURE),
        "--cases",
        str(CASES),
        "--strategy",
        "bm25",
        "--json",
    )
    assert [row["strategy"] for row in json.loads(single.stdout)["rows"]] == ["bm25"]


def test_evaluate_with_missing_cases_file_fails_cleanly(tmp_path):
    invoke(tmp_path, "index", str(FIXTURE))
    result = invoke(
        tmp_path, "evaluate", str(FIXTURE), "--cases", str(tmp_path / "nope.json")
    )
    assert result.exit_code == 2
    assert "cases" in result.stderr.lower()
