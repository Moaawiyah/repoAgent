"""Readable CLI presentation of investigation reports."""

from repoagent.domain.investigation import InvestigationReport


def _confidence_label(confidence: float) -> str:
    if confidence >= 0.75:
        return "High"
    if confidence >= 0.5:
        return "Medium"
    return "Low"


def render_investigation(report: InvestigationReport) -> str:
    """Render a human-readable investigation report."""
    issue = report.issue.description
    lines = [
        "RepoAgent Investigation",
        "",
        f"Issue: {issue}",
        "",
    ]
    primary = report.primary_hypothesis
    if primary is not None:
        lines.extend(
            [
                "Primary Root Cause:",
                primary.statement,
                "",
                f"Confidence: {_confidence_label(report.confidence)} "
                f"({report.confidence:.2f})",
            ]
        )
        if primary.affected_symbols:
            lines.append("Affected symbols: " + ", ".join(primary.affected_symbols))
    else:
        lines.append("Primary Root Cause: none identified")
    if report.evidence:
        lines.extend(["", "Evidence:"])
        for position, item in enumerate(report.evidence, start=1):
            lines.append(
                f"{position}. {item.qualified_name} "
                f"{item.file_path}:{item.start_line}-{item.end_line} "
                f"[{item.retrieval_source}]"
            )
            if item.graph_path:
                chain = " -> ".join(hop.target_symbol for hop in item.graph_path)
                lines.append(f"   via {item.graph_path[0].source_symbol} -> {chain}")
    alternatives = [
        hypothesis
        for hypothesis in report.hypotheses
        if hypothesis.hypothesis_id != report.primary_hypothesis_id
    ]
    for hypothesis in alternatives[:2]:
        lines.extend(
            [
                "",
                f"Alternative Hypothesis (confidence {hypothesis.confidence:.2f}):",
                hypothesis.statement,
            ]
        )
    if report.open_questions:
        lines.extend(["", "Open Questions:"])
        lines.extend(f"- {question}" for question in report.open_questions[:4])
    lines.extend(
        [
            "",
            f"Termination: {report.termination_reason.value}",
            f"Iterations: {report.iterations}",
            f"Queries: {len(report.queries)}",
        ]
    )
    return "\n".join(lines)
