"""Deterministically parsed validation results and baseline comparison (M7)."""

from enum import StrEnum

from pydantic import Field

from repoagent.analysis.models import AnalysisModel
from repoagent.domain.sandbox import SandboxExecution


class ValidationPhase(StrEnum):
    BASELINE = "baseline"
    PATCHED = "patched"


class TestFailure(AnalysisModel):
    """A failing or erroring test identifier with a short message."""

    __test__ = False
    test_id: str = Field(max_length=500)
    message: str = Field(default="", max_length=300)
    kind: str = "failed"


class TestSummary(AnalysisModel):
    """Counts parsed from pytest; ``parsed`` is False when unavailable."""

    __test__ = False
    exit_code: int | None = None
    parsed: bool = False
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    failures: list[TestFailure] = Field(default_factory=list, max_length=50)

    @property
    def failing_ids(self) -> set[str]:
        return {failure.test_id for failure in self.failures}


class LintViolation(AnalysisModel):
    path: str = Field(max_length=500)
    line: int = 0
    code: str = Field(max_length=20)
    message: str = Field(max_length=300)

    @property
    def signature(self) -> str:
        """Line-independent identity so shifted code is not a new violation."""
        return f"{self.path}|{self.code}|{self.message}"


class LintSummary(AnalysisModel):
    exit_code: int | None = None
    parsed: bool = False
    violations: list[LintViolation] = Field(default_factory=list, max_length=100)
    total: int = 0


class ValidationComparison(AnalysisModel):
    """Differences between the baseline and the patched workspace."""

    new_failures: list[str] = Field(default_factory=list)
    fixed_failures: list[str] = Field(default_factory=list)
    persisting_failures: list[str] = Field(default_factory=list)
    new_lint: list[str] = Field(default_factory=list)

    @property
    def regression(self) -> bool:
        return bool(self.new_failures or self.new_lint)


class ValidationResult(AnalysisModel):
    """Everything known about one baseline or patched validation run."""

    phase: ValidationPhase
    execution: SandboxExecution
    tests: TestSummary | None = None
    lint: LintSummary | None = None
    passed: bool = False
    summary: str = Field(default="", max_length=1000)
    comparison: ValidationComparison | None = None
    signature: str = ""
