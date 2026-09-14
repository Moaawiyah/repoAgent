"""Obsidian vault export: determinism, safety, and structure."""

from pathlib import Path

import pytest

from repoagent.analysis.analyzer import RepositoryAnalyzer
from repoagent.domain.errors import ExportError
from repoagent.domain.repository import RepositorySpec
from repoagent.export.notes import safe_name
from repoagent.export.obsidian import ObsidianExporter
from repoagent.graph.builder import RepositoryGraphBuilder

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "rag_repo"


@pytest.fixture(scope="module")
def snapshot():
    analysis = RepositoryAnalyzer().analyze(RepositorySpec(source=str(FIXTURE)))
    return RepositoryGraphBuilder().build(analysis).to_snapshot()


def export(snapshot, tmp_path, name="vault", **kwargs):
    destination = tmp_path / name
    exporter = ObsidianExporter(FIXTURE.resolve())
    return exporter.export(snapshot, destination, **kwargs), destination


def test_vault_structure_is_created(snapshot, tmp_path):
    summary, destination = export(snapshot, tmp_path)
    assert summary.notes == len(snapshot.nodes) + 1
    assert (destination / "Repository.md").is_file()
    assert (destination / "Classes" / "auth.service.AuthService.md").is_file()
    assert (
        destination / "Methods" / "auth.service.AuthService.verify_password.md"
    ).is_file()
    assert (destination / "Modules" / "auth.service.md").is_file()


def test_export_is_deterministic(snapshot, tmp_path):
    _, first = export(snapshot, tmp_path, name="v1")
    _, second = export(snapshot, tmp_path, name="v2")
    first_files = {p.relative_to(first): p.read_bytes() for p in first.rglob("*.md")}
    second_files = {p.relative_to(second): p.read_bytes() for p in second.rglob("*.md")}
    assert first_files == second_files


def test_notes_contain_metadata_links_and_source(snapshot, tmp_path):
    _, destination = export(snapshot, tmp_path)
    note = (
        destination / "Methods" / "auth.service.AuthService.verify_password.md"
    ).read_text(encoding="utf-8")
    assert "# auth.service.AuthService.verify_password" in note
    assert "**Type:** method" in note
    assert "**File:** `auth/service.py`" in note
    assert "**Lines:** 16-18" in note
    assert "[[auth.service.AuthService]]" in note
    assert "Called by:" in note
    assert "```python" in note
    assert "def verify_password" in note


def test_unresolved_targets_are_not_wikilinks(snapshot, tmp_path):
    _, destination = export(snapshot, tmp_path)
    login = (
        destination / "Methods" / "auth.controller.AuthController.login.md"
    ).read_text(encoding="utf-8")
    assert "Calls:" in login
    assert "`auth.service.AuthService.authenticate`" in login
    assert "- [[auth.service.AuthService.authenticate]]" not in login


def test_unsafe_identifiers_are_sanitized(snapshot, tmp_path):
    assert safe_name("mod/Class..name") == "mod_Class..name"
    assert safe_name("..evil") == "evil"
    assert safe_name("$$$") == "___"
    assert "/" not in safe_name("../../etc/passwd")


def test_non_empty_destination_requires_overwrite(snapshot, tmp_path):
    destination = tmp_path / "existing"
    destination.mkdir()
    (destination / "user-file.txt").write_text("keep me", encoding="utf-8")
    with pytest.raises(ExportError):
        export(snapshot, tmp_path, name="existing")
    assert (destination / "user-file.txt").read_text(encoding="utf-8") == "keep me"
    summary, _ = export(snapshot, tmp_path, name="existing", overwrite=True)
    assert summary.notes > 0
    assert (destination / "user-file.txt").exists()


def test_source_omitted_when_file_unreadable(tmp_path):
    analysis = RepositoryAnalyzer().analyze(RepositorySpec(source=str(FIXTURE)))
    graph = RepositoryGraphBuilder().build(analysis).to_snapshot()
    broken_root = tmp_path / "missing-root"
    summary = ObsidianExporter(broken_root).export(
        graph, tmp_path / "vault-nosrc", overwrite=True
    )
    assert summary.notes == len(graph.nodes) + 1
