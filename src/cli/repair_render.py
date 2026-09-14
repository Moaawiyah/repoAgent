"""Human-readable presentation for unapplied M6 repair reports."""

from repoagent.domain.repair import RepairReport


def render_repair(report: RepairReport) -> str:
    root = report.investigation.primary_hypothesis
    lines = [
        "RepoAgent Static Repair",
        "",
        "Root Cause:",
        root.statement if root else "none",
    ]
    if report.proposal:
        lines.extend(["", "Patch Summary:", report.proposal.plan.summary])
    if report.validation:
        lines.extend(
            [
                "",
                (
                    "Static Validation: "
                    + ("passed" if report.validation.valid else "failed")
                ),
            ]
        )
        lines.extend(f"- {error}" for error in report.validation.errors)
    if report.reviews:
        review = report.reviews[-1]
        lines.extend(
            ["", f"Reviewer Decision: {review.decision.value}", review.rationale]
        )
        if review.recommended_tests:
            lines.extend(
                [
                    "",
                    "Recommended Runtime Tests:",
                    *[f"- {item}" for item in review.recommended_tests],
                ]
            )
    lines.extend(
        [
            "",
            f"Final Status: {report.status.value}",
            "Patch has not been applied or executed.",
        ]
    )
    return "\n".join(lines)
