"""Graph inspection and Obsidian export CLI behavior."""

import json
from pathlib import Path

from typer.testing import CliRunner

from repoagent.cli.main import app

runner = CliRunner()
FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "rag_repo"
CASES = Path(__file__).resolve().parents[1] / "fixtures" / "rag_cases.json"


def invoke(tmp_path, *args):
    return runner.invoke(app, ["--data-dir", str(tmp_path / "data"), *args])


def test_graph_summary_and_json(tmp_path):
    result = invoke(tmp_path, "graph", str(FIXTURE))
    assert result.exit_code == 0, result.output
    assert "RepoAgent Repository Graph" in result.output
    assert "Nodes: " in result.output and "Edges: " in result.output
    raw = invoke(tmp_path, "graph", str(FIXTURE), "--json").stdout
    data = json.loads(raw)
    assert set(data) == {"nodes", "edges"}
    assert data["nodes"] and data["edges"]


def test_graph_symbol_inspection(tmp_path):
    result = invoke(
        tmp_path,
        "graph",
        str(FIXTURE),
        "--symbol",
        "auth.service.AuthService.authenticate",
    )
    assert result.exit_code == 0, result.output
    assert "CALLS → auth.service.AuthService.verify_password" in result.output
    assert "CALLS ← auth.controller.AuthController.login" in result.output
    assert "CONTAINS ← auth.service.AuthService" in result.output
    raw = invoke(
        tmp_path,
        "graph",
        str(FIXTURE),
        "--symbol",
        "auth.service.AuthService.authenticate",
        "--json",
    ).stdout
    inspection = json.loads(raw)
    assert inspection["symbol"] == "auth.service.AuthService.authenticate"
    assert inspection["outgoing"] and inspection["parents"]


def test_graph_unknown_symbol_is_operational_error(tmp_path):
    result = invoke(tmp_path, "graph", str(FIXTURE), "--symbol", "no.Such")
    assert result.exit_code == 1
    assert "not found" in result.stderr


def test_hybrid_graph_search_requires_index(tmp_path):
    result = invoke(
        tmp_path,
        "search",
        str(FIXTURE),
        "where does login verify the password",
        "--strategy",
        "hybrid_graph",
        "--json",
    )
    assert result.exit_code == 1
    assert "not been indexed" in result.stderr


def test_hybrid_graph_search_with_evidence(tmp_path):
    invoke(tmp_path, "index", str(FIXTURE))
    result = invoke(
        tmp_path,
        "search",
        str(FIXTURE),
        "where does login verify the password",
        "--strategy",
        "hybrid_graph",
        "--top-k",
        "5",
        "--json",
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert data["strategy"] == "hybrid_graph"
    qualified = [r["chunk"]["qualified_name"] for r in data["results"]]
    assert "auth.service.AuthService.verify_password" in qualified
    evidence_kinds = {note["kind"] for r in data["results"] for note in r["evidence"]}
    assert evidence_kinds & {"graph", "hybrid_seed", "bm25", "vector"}
    graph_notes = [
        note
        for r in data["results"]
        for note in r["evidence"]
        if note["kind"] == "graph" and note["path"]
    ]
    assert graph_notes, "expected at least one graph path with hops"
    assert graph_notes[0]["path"][0]["relation"] in {"calls", "contains", "defines"}


def test_export_obsidian_happy_path(tmp_path):
    vault = tmp_path / "repoagent-vault"
    result = invoke(tmp_path, "export-obsidian", str(FIXTURE), str(vault), "--json")
    assert result.exit_code == 0, result.output
    summary = json.loads(result.stdout)
    assert summary["notes"] > 1
    assert (vault / "Repository.md").is_file()


def test_export_obsidian_overwrite_guard(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "keep.txt").write_text("mine", encoding="utf-8")
    blocked = invoke(tmp_path, "export-obsidian", str(FIXTURE), str(vault))
    assert blocked.exit_code == 1
    assert "overwrite" in blocked.stderr
    assert (vault / "keep.txt").exists()
    allowed = invoke(
        tmp_path, "export-obsidian", str(FIXTURE), str(vault), "--overwrite"
    )
    assert allowed.exit_code == 0, allowed.output
    assert (vault / "keep.txt").exists()


def test_evaluate_covers_four_strategies(tmp_path):
    invoke(tmp_path, "index", str(FIXTURE))
    result = invoke(tmp_path, "evaluate", str(FIXTURE), "--cases", str(CASES), "--json")
    assert result.exit_code == 0, result.output
    rows = json.loads(result.stdout)["rows"]
    assert [row["strategy"] for row in rows] == [
        "bm25",
        "vector",
        "hybrid",
        "hybrid_graph",
    ]
