"""Deterministic pytest and Ruff output parsing; no LLM involvement."""

import re

from repoagent.domain.sandbox import CommandResult
from repoagent.domain.validation import (
    LintSummary,
    LintViolation,
    TestFailure,
    TestSummary,
)

_COUNT = re.compile(r"(\d+) (passed|failed|skipped|errors?|xfailed|xpassed)\b")
_SUMMARY = re.compile(
    r"(\d+ (passed|failed|skipped|errors?)|no tests ran).* in [\d.]+s"
)
_OUTCOME = re.compile(r"^(FAILED|ERROR) (\S+)(?: - (.*))?$")
_RUFF = re.compile(r"^(.+?):(\d+):(\d+): ([A-Z]{1,4}\d{1,4}) (.*)$")
_RUFF_TOTAL = re.compile(r"^Found (\d+) errors?")
MAX_FAILURES, MAX_VIOLATIONS = 50, 100


def parse_pytest(result: CommandResult) -> TestSummary:
    """Parse the ``-q -rfE`` summary; unparsed output keeps ``parsed=False``."""
    lines = result.stdout.splitlines()
    summary = next((line for line in reversed(lines) if _SUMMARY.search(line)), None)
    counts = {"passed": 0, "failed": 0, "skipped": 0, "errors": 0}
    if summary:
        for number, label in _COUNT.findall(summary):
            key = "errors" if label.startswith("error") else label
            if key in counts:
                counts[key] += int(number)
    failures = []
    for line in lines:
        match = _OUTCOME.match(line.strip())
        if match and len(failures) < MAX_FAILURES:
            failures.append(
                TestFailure(
                    test_id=match.group(2)[:500],
                    message=(match.group(3) or "")[:300],
                    kind="failed" if match.group(1) == "FAILED" else "error",
                )
            )
    return TestSummary(
        exit_code=result.exit_code,
        parsed=summary is not None,
        failures=failures,
        **counts,
    )


def parse_ruff(result: CommandResult) -> LintSummary:
    """Parse ``--output-format=concise`` diagnostics."""
    violations, total = [], None
    for line in result.stdout.splitlines():
        match = _RUFF.match(line.strip())
        if match and len(violations) < MAX_VIOLATIONS:
            path, row, _, code, message = match.groups()
            violations.append(
                LintViolation(
                    path=path.removeprefix("./")[:500],
                    line=int(row),
                    code=code,
                    message=message[:300],
                )
            )
        found = _RUFF_TOTAL.match(line.strip())
        if found:
            total = int(found.group(1))
    parsed = result.exit_code == 0 or bool(violations)
    return LintSummary(
        exit_code=result.exit_code,
        parsed=parsed,
        violations=violations,
        total=total if total is not None else len(violations),
    )


def is_collection_error(summary: TestSummary) -> bool:
    """Import/syntax problems prevent tests from running at all."""
    markers = ("ImportError", "ModuleNotFoundError", "SyntaxError", "IndentationError")
    return summary.exit_code == 2 or any(
        failure.kind == "error" and any(m in failure.message for m in markers)
        for failure in summary.failures
    )
