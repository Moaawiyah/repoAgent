"""Safe, deterministic repository file discovery."""

import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from repoagent.analysis.gitignore import GitIgnore

IGNORED_DIRECTORIES = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "dist",
        "build",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        ".eggs",
    }
)
METADATA_FILES = frozenset(
    {
        "pyproject.toml",
        "requirements.txt",
        "setup.py",
        "setup.cfg",
        "README.md",
        "README.rst",
    }
)


@dataclass(frozen=True)
class DiscoveryResult:
    """Deterministically ordered discovery output."""

    python_files: tuple[str, ...]
    metadata_files: tuple[str, ...]
    file_count: int


class FileDiscovery:
    """Walks a repository root, skipping ignored, unsafe, and external paths.

    Symbolic links are never followed out of the repository: symlinked
    directories are skipped, and symlinked files are included only when the
    resolved target is a regular file inside the root.
    """

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    def discover(self) -> DiscoveryResult:
        python: list[str] = []
        metadata: list[str] = []
        count = 0
        root_ignore = self._load_gitignore(self._root)
        ignores = [root_ignore] if root_ignore else []
        for relative, entry in self._walk(PurePosixPath("."), ignores):
            count += 1
            if entry.name.endswith(".py"):
                python.append(relative)
            elif entry.name in METADATA_FILES:
                metadata.append(relative)
        return DiscoveryResult(tuple(sorted(python)), tuple(sorted(metadata)), count)

    def _walk(self, directory: PurePosixPath, ignores: list[GitIgnore]):
        try:
            with os.scandir(self._root.joinpath(directory)) as scan:
                entries = sorted(scan, key=lambda item: item.name)
        except OSError:
            return
        for entry in entries:
            relative = directory / entry.name
            if entry.is_symlink():
                included = self._safe_link(entry) is not None and not self._ignored(
                    relative.as_posix(), False, ignores
                )
                if included:
                    yield relative.as_posix(), entry
                continue
            if entry.is_dir(follow_symlinks=False):
                yield from self._walk_dir(relative, entry, ignores)
            elif entry.is_file(follow_symlinks=False) and not self._ignored(
                relative.as_posix(), False, ignores
            ):
                yield relative.as_posix(), entry

    def _walk_dir(self, relative: PurePosixPath, entry, ignores: list[GitIgnore]):
        if entry.name in IGNORED_DIRECTORIES or self._ignored(
            relative.as_posix(), True, ignores
        ):
            return
        local = self._load_gitignore(self._root.joinpath(relative))
        yield from self._walk(relative, ignores + ([local] if local else []))

    def _safe_link(self, entry) -> Path | None:
        try:
            target = Path(entry.path).resolve(strict=True)
        except OSError:
            return None
        if target.is_dir() or not target.is_file():
            return None
        return target if target.is_relative_to(self._root) else None

    @staticmethod
    def _ignored(relative: str, is_dir: bool, ignores: list[GitIgnore]) -> bool:
        return any(rule.matches(relative, is_dir) for rule in ignores)

    @staticmethod
    def _load_gitignore(directory: Path) -> GitIgnore | None:
        path = directory / ".gitignore"
        try:
            return GitIgnore(path.read_text(encoding="utf-8").splitlines())
        except (OSError, UnicodeError):
            return None
