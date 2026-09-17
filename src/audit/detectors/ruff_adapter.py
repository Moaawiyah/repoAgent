"""Optional adapter ingesting Ruff findings through the existing sandbox.

Never runs on the default static audit path: only active when a
`SandboxRunner` is explicitly injected (mirrors the M7 opt-in), and only
when the target repository already configures Ruff itself (`ProjectDetector`
— no rule reimplementation). Installs only Ruff (`DependencyStrategy.TOOLS`),
never the target's own dependencies.
"""

from repoagent.audit.context import AuditContext
from repoagent.domain.audit import (
    CandidateIssue,
    DetectionSource,
    IssueCategory,
    Severity,
    stable_candidate_id,
)
from repoagent.domain.errors import SandboxError
from repoagent.domain.sandbox import (
    CommandKind,
    CommandSpec,
    DependencyStrategy,
    SandboxLimits,
)
from repoagent.domain.validation import LintViolation
from repoagent.ports.sandbox import SandboxRunner
from repoagent.validation.detection import ProjectDetector
from repoagent.validation.parsers import parse_ruff

_HIGH_PREFIXES = ("F",)


class RuffDetector:
    """Runs the target's own configured Ruff check inside the sandbox."""

    name = "ruff"

    def __init__(
        self, sandbox_runner: SandboxRunner | None, limits: SandboxLimits | None = None
    ) -> None:
        self._runner = sandbox_runner
        self._limits = limits or SandboxLimits(dependencies=DependencyStrategy.TOOLS)

    def detect(self, context: AuditContext) -> list[CandidateIssue]:
        if self._runner is None:
            return []
        plan = ProjectDetector(self._limits).detect(context.root)
        if not plan.has(CommandKind.RUFF_CHECK):
            return []
        try:
            with self._runner.session(context.root, plan, self._limits) as session:
                execution = session.run(
                    [CommandSpec(kind=CommandKind.RUFF_CHECK)], None
                )
        except SandboxError:
            return []
        result = execution.result(CommandKind.RUFF_CHECK)
        if result is None:
            return []
        summary = parse_ruff(result)
        return [self._candidate(violation) for violation in summary.violations]

    @staticmethod
    def _candidate(violation: LintViolation) -> CandidateIssue:
        severity = (
            Severity.HIGH
            if violation.code.startswith(_HIGH_PREFIXES)
            else Severity.MEDIUM
        )
        return CandidateIssue(
            id=stable_candidate_id(
                IssueCategory.LINT, violation.path, violation.line, violation.code
            ),
            category=IssueCategory.LINT,
            title=f"Ruff {violation.code}",
            description=violation.message,
            confidence=0.95,
            severity=severity,
            file=violation.path,
            symbol=None,
            start_line=max(violation.line, 1),
            end_line=max(violation.line, 1),
            detection_source=DetectionSource.RUFF,
        )
