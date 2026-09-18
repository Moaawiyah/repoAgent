"""GitHub URL validation and hardened, credential-free, size-bounded fetching."""

import pytest

from repoagent.adapters.github_source import GitHubRepositorySource
from repoagent.domain.errors import RepositoryInvalid
from repoagent.domain.github import parse_github_url
from repoagent.sandbox.git import HARDENING
from tests.support.github import SHA, FakeGit


@pytest.mark.parametrize(
    "raw, slug",
    [
        ("https://github.com/psf/requests", "psf/requests"),
        ("https://github.com/psf/requests.git", "psf/requests"),
        ("  https://www.github.com/a-b/c_d.e/  ", "a-b/c_d.e"),
    ],
)
def test_valid_urls(raw, slug):
    assert parse_github_url(raw).slug == slug


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "github.com/o/r",
        "http://github.com/o/r",
        "ssh://git@github.com/o/r",
        "git@github.com:o/r.git",
        "https://gitlab.com/o/r",
        "https://user:pw@github.com/o/r",
        "https://github.com:8443/o/r",
        "https://github.com/o",
        "https://github.com/o/r/tree/main",
        "https://github.com/o/r?x=1",
        "https://github.com/o/r#frag",
        "https://github.com/-o/r",
        "https://github.com/o/..",
        "https://github.com/o/.hidden",
        "https://github.com/o/r;rm -rf",
        "https://github.com/o/--upload-pack=x",
        "file:///etc/passwd",
        "https://github.com/" + "o" * 300,
    ],
)
def test_invalid_urls_are_rejected(raw):
    with pytest.raises(RepositoryInvalid):
        parse_github_url(raw)


def test_fetch_is_hardened_shallow_and_cached_by_commit(tmp_path):
    git = FakeGit()
    source = GitHubRepositorySource(tmp_path, git)
    handle = source.materialize(parse_github_url("https://github.com/o/r"))
    assert handle.commit == SHA and handle.name == "o/r"
    assert handle.source == "https://github.com/o/r"
    assert handle.path.endswith(f"o__r@{SHA[:12]}")
    assert (tmp_path / f"o__r@{SHA[:12]}" / "pkg" / "mod.py").is_file()
    for argv in git.calls:
        assert argv[: 1 + len(HARDENING)] == ["git", *HARDENING]
        assert "credential.helper=" in argv
    fetch = next(argv for argv in git.calls if "fetch" in argv)
    assert fetch[-5:] == ["--depth", "1", "--no-tags", "origin", "HEAD"]
    again = source.materialize(parse_github_url("https://github.com/o/r"))
    assert again.path == handle.path
    assert not list((tmp_path / ".staging").iterdir())


@pytest.mark.parametrize("step", ["fetch", "checkout"])
def test_failed_git_steps_clean_up(tmp_path, step):
    source = GitHubRepositorySource(tmp_path, FakeGit(fail_on=step))
    with pytest.raises(RepositoryInvalid, match="public and reachable"):
        source.materialize(parse_github_url("https://github.com/o/r"))
    assert not list((tmp_path / ".staging").iterdir())


def test_unresolvable_commit_and_size_limit_are_rejected(tmp_path):
    bad = GitHubRepositorySource(tmp_path / "a", FakeGit(commit="HEAD"))
    with pytest.raises(RepositoryInvalid, match="commit"):
        bad.materialize(parse_github_url("https://github.com/o/r"))
    big = FakeGit(files={"blob.py": "x" * 5000})
    small = GitHubRepositorySource(tmp_path / "b", big, max_bytes=1000)
    with pytest.raises(RepositoryInvalid, match="size limit"):
        small.materialize(parse_github_url("https://github.com/o/r"))
    assert not list((tmp_path / "b").glob("o__r@*"))
