"""Aggregate measured task results; unavailable values stay ``None``."""

from collections import Counter

from pydantic import Field

from repoagent.analysis.models import AnalysisModel
from repoagent.benchmark.results import FailureCategory, TaskResult


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 4) if values else None


class ExperimentSummary(AnalysisModel):
    experiment: str
    mode: str
    tasks_attempted: int
    successes: int
    success_rate: float | None
    validated_repairs: int
    hidden_tests_resolved: int
    localization_measured: int
    file_localization: float | None
    symbol_localization: float | None
    k: int
    retrieval: dict[str, dict[str, float | None]] = Field(default_factory=dict)
    avg_attempts: float | None
    avg_retrieval_calls: float | None
    avg_llm_calls: float | None
    avg_input_tokens: float | None
    avg_output_tokens: float | None
    avg_prompt_chars: float | None
    avg_duration_seconds: float | None
    files_changed: int
    lines_added: int
    lines_removed: int
    timeouts: int
    sandbox_failures: int
    patch_failures: int
    failures: dict[str, int] = Field(default_factory=dict)


class BenchmarkSummary(AnalysisModel):
    run_id: str
    suite: str
    experiments: list[ExperimentSummary]


def summarize_experiment(name: str, results: list[TaskResult]) -> ExperimentSummary:
    mode = results[0].mode if results else ""
    located = [r for r in results if r.localization.measured]
    repair = [r for r in results if r.mode == "repair"]
    llm = [r for r in results if r.mode != "retrieval"]
    strategies = sorted({s for r in results for s in r.retrieval})
    failures = Counter(r.failure_category.value for r in results if r.failure_category)
    return ExperimentSummary(
        experiment=name,
        mode=mode,
        tasks_attempted=len(results),
        successes=sum(r.success for r in results),
        success_rate=None
        if mode == "retrieval"
        else _mean([float(r.success) for r in results]),
        validated_repairs=sum(r.status == "validated" for r in repair),
        hidden_tests_resolved=sum(r.hidden_tests_passed is True for r in repair),
        localization_measured=len(located),
        file_localization=_mean([float(r.localization.file_hit) for r in located]),
        symbol_localization=_mean([float(r.localization.symbol_hit) for r in located]),
        k=results[0].k if results else 0,
        retrieval={
            s: {
                metric: _mean(
                    [
                        getattr(r.retrieval[s], metric)
                        for r in results
                        if s in r.retrieval
                    ]
                )
                for metric in ("recall_at_k", "mrr", "hit_at_k")
            }
            for s in strategies
        },
        avg_attempts=_mean([r.attempts for r in repair]),
        avg_retrieval_calls=_mean([r.retrieval_calls for r in llm]),
        avg_llm_calls=_mean([r.tokens.llm_calls for r in llm]),
        avg_input_tokens=_mean([r.tokens.input_tokens for r in llm]),
        avg_output_tokens=_mean([r.tokens.output_tokens for r in llm]),
        avg_prompt_chars=_mean([r.tokens.prompt_chars for r in repair]),
        avg_duration_seconds=_mean([r.duration_seconds for r in results]),
        files_changed=sum(r.patch.files_changed for r in repair),
        lines_added=sum(r.patch.lines_added for r in repair),
        lines_removed=sum(r.patch.lines_removed for r in repair),
        timeouts=failures.get(FailureCategory.TIMEOUT, 0),
        sandbox_failures=failures.get(FailureCategory.SANDBOX_FAILURE, 0),
        patch_failures=failures.get(FailureCategory.PATCH_APPLY_FAILURE, 0)
        + failures.get(FailureCategory.PATCH_GENERATION_FAILURE, 0),
        failures=dict(sorted(failures.items())),
    )


def summarize(run_id: str, suite: str, results: list[TaskResult]) -> BenchmarkSummary:
    names = list(dict.fromkeys(r.experiment for r in results))
    return BenchmarkSummary(
        run_id=run_id,
        suite=suite,
        experiments=[
            summarize_experiment(n, [r for r in results if r.experiment == n])
            for n in names
        ],
    )
