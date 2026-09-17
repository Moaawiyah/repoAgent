"""ResourceHandlingDetector and SubprocessRiskDetector."""

from repoagent.audit.detectors.resources import ResourceHandlingDetector
from repoagent.audit.detectors.subprocess_risk import SubprocessRiskDetector
from tests.support.audit import build_context


def test_flags_unclosed_open_call():
    found = ResourceHandlingDetector().detect(build_context())
    assert any(c.symbol == "risky.read_all" for c in found)


def test_does_not_flag_open_used_as_context_manager():
    found = ResourceHandlingDetector().detect(build_context())
    assert not any(c.file == "clean.py" for c in found)


def test_flags_subprocess_run_with_shell_true():
    found = SubprocessRiskDetector().detect(build_context())
    assert any(c.symbol == "risky.run_command" for c in found)


def test_does_not_flag_subprocess_run_without_shell():
    found = SubprocessRiskDetector().detect(build_context())
    assert not any(c.file == "clean.py" for c in found)
