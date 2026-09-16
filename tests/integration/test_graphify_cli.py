"""``repoagent graphify``: combined graph.json + Obsidian CLI behavior."""

import json
from pathlib import Path

from typer.testing import CliRunner

from repoagent.cli.main import app
from repoagent.graph.serializer import document_to_snapshot, read_graph_json

runner = CliRunner()
FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "rag_repo"


def invoke(tmp_path, *args):
    return runner.invoke(app, ["--data-dir", str(tmp_path / "data"), *args])


def test_graphify_text_summary(tmp_path):
    result = invoke(tmp_path, "graphify", str(FIXTURE))
    assert result.exit_code == 0, result.output
    assert "Graphify complete" in result.output
    assert "Files:" in result.output
    assert "Symbols:" in result.output
    assert "Nodes:" in result.output
    assert "Relationships:" in result.output
    assert "graph.json:" not in result.output
    assert "Obsidian:" not in result.output


def test_graphify_json_mode_is_machine_readable(tmp_path):
    result = invoke(tmp_path, "graphify", str(FIXTURE), "--json")
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert set(data) == {
        "repository",
        "files",
        "symbols",
        "node_count",
        "edge_count",
        "graph_json_path",
        "obsidian_path",
    }
    assert data["node_count"] > 0
    assert data["graph_json_path"] is None


def test_graphify_writes_graph_json(tmp_path):
    output = tmp_path / "artifacts" / "graph.json"
    result = invoke(tmp_path, "graphify", str(FIXTURE), "--output", str(output))
    assert result.exit_code == 0, result.output
    assert f"graph.json: {output}" in result.output
    document = read_graph_json(output)
    snapshot = document_to_snapshot(document)
    assert snapshot.nodes and snapshot.edges


def test_graphify_writes_obsidian_vault(tmp_path):
    vault = tmp_path / "artifacts" / "obsidian"
    result = invoke(tmp_path, "graphify", str(FIXTURE), "--obsidian", str(vault))
    assert result.exit_code == 0, result.output
    assert f"Obsidian:   {vault}" in result.output
    assert (vault / "Repository.md").is_file()


def test_graphify_combined_output_and_obsidian(tmp_path):
    output = tmp_path / "graph.json"
    vault = tmp_path / "vault"
    result = invoke(
        tmp_path,
        "graphify",
        str(FIXTURE),
        "--output",
        str(output),
        "--obsidian",
        str(vault),
        "--json",
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    document = read_graph_json(output)
    assert len(document.nodes) == data["node_count"]
    note_count = sum(1 for _ in vault.rglob("*.md"))
    assert note_count == data["node_count"] + 1


def test_graphify_obsidian_overwrite_guard(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "keep.txt").write_text("mine", encoding="utf-8")
    blocked = invoke(tmp_path, "graphify", str(FIXTURE), "--obsidian", str(vault))
    assert blocked.exit_code == 1
    assert "overwrite" in blocked.stderr
    allowed = invoke(
        tmp_path, "graphify", str(FIXTURE), "--obsidian", str(vault), "--overwrite"
    )
    assert allowed.exit_code == 0, allowed.output
    assert (vault / "keep.txt").exists()


def test_graphify_artifacts_flag_organizes_by_repo_name(tmp_path):
    artifacts = tmp_path / "artifacts"
    result = invoke(tmp_path, "graphify", str(FIXTURE), "--artifacts", str(artifacts))
    assert result.exit_code == 0, result.output
    repo_dir = artifacts / "rag_repo"
    assert f"graph.json: {repo_dir / 'graph.json'}" in result.output
    assert f"Obsidian:   {repo_dir / 'vault'}" in result.output
    assert (repo_dir / "graph.json").is_file()
    assert (repo_dir / "vault" / "Repository.md").is_file()


def test_graphify_preserves_existing_graph_and_export_obsidian_commands(tmp_path):
    """Backward compatibility: the original M4 commands still work unchanged."""
    graph_result = invoke(tmp_path, "graph", str(FIXTURE))
    assert graph_result.exit_code == 0, graph_result.output
    export_result = invoke(
        tmp_path, "export-obsidian", str(FIXTURE), str(tmp_path / "legacy-vault")
    )
    assert export_result.exit_code == 0, export_result.output
