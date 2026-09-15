"""Human-readable benchmark summary; every value comes from stored results."""

from repoagent.benchmark.metrics import BenchmarkSummary, ExperimentSummary
from repoagent.benchmark.provenance import RunManifest

NA = "n/a"


def _pct(value: float | None) -> str:
    return NA if value is None else f"{100 * value:.1f}%"


def _num(value: float | None, digits: int = 2) -> str:
    return NA if value is None else f"{value:.{digits}f}"


def _experiment(item: ExperimentSummary) -> list[str]:
    rows = [
        f"Experiment: {item.experiment} ({item.mode})",
        f"  Tasks attempted:          {item.tasks_attempted}",
    ]
    if item.mode != "retrieval":
        rows.append(
            f"  Successes:                {item.successes} ({_pct(item.success_rate)})"
        )
    if item.mode == "repair":
        rows += [
            f"  Validated repairs:        {item.validated_repairs}",
            f"  Hidden tests resolved:    {item.hidden_tests_resolved}",
            f"  Average repair attempts:  {_num(item.avg_attempts)}",
            f"  Lines added/removed:      {item.lines_added}/{item.lines_removed}",
        ]
    if item.localization_measured:
        rows += [
            f"  File localization:        {_pct(item.file_localization)}",
            f"  Symbol localization:      {_pct(item.symbol_localization)}",
        ]
    for strategy, values in item.retrieval.items():
        rows.append(
            f"  {strategy:<13} Recall@{item.k}: {_num(values['recall_at_k'], 3)}"
            f"  MRR: {_num(values['mrr'], 3)}"
        )
    if item.mode != "retrieval":
        rows += [
            f"  Average LLM calls:        {_num(item.avg_llm_calls)}",
            f"  Average retrieval calls:  {_num(item.avg_retrieval_calls)}",
            f"  Average tokens in/out:    {_num(item.avg_input_tokens, 0)}"
            f"/{_num(item.avg_output_tokens, 0)}",
        ]
    rows.append(f"  Average runtime (s):      {_num(item.avg_duration_seconds)}")
    rows += [f"  Failure {name}: {count}" for name, count in item.failures.items()]
    return rows


def render_benchmark(manifest: RunManifest, summary: BenchmarkSummary) -> str:
    lines = [
        "RepoAgent Evaluation",
        f"Run: {manifest.run_id}  Suite: {manifest.suite}",
        f"RepoAgent {manifest.repoagent_version} @ {manifest.repoagent_commit or NA}"
        f"  Model: {manifest.llm_provider}/{manifest.llm_model or NA}",
        "",
    ]
    for item in summary.experiments:
        lines += [*_experiment(item), ""]
    return "\n".join(lines).rstrip()
