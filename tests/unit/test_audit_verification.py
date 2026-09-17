"""verify_candidates(): empty input and malformed-output resilience."""

from repoagent.application.audit_verification import verify_candidates
from repoagent.domain.audit import (
    CandidateIssue,
    DetectionSource,
    IssueCategory,
    Severity,
    stable_candidate_id,
)
from tests.support.scripted import ScriptedLLMProvider


def _candidate() -> CandidateIssue:
    return CandidateIssue(
        id=stable_candidate_id(IssueCategory.TODO_MARKER, "a.py", 1, "x"),
        category=IssueCategory.TODO_MARKER,
        title="TODO marker",
        description="d",
        confidence=1.0,
        severity=Severity.LOW,
        file="a.py",
        start_line=1,
        end_line=1,
        detection_source=DetectionSource.AST_TODO,
    )


def test_empty_candidates_short_circuits():
    results, metrics = verify_candidates(ScriptedLLMProvider([]), [])
    assert results == []
    assert metrics.verification_llm_calls == 0


def test_malformed_output_is_reported_uncertain_not_dropped():
    provider = ScriptedLLMProvider(["not json"])
    results, metrics = verify_candidates(provider, [_candidate()])
    assert len(results) == 1
    assert results[0].status == "uncertain"
    assert results[0].verification.confidence == 0.0
    assert metrics.uncertain == 1
