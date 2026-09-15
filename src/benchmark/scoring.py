"""Localization scoring from real agent reports against evaluator labels."""

from repoagent.benchmark.models import BenchmarkTask
from repoagent.benchmark.results import Localization, PatchMetrics
from repoagent.domain.investigation import InvestigationReport
from repoagent.domain.repair import PatchProposal


def _recall(found: list[str], expected: list[str]) -> float:
    return len(set(found) & set(expected)) / len(set(expected)) if expected else 0.0


def localization(
    task: BenchmarkTask, report: InvestigationReport | None
) -> Localization:
    """Hits use the primary hypothesis only; recall uses all relevant evidence."""
    if report is None:
        return Localization()
    primary = report.primary_hypothesis
    cited = [
        e
        for e in report.evidence
        if primary and e.evidence_id in primary.supporting_evidence
    ]
    files = sorted({e.file_path for e in cited})
    symbols = sorted(
        {
            *(e.qualified_name for e in cited),
            *(primary.affected_symbols if primary else []),
        }
    )
    return Localization(
        measured=True,
        file_hit=bool(set(files) & set(task.expected_files)),
        symbol_hit=bool(set(symbols) & set(task.expected_symbols)),
        file_recall=_recall(report.relevant_files, task.expected_files),
        symbol_recall=_recall(report.relevant_symbols, task.expected_symbols),
        predicted_files=files,
        predicted_symbols=symbols,
    )


def patch_metrics(
    task: BenchmarkTask, proposal: PatchProposal | None, stats: tuple[int, int, int]
) -> PatchMetrics:
    files, added, removed = stats
    touched = set(proposal.plan.affected_files) if proposal else set()
    return PatchMetrics(
        files_changed=files,
        lines_added=added,
        lines_removed=removed,
        touches_expected_file=bool(touched & set(task.expected_files)),
    )
