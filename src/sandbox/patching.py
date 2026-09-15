"""Apply a validated unified diff to a disposable workspace copy only."""

import os
from pathlib import Path, PurePosixPath

from repoagent.adapters.patch_validator import StaticPatchValidator
from repoagent.domain.errors import WorkspaceError


class WorkspacePatcher:
    """Re-verifies context against the copy, then writes without following links."""

    def apply(self, workspace: Path, unified_diff: str) -> list[str]:
        """Return changed paths; raise ``WorkspaceError`` if the patch cannot apply."""
        validator = StaticPatchValidator(workspace)
        try:
            patched, _ = validator.apply(unified_diff)
        except (OSError, SyntaxError, UnicodeError, ValueError) as error:
            raise WorkspaceError(f"Patch did not apply cleanly: {error}") from None
        root = workspace.resolve()
        for path, content in patched.items():
            target = root / path
            if target.is_symlink() or not target.resolve().is_relative_to(root):
                raise WorkspaceError(f"Unsafe patch target: {path}")
            flags = os.O_WRONLY | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0)
            with os.fdopen(os.open(target, flags), "w", encoding="utf-8") as stream:
                stream.write(content)
        return sorted(patched)


MAX_OVERLAY_BYTES = 1_000_000


def write_overlay(workspace: Path, files: dict[str, str]) -> None:
    """Write evaluator-supplied files (e.g. hidden tests) inside the copy only."""
    root = workspace.resolve()
    for path, content in files.items():
        relative = PurePosixPath(path)
        unsafe = relative.is_absolute() or ".." in relative.parts or "\\" in path
        if unsafe or not path.endswith(".py") or len(content) > MAX_OVERLAY_BYTES:
            raise WorkspaceError(f"Unsafe overlay file: {path}")
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_symlink() or not target.parent.resolve().is_relative_to(root):
            raise WorkspaceError(f"Unsafe overlay file: {path}")
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0)
        with os.fdopen(os.open(target, flags, 0o644), "w", encoding="utf-8") as stream:
            stream.write(content)
