"""Concurrent fetches of the same commit must not race the install step."""

import threading
from pathlib import Path

from repoagent.adapters.github_source import GitHubRepositorySource
from repoagent.domain.github import parse_github_url
from repoagent.sandbox.git import HARDENING, NO_CREDENTIALS
from tests.support.github import FakeGit


def test_concurrent_materialize_for_the_same_commit_does_not_race_install(
    tmp_path, monkeypatch
):
    """Two threads fetching the same commit must not destructively race
    _install (rmtree + rename); the second must see the ready marker and
    skip installing rather than clobber the first thread's workspace."""
    barrier = threading.Barrier(2)

    class SynchronizedGit(FakeGit):
        def run(self, argv, timeout, max_output):
            step = argv[len(HARDENING) + len(NO_CREDENTIALS) + 3]
            if step == "rev-parse":
                barrier.wait(timeout=2)
            return super().run(argv, timeout, max_output)

    installs = []
    original_install = GitHubRepositorySource._install

    def counted_install(self, staging, target):
        installs.append(target)
        original_install(self, staging, target)

    monkeypatch.setattr(GitHubRepositorySource, "_install", counted_install)
    source = GitHubRepositorySource(tmp_path, SynchronizedGit())

    results: list = []

    def run() -> None:
        results.append(source.materialize(parse_github_url("https://github.com/o/r")))

    threads = [threading.Thread(target=run) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert len(results) == 2 and results[0].path == results[1].path
    assert len(installs) == 1
    assert (Path(results[0].path) / "pkg" / "mod.py").is_file()
