"""Input validation and immutable domain serialization."""

import pytest
from pydantic import ValidationError

from repoagent.domain.repository import RepositorySpec
from repoagent.domain.tasks import TaskKind, TaskRecord, TaskRequest


@pytest.mark.parametrize(
    "source",
    [
        "http://github.com/a/b",
        "https://user:secret@github.com/a/b",
        "https://gitlab.com/a/b",
        "git@github.com:a/b.git",
        "https://github.com/a/b/issues/1",
        "https://github.com/a/b?token=secret",
        "https://github.com/a/b#main",
        "https://github.com/a/..",
        "https://github.com:443/a/b",
        "https://github.com/a/.git",
        "",
        "/nonexistent-repoagent-source",
    ],
)
def test_invalid_sources(source):
    with pytest.raises(ValidationError):
        RepositorySpec(source=source)


def test_local_and_remote_sources(tmp_path):
    assert RepositorySpec(source=str(tmp_path)).source == str(tmp_path.resolve())
    url = "https://github.com/Moaawiyah/repoAgent.git"
    assert RepositorySpec(source=url + "/").source == url
    regular_file = tmp_path / "file"
    regular_file.touch()
    with pytest.raises(ValidationError):
        RepositorySpec(source=str(regular_file))


@pytest.mark.parametrize("commit", ["", " ", "main\x00bad"])
def test_invalid_commit(commit):
    with pytest.raises(ValidationError):
        RepositorySpec(source="https://github.com/a/b", commit=commit)


def test_record_roundtrip_and_immutability():
    request = TaskRequest(
        kind="fix",
        repository=RepositorySpec(source="https://github.com/a/b", commit="feature/x"),
        description="Unexpected exception",
    )
    record = TaskRecord(request=request)
    assert TaskRecord.model_validate_json(record.model_dump_json()) == record
    assert record.created_at.utcoffset().total_seconds() == 0
    with pytest.raises(ValidationError):
        record.status = "running"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"kind": "index"},
        {"kind": "benchmark", "suite": "unknown"},
        {"kind": "benchmark", "suite": "synthetic", "description": "irrelevant"},
        {"kind": "fix", "description": " "},
        {"kind": "index", "description": "irrelevant"},
        {"kind": "ask"},
        {"kind": "index", "suite": "synthetic"},
    ],
)
def test_invalid_requests(kwargs):
    if kwargs["kind"] != "benchmark" and kwargs != {"kind": "index"}:
        kwargs["repository"] = RepositorySpec(source="https://github.com/a/b")
    with pytest.raises(ValidationError):
        TaskRequest(**kwargs)


def test_benchmark_request():
    request = TaskRequest(kind=TaskKind.BENCHMARK, suite="synthetic")
    assert request.repository is None
