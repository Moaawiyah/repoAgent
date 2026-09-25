"""Dependency lines and import roots read statically from project files."""

from pathlib import Path

from repoagent.domain.errors import UnsafeCommandError
from repoagent.validation.policy import normalize_requirement
from repoagent.validation.setup_cfg import install_requires_lines, read_ini

MAX_CONFIG_BYTES = 1_000_000
REQUIREMENT_FILES = (
    "requirements.txt",
    "requirements-dev.txt",
    "requirements-test.txt",
)


def read_config(path: Path) -> str:
    if (
        path.is_symlink()
        or not path.is_file()
        or path.stat().st_size > MAX_CONFIG_BYTES
    ):
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def normalize_lines(lines) -> tuple[list[str], list[str]]:
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


def project_lines(
    root: Path, pyproject: dict, pinned: tuple[str, ...] = ()
) -> list[str]:
    """Declared dependencies, or the caller's pinned set when one is given.

    A pinned set (e.g. a benchmark task's frozen environment) replaces the
    project's own ranges so repeated runs install identical versions.
    """
    if pinned:
        return list(pinned)
    project = pyproject.get("project", {}) if isinstance(pyproject, dict) else {}
    lines = list(project.get("dependencies", []))
    optional = project.get("optional-dependencies", {})
    groups = pyproject.get("dependency-groups", {})
    for name in ("test", "tests", "dev"):
        lines.extend(optional.get(name, []))
        lines.extend(item for item in groups.get(name, []) if isinstance(item, str))
    for name in REQUIREMENT_FILES:
        lines.extend(read_config(root / name).splitlines())
    lines.extend(install_requires_lines(read_ini(read_config(root / "setup.cfg"))))
    return [line for line in lines if isinstance(line, str)]


def import_roots(root: Path) -> list[str]:
    """``["src"]`` for a src-layout project, so tests can import it uninstalled."""
    src = root / "src"
    if not src.is_dir() or src.is_symlink():
        return []
    packages = (child for child in src.iterdir() if (child / "__init__.py").is_file())
    return ["src"] if any(packages) else []
