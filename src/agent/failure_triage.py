"""Deterministic failure classification that avoids unnecessary LLM calls."""

from repoagent.domain.repair_execution import (
    FailureAnalysis,
    FailureCategory,
    NextAction,
    RepairAttempt,
)
from repoagent.domain.sandbox import SandboxOutcome
from repoagent.domain.validation import ValidationResult
from repoagent.validation.parsers import is_collection_error


def _path(test_id: str) -> str:
    return test_id.split("::", 1)[0][:300]


def triage(
    validation: ValidationResult,
    baseline: ValidationResult | None,
    attempts: list[RepairAttempt],
) -> FailureAnalysis | None:
    """Return an analysis when parsing alone explains the failure."""
    tests, comparison = validation.tests, validation.comparison
    if validation.execution.outcome == SandboxOutcome.TIMEOUT:
        return FailureAnalysis(
            category=FailureCategory.TIMEOUT,
            likely_reason="Validation exceeded the sandbox timeout after patching.",
            patch_caused_failure=baseline is not None,
            next_action=NextAction.STOP,
        )
    previous = attempts[-1] if attempts else None
    if (
        previous
        and previous.failure_analysis
        and previous.validation.signature == validation.signature
    ):
        prior = previous.failure_analysis
        return prior.model_copy(
            update={
                "likely_reason": (
                    "Identical failure persisted after revision. " + prior.likely_reason
                )[:800],
                "source": "deterministic",
            }
        )
    baseline_tests = baseline.tests if baseline else None
    if (
        tests
        and is_collection_error(tests)
        and not (baseline_tests and is_collection_error(baseline_tests))
    ):
        first = tests.failures[0] if tests.failures else None
        return FailureAnalysis(
            category=FailureCategory.COLLECTION_ERROR,
            likely_reason=(
                "Tests could not be collected after patching: "
                + (first.message if first and first.message else "import error")
            )[:800],
            affected_file=_path(first.test_id) if first else None,
            patch_caused_failure=True,
            next_action=NextAction.REVISE_PATCH,
        )
    tests_green = tests is None or tests.exit_code == 0
    if tests_green and comparison and comparison.new_lint:
        first = comparison.new_lint[0].split("|")
        return FailureAnalysis(
            category=FailureCategory.LINT,
            likely_reason=(
                f"Patch introduced {len(comparison.new_lint)} Ruff violation(s): "
                + "; ".join(item.replace("|", " ") for item in comparison.new_lint[:3])
            )[:800],
            affected_file=first[0][:300],
            patch_caused_failure=True,
            next_action=NextAction.REVISE_PATCH,
        )
    return None


def failure_summary(validation: ValidationResult) -> str:
    """Short, model-independent description preserved with each attempt."""
    tests = validation.tests
    lines = [validation.summary]
    if tests:
        lines.extend(
            f"{item.test_id}: {item.message}"[:200] for item in tests.failures[:5]
        )
    return "\n".join(lines)[:1000]
