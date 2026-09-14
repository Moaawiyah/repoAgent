"""Turn raw sandbox executions into typed, compared validation results.

Pass rule: the sandbox completed, the original repository is unchanged, every
required pytest run exits 0, and Ruff introduces no violation absent from the
baseline (pre-existing lint debt in a target repository is not a regression).
"""

import hashlib
import re

from repoagent.domain.sandbox import (
    CommandKind,
    SandboxExecution,
    SandboxOutcome,
    ValidationPlan,
)
from repoagent.domain.validation import (
    LintSummary,
    TestSummary,
    ValidationComparison,
    ValidationPhase,
    ValidationResult,
)
from repoagent.validation.parsers import parse_pytest, parse_ruff

USABLE_BASELINE_EXITS = {0, 1, 2}
_VOLATILE = re.compile(r"0x[0-9a-f]+|\d+(\.\d+)?")


def _parse(
    execution: SandboxExecution,
) -> tuple[TestSummary | None, LintSummary | None]:
    tests, lint = (
        execution.result(CommandKind.PYTEST),
        execution.result(CommandKind.RUFF_CHECK),
    )
    return (parse_pytest(tests) if tests else None, parse_ruff(lint) if lint else None)


def baseline_usable(result: ValidationResult, plan: ValidationPlan) -> bool:
    """The baseline must run to completion so regressions can be identified."""
    if result.execution.outcome != SandboxOutcome.COMPLETED:
        return False
    if plan.has(CommandKind.PYTEST):
        tests = result.tests
        return bool(tests and tests.exit_code in USABLE_BASELINE_EXITS and tests.parsed)
    return True


class ValidationEvaluator:
    """Deterministic comparison; never asks a model whether tests passed."""

    def baseline(self, execution: SandboxExecution) -> ValidationResult:
        tests, lint = _parse(execution)
        passed = execution.outcome == SandboxOutcome.COMPLETED and all(
            item.exit_code == 0 for item in execution.commands
        )
        return ValidationResult(
            phase=ValidationPhase.BASELINE,
            execution=execution,
            tests=tests,
            lint=lint,
            passed=passed,
            summary=self._summary(execution, tests, None),
        )

    def patched(
        self, execution: SandboxExecution, baseline: ValidationResult | None
    ) -> ValidationResult:
        tests, lint = _parse(execution)
        comparison = self._compare(tests, lint, baseline)
        lint_ok = (
            lint is None
            or lint.exit_code == 0
            or (lint.exit_code == 1 and not comparison.new_lint)
        )
        passed = (
            execution.outcome == SandboxOutcome.COMPLETED
            and execution.repository_unchanged
            and (tests is None or tests.exit_code == 0)
            and lint_ok
        )
        return ValidationResult(
            phase=ValidationPhase.PATCHED,
            execution=execution,
            tests=tests,
            lint=lint,
            passed=passed,
            comparison=comparison,
            summary=self._summary(execution, tests, comparison),
            signature=self._signature(execution, tests, comparison),
        )

    @staticmethod
    def _compare(
        tests: TestSummary | None,
        lint: LintSummary | None,
        baseline: ValidationResult | None,
    ) -> ValidationComparison:
        before = baseline.tests.failing_ids if baseline and baseline.tests else set()
        after = tests.failing_ids if tests else set()
        old_lint = (
            {v.signature for v in baseline.lint.violations}
            if baseline and baseline.lint
            else set()
        )
        new_lint = [v.signature for v in lint.violations] if lint else []
        return ValidationComparison(
            new_failures=sorted(after - before),
            fixed_failures=sorted(before - after),
            persisting_failures=sorted(after & before),
            new_lint=sorted({item for item in new_lint if item not in old_lint}),
        )

    @staticmethod
    def _summary(
        execution: SandboxExecution,
        tests: TestSummary | None,
        comparison: ValidationComparison | None,
    ) -> str:
        parts = [execution.outcome.value]
        if tests:
            parts.append(
                f"tests passed={tests.passed} failed={tests.failed} "
                f"errors={tests.errors} skipped={tests.skipped} exit={tests.exit_code}"
            )
        if comparison and comparison.new_failures:
            parts.append("new failures: " + ", ".join(comparison.new_failures[:5]))
        if comparison and comparison.new_lint:
            parts.append(f"new lint violations: {len(comparison.new_lint)}")
        parts.extend(execution.errors[:2])
        return "; ".join(parts)[:1000]

    @staticmethod
    def _signature(
        execution: SandboxExecution,
        tests: TestSummary | None,
        comparison: ValidationComparison,
    ) -> str:
        failures = sorted(
            f"{item.test_id}:{_VOLATILE.sub('#', item.message)}"
            for item in (tests.failures if tests else [])
        )
        material = "|".join([execution.outcome, *failures, *comparison.new_lint])
        return hashlib.sha256(material.encode()).hexdigest()[:16]
