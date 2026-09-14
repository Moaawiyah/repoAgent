"""Investigation domain model behavior."""

import pytest
from pydantic import ValidationError

from repoagent.domain.investigation import (
    EvidenceItem,
    InvestigationReport,
    Issue,
    RootCauseHypothesis,
    TerminationReason,
)
from repoagent.retrieval.models import GraphHop


def test_issue_requires_only_description():
    issue = Issue(description="Users cannot log in.")
    assert issue.title is None
    with pytest.raises(ValidationError):
        Issue(description="   ")


def evidence(evidence_id="e1", confidence=0.5, relevance=None):
    return EvidenceItem(
        evidence_id=evidence_id,
        query="q",
        retrieval_source="hybrid_graph",
        file_path="a.py",
        symbol_name="func",
        qualified_name="a.func",
        start_line=1,
        end_line=2,
        snippet="x = 1",
        rank=1,
        confidence=confidence,
        relevance=relevance,
        graph_path=[
            GraphHop(source_symbol="a.other", relation="calls", target_symbol="a.func")
        ],
    )


def test_evidence_confidence_is_bounded():
    with pytest.raises(ValidationError):
        evidence(confidence=1.5)
    item = evidence(confidence=0.0)
    assert item.confidence == 0.0
    assert item.graph_path[0].relation == "calls"


def test_report_primary_hypothesis_and_serialization():
    strong = RootCauseHypothesis(statement="lookup is case-sensitive", confidence=0.8)
    weak = RootCauseHypothesis(statement="missing normalization", confidence=0.5)
    report = InvestigationReport(
        task_id="t1",
        repository="/repo",
        issue=Issue(description="login fails"),
        issue_summary="login fails",
        evidence=[evidence()],
        hypotheses=[weak, strong],
        primary_hypothesis_id=strong.hypothesis_id,
        confidence=0.8,
        relevant_files=["a.py"],
        relevant_symbols=["a.func"],
        termination_reason=TerminationReason.CONFIDENT_ROOT_CAUSE,
    )
    assert report.primary_hypothesis is strong
    assert report.primary_hypothesis.statement.startswith("lookup")
    data = report.model_dump(mode="json")
    assert InvestigationReport.model_validate(data) == report


def test_report_without_hypotheses_defaults_to_insufficient():
    report = InvestigationReport(
        task_id="t2",
        repository="/repo",
        issue=Issue(description="x"),
        issue_summary="x",
    )
    assert report.primary_hypothesis is None
    assert report.termination_reason is TerminationReason.INSUFFICIENT_EVIDENCE
