"""GraphifyService: one build feeding graph.json and Obsidian together."""

from pathlib import Path

from repoagent.application.graphify import GraphifyService
from repoagent.domain.repository import RepositorySpec
from repoagent.graph.serializer import document_to_snapshot, read_graph_json

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "rag_repo"


def test_run_with_no_outputs_returns_counts_only():
    result = GraphifyService().run(RepositorySpec(source=str(FIXTURE)))
    assert result.repository == "rag_repo"
    assert result.files > 0
    assert result.symbols == result.node_count
    assert result.edge_count > 0
    assert result.graph_json_path is None
    assert result.obsidian_path is None


def test_run_writes_graph_json(tmp_path):
    path = tmp_path / "artifacts" / "graph.json"
    result = GraphifyService().run(RepositorySpec(source=str(FIXTURE)), output=path)
    assert result.graph_json_path == str(path)
    document = read_graph_json(path)
    snapshot = document_to_snapshot(document)
    assert len(snapshot.nodes) == result.node_count
    assert len(snapshot.edges) == result.edge_count
    assert document.metadata.files == result.files
    assert document.metadata.symbols == result.symbols


def test_run_writes_obsidian_vault(tmp_path):
    vault = tmp_path / "vault"
    result = GraphifyService().run(RepositorySpec(source=str(FIXTURE)), obsidian=vault)
    assert result.obsidian_path == str(vault)
    assert (vault / "Repository.md").is_file()
    assert (vault / "Classes" / "auth.service.AuthService.md").is_file()


def test_run_shares_one_build_for_both_outputs(tmp_path):
    """graph.json and the vault must describe the identical graph build."""
    path = tmp_path / "graph.json"
    vault = tmp_path / "vault"
    result = GraphifyService().run(
        RepositorySpec(source=str(FIXTURE)), output=path, obsidian=vault
    )
    document = read_graph_json(path)
    assert len(document.nodes) == result.node_count
    assert len(document.edges) == result.edge_count
    note_count = sum(1 for _ in vault.rglob("*.md"))
    assert note_count == result.node_count + 1  # + Repository.md


def test_run_is_deterministic_across_calls(tmp_path):
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    GraphifyService().run(RepositorySpec(source=str(FIXTURE)), output=first)
    GraphifyService().run(RepositorySpec(source=str(FIXTURE)), output=second)
    assert first.read_bytes() == second.read_bytes()


def test_artifacts_dir_writes_a_repo_named_subdirectory(tmp_path):
    result = GraphifyService().run(
        RepositorySpec(source=str(FIXTURE)), artifacts_dir=tmp_path / "artifacts"
    )
    expected = tmp_path / "artifacts" / "rag_repo"
    assert result.graph_json_path == str(expected / "graph.json")
    assert result.obsidian_path == str(expected / "vault")
    assert (expected / "graph.json").is_file()
    assert (expected / "vault" / "Repository.md").is_file()


def test_explicit_output_wins_over_artifacts_dir(tmp_path):
    custom = tmp_path / "custom.json"
    result = GraphifyService().run(
        RepositorySpec(source=str(FIXTURE)),
        output=custom,
        artifacts_dir=tmp_path / "artifacts",
    )
    assert result.graph_json_path == str(custom)
    assert custom.is_file()
    # obsidian was left unset, so it still falls back under artifacts_dir
    assert result.obsidian_path == str(tmp_path / "artifacts" / "rag_repo" / "vault")


def test_malformed_python_file_does_not_crash_graphify(tmp_path):
    repo = tmp_path / "broken_repo"
    (repo / "pkg").mkdir(parents=True)
    (repo / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (repo / "pkg" / "good.py").write_text(
        "def helper():\n    return 1\n", encoding="utf-8"
    )
    (repo / "pkg" / "bad.py").write_text("def broken(:\n    pass\n", encoding="utf-8")
    result = GraphifyService().run(RepositorySpec(source=str(repo)))
    assert result.files == 3
    assert result.node_count >= 2  # the module and function from good.py survive
