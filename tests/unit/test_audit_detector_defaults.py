"""MutableDefaultDetector and NoneDefaultAccessDetector."""

from repoagent.audit.detectors.defaults import MutableDefaultDetector
from repoagent.audit.detectors.none_handling import NoneDefaultAccessDetector
from tests.support.audit import build_context


def test_flags_mutable_default_list_argument():
    found = MutableDefaultDetector().detect(build_context())
    assert any(c.symbol == "risky.append_item" for c in found)


def test_does_not_flag_none_default_guarded_by_if():
    found = MutableDefaultDetector().detect(build_context())
    assert not any(c.file == "clean.py" for c in found)


def test_flags_unguarded_access_on_none_default():
    found = NoneDefaultAccessDetector().detect(build_context())
    assert any(c.symbol == "risky.greet" for c in found)


def test_does_not_flag_guarded_none_default():
    found = NoneDefaultAccessDetector().detect(build_context())
    assert not any(c.file == "clean.py" for c in found)
