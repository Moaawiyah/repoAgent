"""Static detection of validation commands and dependencies (never executes).

Configuration is read with ``tomllib``/``configparser`` only. Unsupported
dependency lines (URLs, paths, options, markers) are skipped and recorded.
"""

import tomllib
from pathlib import Path

from repoagent.domain.errors import UnsafeCommandError
from repoagent.domain.sandbox import (
    CommandKind,
    CommandSpec,
    DependencyStrategy,
    SandboxLimits,
    ValidationPlan,
)
from repoagent.validation.policy import (
    TOOL_REQUIREMENTS,
    normalize_requirement,
    requirement_name,
)
from repoagent.validation.setup_cfg import (
    declares_pytest,
    install_requires_lines,
    read_ini,
)

MAX_CONFIG_BYTES = 1_000_000
REQUIREMENT_FILES = (
    "requirements.txt",
    "requirements-dev.txt",
    "requirements-test.txt",
)


def _read(path: Path) -> str:
    if (
        path.is_symlink()
        or not path.is_file()
        or path.stat().st_size > MAX_CONFIG_BYTES
    ):
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


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
        project_specs, skipped = [], []
        if strategy == DependencyStrategy.PROJECT:
            project_specs, skipped = self._normalize(
                self._project_lines(root, pyproject)
            )
        # A project's own pin for a tool we also need (pytest, ruff) wins over
        # our default: forcing an unrelated version range alongside it is a
        # frequent, avoidable cause of "pip install" ResolutionImpossible.
        project_names = {requirement_name(spec) for spec in project_specs}
        tool_specs, _ = self._normalize(
            TOOL_REQUIREMENTS[c.kind]
            for c in commands
            if requirement_name(TOOL_REQUIREMENTS[c.kind]) not in project_names
        )
        accepted = []
        for spec in [*tool_specs, *project_specs]:
            if spec not in accepted:
                accepted.append(spec)
        return accepted, skipped

    @staticmethod
    def _normalize(lines) -> tuple[list[str], list[str]]:
        accepted, skipped = [], []
        for line in lines:
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            try:
                spec = normalize_requirement(line)
            except UnsafeCommandError:
                skipped.append(line.strip()[:120])
                continue
            if spec not in accepted:
                accepted.append(spec)
        return accepted, skipped

    @staticmethod
    def _project_lines(root: Path, pyproject: dict) -> list[str]:
        project = pyproject.get("project", {}) if isinstance(pyproject, dict) else {}
        lines = list(project.get("dependencies", []))
        optional = project.get("optional-dependencies", {})
        groups = pyproject.get("dependency-groups", {})
        for name in ("test", "tests", "dev"):
            lines.extend(optional.get(name, []))
            lines.extend(item for item in groups.get(name, []) if isinstance(item, str))
        for name in REQUIREMENT_FILES:
            lines.extend(_read(root / name).splitlines())
        lines.extend(install_requires_lines(read_ini(_read(root / "setup.cfg"))))
        return [line for line in lines if isinstance(line, str)]
