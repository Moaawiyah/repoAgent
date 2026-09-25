"""Disposable workspace copies that exclude links, secrets, and VCS metadata.

Files are opened with ``O_NOFOLLOW`` and copied as regular content, so a
hostile repository cannot smuggle host paths into the sandbox through
symlinks, hard-link tricks, device files, or FIFOs.
"""

import fnmatch
import hashlib
import os
import shutil
import stat
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from repoagent.domain.errors import WorkspaceError

SKIP_DIRS = frozenset(
    {".git", ".hg", ".svn", ".venv", "venv", "node_modules", "__pycache__"}
    | {".mypy_cache", ".pytest_cache", ".ruff_cache", ".tox", ".nox"}
)
SECRET_PATTERNS: tuple[str, ...] = (
    ".env",
    ".env.*",
    ".netrc",
    ".pypirc",
    ".npmrc",
    "*.pem",
    "*.key",
)
SECRET_PATTERNS += ("id_rsa*", "id_ed25519*", "*.p12", ".git-credentials")
FINGERPRINT_SKIP = frozenset({".venv", "venv", "node_modules"})


@dataclass(frozen=True)
class WorkspaceLimits:
    max_files: int = 20000
    max_total_bytes: int = 500_000_000
    max_file_bytes: int = 50_000_000


@dataclass
class Workspace:
    root: Path
    path: Path
    skipped: list[str] = field(default_factory=list)


class WorkspaceManager:
    """Creates and destroys host-private repository copies."""

    def __init__(self, base_dir: Path | None, limits: WorkspaceLimits) -> None:
        self._base, self._limits = base_dir, limits

    def create(self, repository: Path) -> Workspace:
        source = repository.resolve()
        if not source.is_dir():
            raise WorkspaceError("Repository is not a readable directory")
        if self._base is not None:
            self._base.mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix="repoagent-ws-", dir=self._base)).resolve()
        if source.is_relative_to(root) or root.is_relative_to(source):
            shutil.rmtree(root, ignore_errors=True)
            raise WorkspaceError("Workspace must be outside the repository")
        workspace = Workspace(root=root, path=root / "repo")
        try:
            self._copy(source, workspace)
        except (OSError, WorkspaceError) as error:
            self.destroy(workspace)
            raise WorkspaceError(f"Workspace copy failed: {error}") from None
        return workspace

    def _copy(self, source: Path, workspace: Workspace) -> None:
        files = size = 0
        for current, dirs, names in os.walk(source, followlinks=False):
            here = Path(current)
            relative = here.relative_to(source)
            (workspace.path / relative).mkdir(mode=0o755, parents=True, exist_ok=True)
            dirs[:] = sorted(
                d for d in dirs if d not in SKIP_DIRS and not (here / d).is_symlink()
            )
            for name in sorted(names):
                info = os.lstat(here / name)
                rel = (relative / name).as_posix()
                if not stat.S_ISREG(info.st_mode) or _is_secret(name):
                    workspace.skipped.append(rel)
                    continue
                files, size = files + 1, size + info.st_size
                if (
                    files > self._limits.max_files
                    or size > self._limits.max_total_bytes
                    or info.st_size > self._limits.max_file_bytes
                ):
                    raise WorkspaceError("Repository exceeds workspace size limits")
                _copy_regular(here / name, workspace.path / relative / name)

    @staticmethod
    def destroy(workspace: Workspace) -> bool:
        shutil.rmtree(workspace.root, ignore_errors=True)
        return not workspace.root.exists()


def _is_secret(name: str) -> bool:
    return name != ".env.example" and any(
        fnmatch.fnmatch(name, pattern) for pattern in SECRET_PATTERNS
    )


def _copy_regular(source: Path, target: Path) -> None:
    descriptor = os.open(source, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(descriptor, "rb") as reader:
        if not stat.S_ISREG(os.fstat(reader.fileno()).st_mode):
            raise WorkspaceError("Refusing to copy a non-regular file")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        with os.fdopen(os.open(target, flags, 0o644), "wb") as writer:
            shutil.copyfileobj(reader, writer)


def fingerprint(repository: Path, limit: int = 200_000) -> str:
    """Metadata digest used to prove the original repository was not touched."""
    digest, count = hashlib.sha256(), 0
    root = repository.resolve()
    for current, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in FINGERPRINT_SKIP)
        for name in sorted([*names, *dirs]):
            info = os.lstat(Path(current) / name)
            rel = (Path(current) / name).relative_to(root).as_posix()
            digest.update(
                f"{rel}|{info.st_mode}|{info.st_size}|{info.st_mtime_ns}\n".encode()
            )
            count += 1
            if count >= limit:
                return digest.hexdigest()
    return digest.hexdigest()
