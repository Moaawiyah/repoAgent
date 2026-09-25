"""Human-readable presentation for repository audit reports."""

from repoagent.cli.execution_render import render_validated_repair
from repoagent.cli.repair_render import render_repair
from repoagent.domain.audit import CandidateIssue, VerificationStatus
from repoagent.domain.audit_report import AuditReport

_SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def _finding(candidate: CandidateIssue) -> str:
    reasoning = candidate.verification.reasoning if candidate.verification else ""
    return "\n".join(
        [
            f"[{candidate.severity.value.upper()}] {candidate.title}",
            f"{candidate.file}:{candidate.start_line}-{candidate.end_line}",
            f"Confidence: {candidate.confidence:.2f}",
            f"Evidence: {reasoning or candidate.description}",
        ]
    )


def render_audit(report: AuditReport) -> str:
    verified = sorted(
        report.by_status(VerificationStatus.VERIFIED),
        key=lambda c: (_SEVERITY_ORDER.get(c.severity.value, 3), -c.confidence),
    )
    lines = [
        "Repository Audit",
        "",
        "Scanned:",
        f"  {report.files_scanned} files",
        f"  {report.symbols_scanned} symbols",
        "",
        f"Candidates: {report.metrics.candidates_generated}",
        f"Verified:    {report.metrics.verified}",
        f"Uncertain:   {report.metrics.uncertain}",
        f"Rejected:    {report.metrics.rejected}",
    ]
    for candidate in verified:
        lines.extend(["", _finding(candidate)])
    if report.repair is not None:
        lines.extend(["", "Repair Attempt:", render_repair(report.repair)])
    if report.validated_repair is not None:
        lines.extend(
            [
                "",
                f"Validated Repair (finding {report.repair_candidate_id}):",
                render_validated_repair(report.validated_repair),
            ]
        )
    elif report.metrics.repair_status == "no_verified_candidate":
        lines.extend(["", "Repair: no verified finding to repair"])
    if report.error:
        lines.extend(["", f"Error: {report.error}"])
    return "\n".join(lines)
