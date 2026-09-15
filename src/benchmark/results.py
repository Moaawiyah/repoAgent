"""Structured, reproducible per-task benchmark results (one JSONL line each)."""

from enum import StrEnum

from pydantic import Field

from repoagent.analysis.models import AnalysisModel


class FailureCategory(StrEnum):
    SETUP_FAILURE = "setup_failure"
    PROVIDER_ERROR = "provider_error"
    LOCALIZATION_FAILURE = "localization_failure"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    INCORRECT_ROOT_CAUSE = "incorrect_root_cause"
    PATCH_GENERATION_FAILURE = "patch_generation_failure"
    REVIEW_REJECTION = "review_rejection"
    PATCH_APPLY_FAILURE = "patch_apply_failure"
    TEST_FAILURE = "test_failure"
    REGRESSION = "regression"
    TIMEOUT = "timeout"
    SANDBOX_FAILURE = "sandbox_failure"
    MAX_ATTEMPTS = "max_attempts"
    VALIDATION_UNAVAILABLE = "validation_unavailable"


class Localization(AnalysisModel):
    """Whether the agent's primary conclusion or patch hit labeled locations."""

    measured: bool = False
    file_hit: bool = False
    symbol_hit: bool = False
    file_recall: float = 0.0
    symbol_recall: float = 0.0
    predicted_files: list[str] = Field(default_factory=list)
    predicted_symbols: list[str] = Field(default_factory=list)


class RetrievalScore(AnalysisModel):
    recall_at_k: float
    mrr: float
    hit_at_k: float


class PatchMetrics(AnalysisModel):
    files_changed: int = 0
    lines_added: int = 0
    lines_removed: int = 0
    touches_expected_file: bool = False


class TokenUsage(AnalysisModel):
    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    prompt_chars: int = 0


class TaskResult(AnalysisModel):
    run_id: str
    task_id: str
    benchmark: str
    experiment: str
    mode: str
    status: str
    success: bool = False
    failure_category: FailureCategory | None = None
    failure_reason: str | None = Field(default=None, max_length=1000)
    localization: Localization = Localization()
    retrieval: dict[str, RetrievalScore] = Field(default_factory=dict)
    k: int = 5
    attempts: int = 0
    retrieval_calls: int = 0
    patch: PatchMetrics = PatchMetrics()
    tests_before: dict[str, int] | None = None
    tests_after: dict[str, int] | None = None
    hidden_tests_passed: bool | None = None
    tokens: TokenUsage = TokenUsage()
    duration_seconds: float = 0.0
    sandbox_seconds: float = 0.0
    repository_commit: str | None = None
