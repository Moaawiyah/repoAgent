"""Validate and apply a constrained unified diff only in memory."""

import ast
from pathlib import Path, PurePosixPath

from repoagent.domain.repair import StaticValidation

MAX_FILES, MAX_CHANGED_LINES = 10, 400


class StaticPatchValidator:
    """Reject unsafe or stale patches without writing a target file."""

    def __init__(self, repository: str | Path) -> None:
        self._root = Path(repository).resolve()

    def validate(self, unified_diff: str) -> StaticValidation:
        """Parse, context-check, and syntax-check a standard text patch."""
        try:
            changes = self._parse(unified_diff)
            if len(changes) > MAX_FILES:
                raise ValueError("Patch changes too many files")
            changed = 0
            files = []
            for path, hunks in changes.items():
                target = self._target(path)
                before = target.read_text(encoding="utf-8")
                after, count = self._apply(before, hunks)
                changed += count
                if changed > MAX_CHANGED_LINES:
                    raise ValueError("Patch changes too many lines")
                if path.endswith(".py"):
                    ast.parse(after, filename=path)
                files.append(path)
            return StaticValidation(
                valid=True, changed_files=files, changed_lines=changed
            )
        except (OSError, SyntaxError, UnicodeError, ValueError) as error:
            return StaticValidation(valid=False, errors=[str(error)])

    def _target(self, path: str) -> Path:
        candidate = PurePosixPath(path)
        if candidate.is_absolute() or ".." in candidate.parts or "\\" in path:
            raise ValueError("Unsafe patch path")
        target = (self._root / candidate).resolve()
        if (
            not target.is_relative_to(self._root)
            or not target.is_file()
            or target.is_symlink()
        ):
            raise ValueError(f"Patch target is unavailable: {path}")
        return target

    def _parse(self, text: str) -> dict[str, list[list[str]]]:
        if not text.strip() or "GIT binary patch" in text or "Binary files" in text:
            raise ValueError("Patch must be a non-binary unified diff")
        lines, changes, current, hunk = text.splitlines(), {}, None, None
        for line in lines:
            if line.startswith("--- "):
                continue
            if line.startswith("+++ "):
                raw = line[4:].split("\t", 1)[0]
                if not raw.startswith("b/"):
                    raise ValueError("Patch requires b/ target paths")
                current = raw[2:]
                changes.setdefault(current, [])
            elif line.startswith("@@ ") and line.endswith(" @@"):
                if current is None:
                    raise ValueError("Hunk has no target file")
                hunk = []
                changes[current].append(hunk)
            elif hunk is not None:
                if line.startswith((" ", "+", "-")):
                    hunk.append(line)
                elif line.startswith("\\ No newline"):
                    continue
                else:
                    raise ValueError("Unsupported patch syntax")
        if not changes or any(not hunks for hunks in changes.values()):
            raise ValueError("Patch must be a unified diff")
        return changes

    def _apply(self, original: str, hunks: list[list[str]]) -> tuple[str, int]:
        source, output, cursor, changed = original.splitlines(keepends=True), [], 0, 0
        for hunk in hunks:
            old = [line[1:] + "\n" for line in hunk if line[0] in " -"]
            old = [line for line in old if line != "\n" or True]
            start = self._find(source, old, cursor)
            if start < 0:
                raise ValueError("Patch context does not match target")
            output.extend(source[cursor:start])
            for line in hunk:
                if line[0] in " +":
                    output.append(line[1:] + "\n")
                if line[0] in "+-":
                    changed += 1
            cursor = start + len(old)
        output.extend(source[cursor:])
        return "".join(output), changed

    @staticmethod
    def _find(source: list[str], old: list[str], start: int) -> int:
        if not old:
            return start
        for index in range(start, len(source) - len(old) + 1):
            if source[index : index + len(old)] == old:
                return index
        return -1
