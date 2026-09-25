"""Static detection of validation commands and dependencies (never executes).

Configuration is read with ``tomllib``/``configparser`` only. Unsupported
dependency lines (URLs, paths, options, markers) are skipped and recorded.
"""

import tomllib
from pathlib import Path

from repoagent.domain.sandbox import (
    CommandKind,
    CommandSpec,
    DependencyStrategy,
    SandboxLimits,
    ValidationPlan,
)
from repoagent.validation.policy import TOOL_REQUIREMENTS, requirement_name
from repoagent.validation.requirements import (
    import_roots,
    normalize_lines,
    project_lines,
)
from repoagent.validation.requirements import (
    read_config as _read,
)
from repoagent.validation.setup_cfg import declares_pytest, read_ini


class ProjectDetector:
    """Builds a ``ValidationPlan`` from repository configuration files."""

    def __init__(self, limits: SandboxLimits) -> None:
        self._limits = limits

    def detect(self, repository: Path) -> ValidationPlan:
        root = repository.resolve()
        try:
            pyproject = tomllib.loads(_read(root / "pyproject.toml"))
        except tomllib.TOMLDecodeError:
            pyproject = {}
        tool = pyproject.get("tool", {}) if isinstance(pyproject, dict) else {}
        commands, notes = [], []
        if self._uses_pytest(root, tool):
            commands.append(CommandSpec(kind=CommandKind.PYTEST))
        else:
            notes.append("No pytest tests or configuration detected")
        if "ruff" in tool or any(
            (root / n).is_file() for n in ("ruff.toml", ".ruff.toml")
        ):
            commands.append(CommandSpec(kind=CommandKind.RUFF_CHECK))
        allowed = [c for c in commands if c.kind in self._limits.allowed_commands]
        notes.extend(
            f"Command disabled by policy: {c.kind}"
            for c in commands
            if c not in allowed
        )
        requirements, skipped = self._requirements(root, pyproject, allowed)
        return ValidationPlan(
            commands=allowed,
            requirements=requirements,
            skipped_requirements=skipped,
            notes=notes,
            python_paths=import_roots(root),
        )

    @staticmethod
    def _uses_pytest(root: Path, tool: dict) -> bool:
        if "pytest" in tool or (root / "pytest.ini").is_file():
            return True
        if any(
            declares_pytest(read_ini(_read(root / n))) for n in ("setup.cfg", "tox.ini")
        ):
            return True
        tests = [root / "tests", root / "test"]
        if any(d.is_dir() and not d.is_symlink() for d in tests):
            return True
        return any(root.glob("test_*.py")) or (root / "conftest.py").is_file()

    def _requirements(
        self, root: Path, pyproject: dict, commands: list[CommandSpec]
    ) -> tuple[list[str], list[str]]:
        strategy = self._limits.dependencies
        if strategy == DependencyStrategy.NONE:
            return [], []
        project_specs: list[str] = []
        skipped: list[str] = []
        if strategy == DependencyStrategy.PROJECT:
            project_specs, skipped = normalize_lines(
                project_lines(root, pyproject, self._limits.pinned_requirements)
            )
        # A project's own pin for a tool we also need (pytest, ruff) wins over
        # our default: forcing an unrelated version range alongside it is a
        # frequent, avoidable cause of "pip install" ResolutionImpossible.
        project_names = {requirement_name(spec) for spec in project_specs}
        tool_specs, _ = normalize_lines(
            TOOL_REQUIREMENTS[c.kind]
            for c in commands
            if requirement_name(TOOL_REQUIREMENTS[c.kind]) not in project_names
        )
        accepted = []
        for spec in [*tool_specs, *project_specs]:
            if spec not in accepted:
                accepted.append(spec)
        return accepted, skipped
