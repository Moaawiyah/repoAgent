"""Fake sandbox runner and pytest/Ruff output builders for M7 tests."""

from contextlib import contextmanager

from repoagent.domain.errors import SandboxError
from repoagent.domain.sandbox import (
    CommandKind,
    CommandResult,
    SandboxExecution,
    SandboxOutcome,
)


def pytest_result(passed=1, failed=(), errors=(), exit_code=None, **extra):
    lines = [f"FAILED {test} - AssertionError: boom" for test in failed]
    lines += [
        f"ERROR {test} - ModuleNotFoundError: No module named x" for test in errors
    ]
    counts = [f"{len(failed)} failed"] if failed else []
    counts += [f"{passed} passed"] + ([f"{len(errors)} errors"] if errors else [])
    lines.append(", ".join(counts) + " in 0.12s")
    code = exit_code if exit_code is not None else (1 if failed or errors else 0)
    return CommandResult(
        kind=CommandKind.PYTEST,
        argv=["python", "-m", "pytest"],
        exit_code=code,
        stdout="\n".join(lines),
        duration_seconds=0.5,
        **extra,
    )


def ruff_result(violations=()):
    lines = [
        f"app/x.py:{i + 1}:1: {code} {msg}" for i, (code, msg) in enumerate(violations)
    ]
    return CommandResult(
        kind=CommandKind.RUFF_CHECK,
        argv=["python", "-m", "ruff"],
        exit_code=1 if violations else 0,
        stdout="\n".join(lines),
    )


def execution(*commands, outcome=SandboxOutcome.COMPLETED, errors=(), unchanged=True):
    return SandboxExecution(
        outcome=outcome,
        commands=list(commands),
        errors=list(errors),
        duration_seconds=1.0,
        cleaned_up=True,
        repository_unchanged=unchanged,
    )


class FakeSandboxRunner:
    """Scripted executions: first run is the baseline, then one per attempt."""

    def __init__(self, baseline=None, attempts=(), fail_open=None):
        self.script = [baseline or execution(pytest_result()), *attempts]
        self.fail_open = fail_open
        self.runs, self.opened, self.closed = [], 0, 0
        self.overlays = []
        self.plan = self.limits = None

    @contextmanager
    def session(self, repository, plan, limits):
        if self.fail_open:
            raise SandboxError(self.fail_open)
        self.opened, self.plan, self.limits = self.opened + 1, plan, limits
        try:
            yield self
        finally:
            self.closed += 1

    def run(self, commands, unified_diff, overlay=None):
        self.runs.append((list(commands), unified_diff))
        self.overlays.append(overlay)
        if not self.script:
            raise AssertionError("Fake sandbox ran out of scripted executions")
        return self.script.pop(0)
