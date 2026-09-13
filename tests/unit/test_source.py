"""Repository source validation and materialization."""

import os
from pathlib import Path

import pytest

from repoagent.analysis.source import LocalRepositorySource
from repoagent.domain.errors import RepositoryInvalid
from repoagent.domain.repository import RepositorySpec


def spec(source: str) -> RepositorySpec:
    return RepositorySpec.model_validate(
        {"source": source}, context={"persisted": True}
    )


def test_materializes_existing_directories(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    assert LocalRepositorySource().materialize(spec(str(root))) == root


def test_rejects_files_and_missing_paths(tmp_path):
    target = tmp_path / "file.txt"
    target.write_text("x")
    with pytest.raises(RepositoryInvalid):
        LocalRepositorySource().materialize(spec(str(target)))
    with pytest.raises(RepositoryInvalid):
        LocalRepositorySource().materialize(spec(str(tmp_path / "missing")))


@pytest.mark.skipif(
    not hasattr(os, "geteuid") or os.geteuid() == 0,
    reason="requires an unprivileged user",
)
def test_rejects_unreadable_directories(tmp_path):
    root = tmp_path / "locked"
    root.mkdir()
    root.chmod(0o000)
    try:
        with pytest.raises(RepositoryInvalid, match="not readable"):
            LocalRepositorySource().materialize(spec(str(root)))
    finally:
        root.chmod(0o755)


def test_repository_source_protocol_is_satisfied(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    source: object = LocalRepositorySource()
    materialized = source.materialize(spec(str(root)))
    assert isinstance(materialized, Path) and materialized.is_dir()
