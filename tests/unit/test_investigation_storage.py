"""Investigation persistence and read-only export boundaries."""

from uuid import uuid4

import pytest

from repoagent.adapters.investigation_store import InvestigationStore
from repoagent.domain.errors import ExportError, StorageError
from repoagent.domain.investigation import InvestigationReport, Issue
from repoagent.export.investigation import export_investigation_note


@pytest.fixture
def report(tmp_path):
    return InvestigationReport(
        task_id=str(uuid4()),
        repository=str(tmp_path / "source"),
        issue=Issue(description="login fails"),
        issue_summary="login fails",
    )


def test_report_reopens_with_trace(tmp_path, report):
    directory = tmp_path / "data"
    path = InvestigationStore(directory).save(report)
    assert path.exists()
    assert InvestigationStore(directory).get(report.task_id) == report
    assert not list(directory.glob("tmp*"))


def test_missing_and_invalid_report(tmp_path, report):
    store = InvestigationStore(tmp_path)
    with pytest.raises(StorageError):
        store.get(report.task_id)
    (tmp_path / f"{report.task_id}.json").write_text("invalid")
    with pytest.raises(StorageError):
        store.get(report.task_id)


def test_repository_storage_rejected(report):
    from pathlib import Path

    with pytest.raises(StorageError):
        InvestigationStore(Path(report.repository) / "data").save(report)
    with pytest.raises(ExportError):
        export_investigation_note(report, Path(report.repository) / "vault")
    assert not Path(report.repository).exists()


def test_symlink_export_rejected(tmp_path, report):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "Investigations").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ExportError):
        export_investigation_note(report, vault)


def test_export_invalid_identifier(tmp_path, report):
    malicious = report.model_copy(update={"task_id": "../../escape"})
    with pytest.raises(ExportError):
        export_investigation_note(malicious, tmp_path / "vault")
    assert not (tmp_path / "vault").exists()


def test_storage_failure_sanitized(tmp_path, report):
    file = tmp_path / "file"
    file.write_text("x")
    with pytest.raises(StorageError, match="persist"):
        InvestigationStore(file).save(report)
