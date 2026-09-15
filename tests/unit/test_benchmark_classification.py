"""Failure categories, metric aggregation, and report rendering."""

from types import SimpleNamespace as NS

import pytest

from repoagent.benchmark.classification import classify_investigation, classify_repair
from repoagent.benchmark.metrics import summarize
from repoagent.benchmark.report import render_benchmark
from repoagent.benchmark.results import FailureCategory as F
from repoagent.benchmark.results import Localization, TaskResult, TokenUsage

GOLD = ["app/core.py"]


def investigation(reason="confident_root_cause", files=("app/core.py",)):
    evidence = [NS(file_path=f) for f in files]
    return NS(termination_reason=reason, evidence=evidence)


def attempt(new_failures=(), category=None, files=("app/core.py",)):
    comparison = NS(new_failures=list(new_failures))
    analysis = NS(category=category) if category else None
    return NS(
        validation=NS(comparison=comparison),
        failure_analysis=analysis,
        static_validation=NS(changed_files=list(files)),
    )


def report(status, attempts=(), rationale="ok", inv=None):
    return NS(
        status=status,
        attempts=list(attempts),
        reviews=[NS(rationale=rationale)],
        investigation=inv or investigation(),
    )


@pytest.mark.parametrize(
    "inv, located, expected",
    [
        (investigation(), Localization(file_hit=True), None),
        (investigation(files=("other.py",)), Localization(), F.LOCALIZATION_FAILURE),
        (investigation("max_iterations"), Localization(), F.INSUFFICIENT_EVIDENCE),
        (investigation(), Localization(), F.INCORRECT_ROOT_CAUSE),
        (investigation("provider_error"), Localization(), F.PROVIDER_ERROR),
    ],
)
def test_investigation_categories(inv, located, expected):
    assert classify_investigation(inv, located, GOLD) == expected


@pytest.mark.parametrize(
    "item, hidden, expected",
    [
        (report("validated", [attempt()]), None, None),
        (report("validated", [attempt()]), True, None),
        (report("validated", [attempt()]), False, F.TEST_FAILURE),
        (
            report("validated", [attempt(files=("x.py",))]),
            False,
            F.INCORRECT_ROOT_CAUSE,
        ),
        (report("timeout"), None, F.TIMEOUT),
        (report("patch_apply_failed"), None, F.PATCH_APPLY_FAILURE),
        (report("baseline_failed"), None, F.SANDBOX_FAILURE),
        (report("review_rejected"), None, F.REVIEW_REJECTION),
        (
            report("review_rejected", rationale="Static patch validation failed."),
            None,
            F.PATCH_GENERATION_FAILURE,
        ),
        (report("max_attempts", [attempt(["t::a"])]), None, F.REGRESSION),
        (report("max_attempts", [attempt()]), None, F.MAX_ATTEMPTS),
        (
            report("validation_failed", [attempt(category="wrong_root_cause")]),
            None,
            F.INCORRECT_ROOT_CAUSE,
        ),
        (report("validation_failed", [attempt()]), None, F.TEST_FAILURE),
        (report("insufficient_evidence"), None, F.INCORRECT_ROOT_CAUSE),
    ],
)
def test_repair_categories(item, hidden, expected):
    assert classify_repair(item, Localization(), GOLD, hidden) == expected


def result(**fields):
    base = {"run_id": "20260101T000000Z-abcdef", "benchmark": "b", "mode": "repair"}
    return TaskResult(**(base | fields))


def test_summary_and_report_use_only_measured_values():
    results = [
        result(task_id="a", experiment="full", status="validated", success=True,
               attempts=2, tokens=TokenUsage(llm_calls=10, input_tokens=100),
               localization=Localization(measured=True, file_hit=True)),
        result(task_id="b", experiment="full", status="timeout",
               failure_category=F.TIMEOUT, attempts=1),
        result(task_id="a", experiment="no_graph", status="validated", success=True),
    ]  # fmt: skip
    summary = summarize("20260101T000000Z-abcdef", "suite", results)
    full = summary.experiments[0]
    assert full.success_rate == 0.5 and full.avg_attempts == 1.5
    assert full.file_localization == 1.0 and full.localization_measured == 1
    assert full.timeouts == 1 and full.failures == {"timeout": 1}
    assert full.avg_llm_calls == 5.0
    assert summary.experiments[1].symbol_localization is None
    manifest = NS(
        run_id="r", suite="suite", repoagent_version="0.1.0",
        repoagent_commit=None, llm_provider="groq", llm_model="m",
    )  # fmt: skip
    text = render_benchmark(manifest, summary)
    assert "Validated repairs:        1" in text and "Failure timeout: 1" in text
    assert "Symbol localization:      0.0%" in text and "no_graph" in text
