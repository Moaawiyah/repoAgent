"""Obsidian investigation note export behavior."""

import pytest

from repoagent.domain.errors import ExportError
from repoagent.domain.investigation import (
    EvidenceItem,
    InvestigationReport,
    Issue,
    RootCauseHypothesis,
)
from repoagent.export.investigation import (
    export_investigation_note,
    render_investigation_note,
)
from repoagent.retrieval.models import GraphHop


def report(task_id="task001"):
    hypothesis = RootCauseHypothesis(
        statement="Email lookup compares the raw value case-sensitively.",
        confidence=0.84,
        affected_symbols=["app.users.repository.UserRepository.find_by_email"],
    )
    return InvestigationReport(
        task_id=task_id,
        repository="/repo",
        issue=Issue(description="Uppercase emails cannot log in"),
        issue_summary="Uppercase emails cannot log in",
        evidence=[
            EvidenceItem(
                evidence_id="e1",
                query="email",
                retrieval_source="hybrid_graph",
                file_path="app/users/repository.py",
                symbol_name="find_by_email",
                qualified_name="app.users.repository.UserRepository.find_by_email",
                start_line=12,
                end_line=18,
                snippet="if user['email'] == email:",
                rank=1,
            )
        ],
        hypotheses=[hypothesis],
        primary_hypothesis_id=hypothesis.hypothesis_id,
        confidence=0.84,
        relevant_files=["app/users/repository.py"],
        graph_paths=[
            [
                GraphHop(
                    source_symbol="app.auth.service.AuthService.login",
                    relation="calls",
                    target_symbol=("app.users.repository.UserRepository.find_by_email"),
                )
            ]
        ],
    )


def test_note_renders_issue_hypothesis_and_path(tmp_path):
    note = render_investigation_note(report())
    assert "# Investigation task001" in note
    assert "## Issue" in note and "## Primary Hypothesis" in note
    assert (
        "## Evidence" in note
        and "[[app.users.repository.UserRepository.find_by_email]]" in note
    )
    assert "## Investigation Path" in note
    assert "0.84" in note


def test_export_writes_once_then_requires_overwrite(tmp_path):
    vault = tmp_path / "vault"
    path = export_investigation_note(report(), vault)
    assert path.is_file()
    assert path.parent.name == "Investigations"
    with pytest.raises(ExportError):
        export_investigation_note(report(), vault)
    again = export_investigation_note(report(), vault, overwrite=True)
    assert again == path


def test_note_renders_without_hypotheses(tmp_path):
    empty = report(task_id="task002").model_copy(
        update={
            "hypotheses": [],
            "primary_hypothesis_id": None,
            "confidence": 0.0,
            "graph_paths": [],
        }
    )
    note = render_investigation_note(empty)
    assert "No hypothesis reached" in note
    assert "No evidence collected." not in note
