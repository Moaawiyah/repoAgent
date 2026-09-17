"""RuffDetector: sandbox-gated, ingests Ruff findings via existing parsing."""

from repoagent.audit.detectors.ruff_adapter import RuffDetector
from tests.support.audit import build_context
from tests.support.sandbox import FakeSandboxRunner, execution, ruff_result


def _configured_repo(tmp_path):
    (tmp_path / "ruff.toml").write_text("line-length = 88\n")
    (tmp_path / "mod.py").write_text("x = 1\n")
    return build_context(tmp_path)


def test_no_op_without_a_sandbox_runner():
    assert RuffDetector(None).detect(build_context()) == []


def test_no_op_when_repository_has_no_ruff_config():
    runner = FakeSandboxRunner(baseline=execution(ruff_result([("F401", "unused")])))
    found = RuffDetector(runner).detect(build_context())
    assert found == []
    assert runner.opened == 0


def test_ingests_violations_when_configured_and_sandboxed(tmp_path):
    runner = FakeSandboxRunner(
        baseline=execution(ruff_result([("F401", "'os' imported but unused")]))
    )
    context = _configured_repo(tmp_path)
    found = RuffDetector(runner).detect(context)
    assert len(found) == 1
    assert found[0].detection_source == "ruff"
    assert found[0].severity == "high"
    assert runner.opened == 1
