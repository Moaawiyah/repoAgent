"""Trusted command catalog and allowlist; no model output reaches argv.

Every argv is a constant built by RepoAgent. The only variable input is a
dependency specification, which must match a strict name/extras/version
grammar so options, URLs, paths, and shell metacharacters are rejected.
"""

import re

from repoagent.domain.errors import UnsafeCommandError
from repoagent.domain.sandbox import CommandKind, CommandSpec

DEPS_MOUNT, WORKSPACE_MOUNT = "/deps", "/workspace"
TOOL_REQUIREMENTS = {
    CommandKind.PYTEST: "pytest>=8,<9",
    CommandKind.RUFF_CHECK: "ruff>=0.9,<1",
}
MAX_REQUIREMENTS = 60
_REQUIREMENT = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}"
    r"(\[[A-Za-z0-9._-]+(,[A-Za-z0-9._-]+)*\])?"
    r"((===|==|!=|~=|>=|<=|>|<)[A-Za-z0-9.*+!_-]{1,40}"
    r"(,(===|==|!=|~=|>=|<=|>|<)[A-Za-z0-9.*+!_-]{1,40})*)?$"
)
_CATALOG: dict[CommandKind, tuple[str, ...]] = {
    CommandKind.PYTEST: (
        "python",
        "-m",
        "pytest",
        "-q",
        "-rfE",
        "--tb=short",
        "--color=no",
        "-p",
        "no:cacheprovider",
        "-o",
        "addopts=",
    ),
    CommandKind.RUFF_CHECK: (
        "python",
        "-m",
        "ruff",
        "check",
        "--no-cache",
        "--output-format=concise",
        ".",
    ),
}


def normalize_requirement(raw: str) -> str:
    """Return a safe specifier or raise; environment markers are unsupported."""
    text = raw.split("#", 1)[0].strip().replace(" ", "")
    if not _REQUIREMENT.fullmatch(text):
        raise UnsafeCommandError(f"Unsupported dependency specification: {raw[:80]}")
    return text


class CommandPolicy:
    """Maps allowlisted command kinds to constant argv vectors."""

    def __init__(self, allowed: frozenset[CommandKind]) -> None:
        self._allowed = allowed

    def argv(self, spec: CommandSpec) -> list[str]:
        """Return the trusted argv for an allowed validation command."""
        if spec.kind not in self._allowed or spec.kind not in _CATALOG:
            raise UnsafeCommandError(f"Command is not allowlisted: {spec.kind}")
        return list(_CATALOG[spec.kind])

    @staticmethod
    def install_argv(requirements: list[str]) -> list[str]:
        """Wheel-only install into the dependency mount; never builds sdists."""
        if not requirements or len(requirements) > MAX_REQUIREMENTS:
            raise UnsafeCommandError("Dependency list is empty or too large")
        specs = [normalize_requirement(item) for item in requirements]
        return [
            "python",
            "-m",
            "pip",
            "install",
            "--no-input",
            "--disable-pip-version-check",
            "--no-compile",
            "--only-binary=:all:",
            "--target",
            DEPS_MOUNT,
            "--",
            *specs,
        ]
