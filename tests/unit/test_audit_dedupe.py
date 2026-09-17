"""deduplicate(): overlapping same-file/category findings collapse."""

from repoagent.audit.dedupe import deduplicate
from repoagent.domain.audit import (
    CandidateIssue,
    DetectionSource,
    IssueCategory,
    Severity,
    stable_candidate_id,
)


def _candidate(start, end, confidence, detail="x") -> CandidateIssue:
    return CandidateIssue(
        id=stable_candidate_id(IssueCategory.DEAD_CODE, "a.py", start, detail),
        category=IssueCategory.DEAD_CODE,
        title="Unreachable code",
        description="d",
        confidence=confidence,
        severity=Severity.LOW,
        file="a.py",
        start_line=start,
        end_line=end,
        detection_source=DetectionSource.AST_DEAD_CODE,
    )


def test_overlapping_same_category_candidates_collapse_to_higher_confidence():
    low = _candidate(10, 12, 0.5)
    high = _candidate(11, 13, 0.9)
    kept, removed = deduplicate([low, high])
    assert removed == 1
    assert kept == [high]


def test_non_overlapping_candidates_are_both_kept():
    first = _candidate(1, 2, 0.6)
    second = _candidate(20, 21, 0.6)
    kept, removed = deduplicate([first, second])
    assert removed == 0
    assert {c.start_line for c in kept} == {1, 20}


def test_different_category_same_range_is_not_deduplicated():
    dead = _candidate(5, 6, 0.7)
    other = dead.model_copy(update={"category": IssueCategory.TODO_MARKER})
    kept, removed = deduplicate([dead, other])
    assert removed == 0
    assert len(kept) == 2


def test_empty_input_returns_empty():
    assert deduplicate([]) == ([], 0)
