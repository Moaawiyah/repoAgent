"""CandidateIssue stable identity and conversion into the existing Issue."""

from repoagent.domain.audit import (
    CandidateIssue,
    DetectionSource,
    IssueCategory,
    Severity,
    VerificationStatus,
    VerifierFinding,
    stable_candidate_id,
)


def _candidate(**overrides) -> CandidateIssue:
    defaults = dict(
        id=stable_candidate_id(IssueCategory.MUTABLE_DEFAULT, "a.py", 3, "x"),
        category=IssueCategory.MUTABLE_DEFAULT,
        title="Mutable default argument",
        description="Parameter defaults to a mutable literal.",
        confidence=0.9,
        severity=Severity.MEDIUM,
        file="a.py",
        symbol="a.f",
        start_line=3,
        end_line=5,
        detection_source=DetectionSource.AST_MUTABLE_DEFAULT,
    )
    defaults.update(overrides)
    return CandidateIssue(**defaults)


def test_stable_id_is_deterministic_and_input_sensitive():
    first = stable_candidate_id(IssueCategory.DEAD_CODE, "a.py", 10, "x")
    second = stable_candidate_id(IssueCategory.DEAD_CODE, "a.py", 10, "x")
    third = stable_candidate_id(IssueCategory.DEAD_CODE, "a.py", 11, "x")
    assert first == second
    assert first != third


def test_to_issue_includes_location_and_verifier_reasoning():
    verification = VerifierFinding(
        status=VerificationStatus.VERIFIED,
        reasoning="Confirmed by evidence in a.py.",
        confidence=0.8,
    )
    candidate = _candidate(
        status=VerificationStatus.VERIFIED, verification=verification
    )
    issue = candidate.to_issue()
    assert issue.title == candidate.title
    assert "a.py:3-5" in issue.description
    assert "Confirmed by evidence" in issue.description
    assert issue.observed_behavior == candidate.description


def test_to_issue_without_verification_omits_reasoning_gracefully():
    candidate = _candidate()
    issue = candidate.to_issue()
    assert issue.description.endswith("Verifier reasoning:")
