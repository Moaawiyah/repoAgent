"""Materialize benchmark repositories: local fixtures or pinned GitHub commits.

Git runs on the host only to fetch data (never target code) with hooks,
symlinks, LFS filters, and non-HTTPS protocols disabled.
"""

import shutil
from pathlib import Path

from repoagent.benchmark.models import RepositoryRef
from repoagent.domain.errors import RepositoryInvalid
from repoagent.sandbox.git import HARDENING
from repoagent.sandbox.process import ProcessRunner, SubprocessRunner

GIT_TIMEOUT, MAX_OUTPUT = 900, 8000
__all__ = ["HARDENING", "RepositoryMaterializer"]


class RepositoryMaterializer:
    def __init__(
        self,
        cache_dir: Path,
        base_dir: Path,
        process: ProcessRunner | None = None,
    ) -> None:
        self._cache, self._base = cache_dir, base_dir
        self._process = process or SubprocessRunner()

    def materialize(self, ref: RepositoryRef) -> Path:
        if not ref.is_remote:
            path = (self._base / ref.source).resolve()
            if not path.is_dir():
                raise RepositoryInvalid(f"Benchmark repository not found: {ref.source}")
            return path
        owner, name = ref.source.removesuffix(".git").split("/")[-2:]
        commit = ref.commit or ""  # remote refs are validated to carry a SHA
        target = self._cache / f"{owner}__{name}@{commit[:12]}"
        ready = target.parent / f"{target.name}.ready"
        if ready.exists() and target.is_dir():
            return target
        shutil.rmtree(target, ignore_errors=True)
        target.mkdir(parents=True)
        steps = [
            ["init", "--quiet"],
            ["remote", "add", "origin", ref.source],
            ["fetch", "--quiet", "--depth", "1", "origin", commit],
            ["checkout", "--quiet", "--detach", "FETCH_HEAD"],
        ]
        for step in steps:
            result = self._process.run(
                ["git", *HARDENING, "-C", str(target), *step], GIT_TIMEOUT, MAX_OUTPUT
            )
            if result.timed_out or result.exit_code != 0:
                shutil.rmtree(target, ignore_errors=True)
                raise RepositoryInvalid(f"Could not fetch {ref.source}@{ref.commit}")
        shutil.rmtree(target / ".git", ignore_errors=True)
        ready.write_text(commit)
        return target
