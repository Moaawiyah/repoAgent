"""Investigation benchmark metrics computed from real reports."""

from collections.abc import Callable

from pydantic import Field

from repoagent.analysis.models import AnalysisModel
from repoagent.domain.investigation import InvestigationReport


class InvestigationTask(AnalysisModel):
    """One labeled investigation benchmark task."""

    name: str
    repository: str
    issue: str
    expected_files: list[str] = Field(default_factory=list)
    expected_symbols: list[str] = Field(default_factory=list)
    expected_root_cause_file: str | None = None
    expected_root_cause_symbol: str | None = None


class TaskOutcome(AnalysisModel):
    """Objective metrics for one task; no language comparison."""

    task: str
    file_recall: float
    symbol_recall: float
    root_cause_localized: bool
    iterations: int
    retrieval_rounds: int
    retrieval_calls: int
    termination_reason: str


class BenchmarkOutcome(AnalysisModel):
    """Aggregated investigation benchmark results."""

    tasks: int
    avg_file_recall: float
    avg_symbol_recall: float
    root_cause_accuracy: float
    avg_iterations: float
    avg_retrieval_rounds: float
    avg_retrieval_calls: float
    outcomes: list[TaskOutcome] = Field(default_factory=list)


def _recall(found: list[str], expected: list[str]) -> float:
    if not expected:
        return 0.0
    hits = len(set(found) & set(expected))
    return hits / len(set(expected))


def evaluate_task(task: InvestigationTask, report: InvestigationReport) -> TaskOutcome:
    """Measure localization against the labeled expectations."""
    primary = report.primary_hypothesis
    localized = False
    if primary is not None and task.expected_root_cause_symbol:
        localized = any(
            item.evidence_id in primary.supporting_evidence
            and item.qualified_name == task.expected_root_cause_symbol
            and item.qualified_name in primary.affected_symbols
            and (
                not task.expected_root_cause_file
                or item.file_path == task.expected_root_cause_file
            )
            for item in report.evidence
        )
    rounds = sum(1 for entry in report.trace if entry.action == "retrieve")
    return TaskOutcome(
        task=task.name,
        file_recall=_recall(report.relevant_files, task.expected_files),
        symbol_recall=_recall(report.relevant_symbols, task.expected_symbols),
        root_cause_localized=localized,
        iterations=report.iterations,
        retrieval_rounds=rounds,
        retrieval_calls=report.tool_calls,
        termination_reason=report.termination_reason.value,
    )


def run_investigation_benchmark(
    investigate: Callable[[InvestigationTask], InvestigationReport],
    tasks: list[InvestigationTask],
) -> BenchmarkOutcome:
    """Run every task through the provided investigator callable."""
    outcomes = [evaluate_task(task, investigate(task)) for task in tasks]
    count = len(outcomes) or 1
    return BenchmarkOutcome(
        tasks=len(outcomes),
        avg_file_recall=sum(o.file_recall for o in outcomes) / count,
        avg_symbol_recall=sum(o.symbol_recall for o in outcomes) / count,
        root_cause_accuracy=sum(1 for o in outcomes if o.root_cause_localized) / count,
        avg_iterations=sum(o.iterations for o in outcomes) / count,
        avg_retrieval_rounds=sum(o.retrieval_rounds for o in outcomes) / count,
        avg_retrieval_calls=sum(o.retrieval_calls for o in outcomes) / count,
        outcomes=outcomes,
    )
