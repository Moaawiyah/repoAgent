"""Evaluator-side labels derived deterministically from gold patches."""

import re

from repoagent.analysis.results import RepositoryAnalysis

_FILE = re.compile(r"^diff --git a/(\S+) b/(\S+)$")
_PLUS = re.compile(r"^\+\+\+ b/(\S+)")
_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@")


def changed_ranges(patch: str) -> dict[str, list[tuple[int, int]]]:
    """Original-file line ranges touched by each file of a unified diff."""
    ranges: dict[str, list[tuple[int, int]]] = {}
    current = None
    for line in patch.splitlines():
        header = _FILE.match(line) or _PLUS.match(line)
        if header:
            current = header.groups()[-1]
            ranges.setdefault(current, [])
            continue
        hunk = _HUNK.match(line)
        if hunk and current is not None:
            start, length = int(hunk.group(1)), int(hunk.group(2) or 1)
            ranges[current].append((start, start + max(length, 1) - 1))
    return ranges


def expected_files(patch: str, *, include_tests: bool = False) -> list[str]:
    files = sorted(path for path in changed_ranges(patch) if path.endswith(".py"))
    return [f for f in files if include_tests or not _is_test_path(f)]


def expected_symbols(patch: str, analysis: RepositoryAnalysis) -> list[str]:
    """Innermost function/method whose line span overlaps a changed hunk."""
    ranges = changed_ranges(patch)
    found: set[str] = set()
    for file in analysis.files:
        spans = ranges.get(file.path)
        if not spans or _is_test_path(file.path):
            continue
        callables = [s for s in file.symbols if s.symbol_type in ("function", "method")]
        for start, end in spans:
            overlapping = [
                s for s in callables if s.start_line <= end and start <= s.end_line
            ]
            if overlapping:
                inner = min(overlapping, key=lambda s: s.end_line - s.start_line)
                found.add(inner.qualified_name)
    return sorted(found)


def _is_test_path(path: str) -> bool:
    parts = path.split("/")
    name = parts[-1]
    return any(p in ("tests", "test", "testing") for p in parts[:-1]) or (
        name.startswith("test_") or name.endswith("_test.py") or name == "conftest.py"
    )
