"""render_audit(): repair-attempt and error-field presentation."""

from repoagent.cli.audit_render import render_audit
from repoagent.domain.audit_report import AuditMetrics, AuditReport
from repoagent.domain.investigation import InvestigationReport
from repoagent.domain.repair import RepairReport, RepairStatus


def test_render_includes_repair_attempt_block():
    investigation = InvestigationReport(
        task_id="t", repository="r", issue={"description": "d"}, issue_summary="s"
    )
    repair = RepairReport(investigation=investigation, status=RepairStatus.REJECTED)
    report = AuditReport(
        repository="r", metrics=AuditMetrics(candidates_generated=0), repair=repair
    )
    output = render_audit(report)
    assert "Repair Attempt:" in output
    assert "rejected" in output


def test_render_includes_error_field():
    report = AuditReport(repository="r", error="Repository could not be analyzed")
    output = render_audit(report)
    assert "Error: Repository could not be analyzed" in output
