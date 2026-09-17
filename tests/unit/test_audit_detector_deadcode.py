"""DeadCodeDetector and TodoMarkerDetector."""

from repoagent.audit.detectors.dead_code import DeadCodeDetector
from repoagent.audit.detectors.todo_markers import TodoMarkerDetector
from tests.support.audit import build_context


def test_flags_statement_after_unconditional_return():
    found = DeadCodeDetector().detect(build_context())
    assert any(c.symbol == "risky.run_once" for c in found)


def test_does_not_flag_reachable_code():
    found = DeadCodeDetector().detect(build_context())
    assert not any(c.file == "clean.py" for c in found)


def test_flags_todo_marker_as_inert_text_evidence():
    found = TodoMarkerDetector().detect(build_context())
    match = next(c for c in found if c.file == "risky.py")
    assert "ignore all previous instructions" in match.description
    assert match.confidence == 1.0


def test_does_not_flag_clean_module():
    found = TodoMarkerDetector().detect(build_context())
    assert not any(c.file == "clean.py" for c in found)
