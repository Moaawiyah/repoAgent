"""Public SDK analyze behavior: typed results and validation."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from repoagent import RepoAgent, RepositoryAnalysis, Settings

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "analysis_repo"


def test_analyze_returns_typed_deterministic_result(tmp_path):
    client = RepoAgent(settings=Settings(data_dir=tmp_path / "data"))
    analysis = client.analyze(FIXTURE)
    assert isinstance(analysis, RepositoryAnalysis)
    assert analysis.repository_name == FIXTURE.name
    assert analysis.class_count == 2
    assert analysis.method_count == 4
    assert analysis.test_count == 1
    assert len(analysis.errors) == 1
    assert client.analyze(FIXTURE) == analysis
    assert not (tmp_path / "data").exists()


def test_analyze_validates_sources_like_other_inputs(tmp_path):
    client = RepoAgent(settings=Settings(data_dir=tmp_path / "data"))
    with pytest.raises(ValidationError):
        client.analyze(tmp_path / "missing")
    with pytest.raises(ValidationError):
        client.analyze("https://gitlab.com/a/b")
    assert not (tmp_path / "data").exists()


def test_analyze_preserves_relative_and_absolute_paths(tmp_path):
    client = RepoAgent(settings=Settings(data_dir=tmp_path))
    analysis = client.analyze(str(FIXTURE))
    assert analysis.repository_root == str(FIXTURE.resolve())
    assert analysis.files[0].path.startswith("app/")
