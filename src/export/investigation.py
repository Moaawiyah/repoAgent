"""Obsidian note rendering for investigation reports.

The vault remains a visualization layer: notes link only to symbols that
exist as graph notes, and untrusted issue/evidence text stays inside
fenced blocks.
"""

import re
from pathlib import Path

from repoagent.domain.errors import ExportError
from repoagent.domain.investigation import InvestigationReport
from repoagent.export.notes import safe_name


def _fence(text: str) -> str:
    longest = max((len(run) for run in re.findall(r"`+", text)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}\n{text}\n{fence}"


def render_investigation_note(report: InvestigationReport) -> str:
    """Render an investigation as one Obsidian note."""
    primary = report.primary_hypothesis
    lines = [
        f"# Investigation {report.task_id} — {_short(report.issue.description)}",
        "",
        "## Issue",
        "",
        _fence(report.issue.description),
        "",
        "## Primary Hypothesis",
        "",
    ]
    if primary is not None:
        lines.extend(
            [
                f"Confidence: {primary.confidence:.2f}",
                "",
                _fence(primary.statement),
                "",
                "Affected symbols:",
                *[f"- [[{safe_name(symbol)}]]" for symbol in primary.affected_symbols],
            ]
        )
    else:
        lines.append("_No hypothesis reached._")
    lines.extend(["", "## Evidence", ""])
    evidence_links = [
        f"- [[{safe_name(item.qualified_name)}]] "
        f"`{item.file_path}:{item.start_line}-{item.end_line}`"
        for item in report.evidence
    ]
    lines.extend(evidence_links or ["_No evidence collected._"])
    lines.extend(["", "## Investigation Path", ""])
    for path in report.graph_paths:
        nodes = [path[0].source_symbol, *(hop.target_symbol for hop in path)]
        chain = " → ".join(f"[[{safe_name(node)}]]" for node in nodes)
        lines.append(f"- {chain}")
    lines.extend(
        [
            "",
            "## Confidence",
            "",
            f"{report.confidence:.2f}",
            "",
            f"**Termination:** {report.termination_reason.value}  ",
            f"**Iterations:** {report.iterations}",
            "",
        ]
    )
    return "\n".join(lines)


def export_investigation_note(
    report: InvestigationReport, vault: Path, *, overwrite: bool = False
) -> Path:
    """Write ``Investigations/<task>.md`` into a vault; never deletes."""
    vault = vault.expanduser().resolve()
    folder = vault / "Investigations"
    repository = Path(report.repository).expanduser().resolve()
    if vault.is_relative_to(repository):
        raise ExportError("Investigation exports must be outside the repository")
    if folder.is_symlink():
        raise ExportError("Investigation folder must not be a symlink")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", report.task_id):
        raise ExportError("Invalid investigation identifier")
    target = folder / f"investigation-{report.task_id}.md"
    if target.is_symlink():
        raise ExportError("Investigation note must not be a symlink")
    if not target.resolve().is_relative_to(vault):
        raise ExportError("Investigation note escapes the vault directory")
    if target.exists() and not overwrite:
        raise ExportError(
            "Investigation note already exists; pass overwrite to replace it"
        )
    folder.mkdir(parents=True, exist_ok=True)
    with target.open("w" if overwrite else "x", encoding="utf-8") as output:
        output.write(render_investigation_note(report))
    return target


def _short(text: str, limit: int = 60) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"
