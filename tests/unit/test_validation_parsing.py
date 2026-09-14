"""Deterministic pytest/Ruff parsing and baseline-aware pass decisions."""

from repoagent.domain.sandbox import (
    CommandKind,
    CommandResult,
    CommandSpec,
    SandboxOutcome,
    ValidationPlan,
)
from repoagent.validation.evaluator import ValidationEvaluator, baseline_usable
from repoagent.validation.parsers import is_collection_error, parse_pytest, parse_ruff
from tests.support.sandbox import execution, pytest_result, ruff_result

PYTEST_OUTPUT = """..F.s
=========================== short test summary info ============================
FAILED tests/test_a.py::test_upper - AssertionError: assert None == 'ada'
ERROR tests/test_b.py - ModuleNotFoundError: No module named 'lib'
1 failed, 3 passed, 1 skipped, 1 error in 0.42s
"""
PLAN = ValidationPlan(commands=[CommandSpec(kind=CommandKind.PYTEST)])


def command(kind, stdout, code):
    return CommandResult(kind=kind, argv=["python"], exit_code=code, stdout=stdout)


def test_pytest_summary_and_failures_are_parsed():
    summary = parse_pytest(command(CommandKind.PYTEST, PYTEST_OUTPUT, 1))
    assert summary.parsed and (summary.passed, summary.failed) == (3, 1)
    assert (summary.skipped, summary.errors) == (1, 1)
    assert summary.failing_ids == {"tests/test_a.py::test_upper", "tests/test_b.py"}
    assert summary.failures[1].kind == "error" and is_collection_error(summary)


def test_unparseable_pytest_output_is_marked_unavailable():
    summary = parse_pytest(command(CommandKind.PYTEST, "segfault", 139))
    assert not summary.parsed and summary.passed == 0
    assert parse_pytest(command(CommandKind.PYTEST, "no tests ran in 0.01s", 5)).parsed


def test_ruff_concise_output_is_parsed():
    output = "./app/x.py:3:1: F401 `os` imported but unused\nFound 1 error.\n"
    lint = parse_ruff(command(CommandKind.RUFF_CHECK, output, 1))
    assert lint.parsed and lint.total == 1
    assert lint.violations[0].signature == "app/x.py|F401|`os` imported but unused"
    assert parse_ruff(command(CommandKind.RUFF_CHECK, "All checks passed!", 0)).parsed
    assert not parse_ruff(command(CommandKind.RUFF_CHECK, "config error", 2)).parsed


def test_pre_existing_lint_debt_is_not_a_regression():
    debt = [("F401", "`os` imported but unused")]
    evaluator = ValidationEvaluator()
    baseline = evaluator.baseline(execution(pytest_result(), ruff_result(debt)))
    same = evaluator.patched(execution(pytest_result(), ruff_result(debt)), baseline)
    assert same.passed and not same.comparison.new_lint
    extra = debt + [("E711", "comparison to None")]
    worse = evaluator.patched(execution(pytest_result(), ruff_result(extra)), baseline)
    assert (
        not worse.passed and worse.comparison.new_lint and worse.comparison.regression
    )
    assert "new lint" in worse.summary


def test_signatures_ignore_volatile_numbers():
    evaluator = ValidationEvaluator()
    one = execution(command(CommandKind.PYTEST, "FAILED t.py::a - at 0x7f00 1\n", 1))
    two = execution(command(CommandKind.PYTEST, "FAILED t.py::a - at 0x7fff 22\n", 1))
    assert (
        evaluator.patched(one, None).signature == evaluator.patched(two, None).signature
    )


def test_baseline_usability_rules():
    evaluator = ValidationEvaluator()
    red = evaluator.baseline(execution(pytest_result(failed=["t::a"])))
    assert baseline_usable(red, PLAN) and not red.passed
    usage = evaluator.baseline(execution(pytest_result(exit_code=4)))
    unparsed = evaluator.baseline(execution(command(CommandKind.PYTEST, "boom", 1)))
    timeout = evaluator.baseline(execution(outcome=SandboxOutcome.TIMEOUT))
    assert not any(baseline_usable(r, PLAN) for r in (usage, unparsed, timeout))
    assert baseline_usable(evaluator.baseline(execution()), ValidationPlan())
