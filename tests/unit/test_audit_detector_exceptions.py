"""BroadExceptionDetector: positive fixture hit plus clean-module negative."""

from repoagent.audit.detectors.exceptions import BroadExceptionDetector
from tests.support.audit import build_context


def test_flags_bare_except_that_only_passes():
    context = build_context()
    found = BroadExceptionDetector().detect(context)
    assert any(c.file == "risky.py" and c.symbol == "risky.normalize" for c in found)


def test_does_not_flag_reraising_handler():
    context = build_context()
    found = BroadExceptionDetector().detect(context)
    assert not any(c.file == "clean.py" for c in found)
