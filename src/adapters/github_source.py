"""Fetch a validated public GitHub repository into an isolated workspace.

Only data is downloaded (shallow, hardened git, no credentials); nothing in
the repository is executed on the host. Snapshots are keyed by the exact
commit, so repeated jobs reuse one workspace and its retrieval index.
"""

import re
import shutil
import threading
from pathlib import Path
from uuid import uuid4

from repoagent.domain.errors import RepositoryInvalid
from repoagent.domain.github import GitHubRepository, RepositoryHandle
from repoagent.sandbox.git import HARDENING, NO_CREDENTIALS
from repoagent.sandbox.process import ProcessRunner, SubprocessRunner

MAX_OUTPUT = 8000
_SHA = re.compile(r"^[0-9a-f]{40}$")

# Serializes install of one target directory across concurrent threads in
# this process (the local job queue is a thread pool); without this, two
# jobs fetching the same commit can both pass the "not ready yet" check and
# race a destructive rmtree()+rename() against each other's installed copy.
_INSTALL_LOCKS: dict[str, threading.Lock] = {}
_REGISTRY_LOCK = threading.Lock()


def _install_lock(target: Path) -> threading.Lock:
    key = str(target)
    with _REGISTRY_LOCK:
        return _INSTALL_LOCKS.setdefault(key, threading.Lock())


def tree_bytes(root: Path) -> int:
    """Total regular-file size without following symlinks."""
    return sum(
        path.lstat().st_size
        for path in root.rglob("*")
        if path.is_file() and not path.is_symlink()
    )


class GitHubRepositorySource:
    def __init__(
        self,
        workspace_dir: Path,
        process: ProcessRunner | None = None,
        *,
        timeout: int = 300,
        max_bytes: int = 200 * 1024 * 1024,
    ) -> None:
        self._root, self._process = workspace_dir, process or SubprocessRunner()
        self._timeout, self._max_bytes = timeout, max_bytes

    def _git(self, target: Path, *step: str) -> str:
        argv = ["git", *HARDENING, *NO_CREDENTIALS, "-C", str(target), *step]
        result = self._process.run(argv, self._timeout, MAX_OUTPUT)
        if result.timed_out or result.exit_code != 0:
            raise RepositoryInvalid(
                "Could not fetch the repository (is it public and reachable?)"
            )
        return result.stdout

    def materialize(self, repository: GitHubRepository) -> RepositoryHandle:
        staging = self._root / ".staging" / uuid4().hex
        staging.mkdir(parents=True)
        try:
            commit = self._fetch(repository, staging)
            target = self._root / f"{repository.owner}__{repository.name}@{commit[:12]}"
            with _install_lock(target):
                if not (target.with_name(target.name + ".ready")).exists():
                    self._install(staging, target)
        finally:
            shutil.rmtree(staging, ignore_errors=True)
        return RepositoryHandle(
            source=repository.url, name=repository.slug, path=str(target), commit=commit
        )

    def _fetch(self, repository: GitHubRepository, staging: Path) -> str:
        self._git(staging, "init", "--quiet")
        self._git(staging, "remote", "add", "origin", repository.url)
        self._git(
            staging, "fetch", "--quiet", "--depth", "1", "--no-tags", "origin", "HEAD"
        )
        commit = self._git(staging, "rev-parse", "FETCH_HEAD").strip()
        if not _SHA.fullmatch(commit):
            raise RepositoryInvalid("Fetched repository has no resolvable commit")
        self._git(staging, "checkout", "--quiet", "--detach", commit)
        return commit

    def _install(self, staging: Path, target: Path) -> None:
        shutil.rmtree(staging / ".git", ignore_errors=True)
        if tree_bytes(staging) > self._max_bytes:
            raise RepositoryInvalid("Repository exceeds the configured size limit")
        shutil.rmtree(target, ignore_errors=True)
        try:
            staging.rename(target)
        except OSError:
            if not target.is_dir():
                raise RepositoryInvalid("Could not prepare the workspace") from None
        target.with_name(target.name + ".ready").write_text("ready")
