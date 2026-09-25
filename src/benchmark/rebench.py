"""SWE-rebench importer: real issues, pinned environments, hidden test overlays.

Rows (``nebius/SWE-rebench`` exports) carry the issue text, gold patch,
test patch, FAIL_TO_PASS/PASS_TO_PASS, the Python version, and a frozen
``requirements`` list. Hidden tests are the test files *after* applying the
test patch to the pinned checkout (git is used on data only, never to run
target code); they never enter agent context.
"""

import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path

from repoagent.analysis.analyzer import RepositoryAnalyzer
from repoagent.benchmark.adapters import _issue, _tests
from repoagent.benchmark.gold import changed_ranges, expected_files, expected_symbols
from repoagent.benchmark.loaders import BenchmarkError
from repoagent.benchmark.materialize import RepositoryMaterializer
from repoagent.benchmark.models import (
    BenchmarkSuite,
    BenchmarkTask,
    ExpectedOutcome,
    RepositoryRef,
    TaskEnvironment,
    ValidationCriteria,
)
from repoagent.domain.errors import RepoAgentError
from repoagent.domain.repository import RepositorySpec
from repoagent.sandbox.git import HARDENING
from repoagent.sandbox.process import ProcessRunner, SubprocessRunner

ImageFor = Callable[[str], str | None]


def frozen_requirements(freeze: str, extra: list[str] | None = None) -> list[str]:
    """``name==version`` pins from a pip freeze.

    Conda-built lines (``name @ file:///...``) carry no version, so only
    the name is kept (unpinned); editable and URL lines are dropped.
    ``extra`` adds install-time packages (e.g. ``pytest``) when missing.
    """
    pins: list[str] = []
    for line in freeze.splitlines():
        line = line.strip()
        if not line or line.startswith(("-", "#")):
            continue
        if " @ " in line:
            name, _, target = line.partition(" @ ")
            if target.startswith("file://"):
                pins.append(name.strip())
        elif "==" in line:
            pins.append(line)
    names = {pin.split("==")[0].lower() for pin in pins}
    pins += [item for item in extra or [] if item.lower() not in names]
    return pins


def hidden_tests(
    checkout: Path, test_patch: str, process: ProcessRunner | None = None
) -> dict[str, str]:
    """Contents of every file the test patch creates or changes."""
    paths = [path for path in changed_ranges(test_patch) if path != "/dev/null"]
    if not paths or any(not path.endswith(".py") for path in paths):
        raise BenchmarkError("Hidden tests must be Python files only")
    runner = process or SubprocessRunner()
    with tempfile.TemporaryDirectory(prefix="repoagent-hidden-") as temporary:
        copy = Path(temporary) / "repo"
        shutil.copytree(checkout, copy, symlinks=True)
        (Path(temporary) / "tests.diff").write_text(test_patch, encoding="utf-8")
        argv = ["git", *HARDENING, "-C", str(copy), "apply", "../tests.diff"]
        result = runner.run(argv, 60, 8000)
        if result.timed_out or result.exit_code != 0:
            raise BenchmarkError("Test patch does not apply to the pinned commit")
        return {path: (copy / path).read_text(encoding="utf-8") for path in paths}


def rebench_task(
    record: dict, materializer: RepositoryMaterializer, image_for: ImageFor
) -> BenchmarkTask:
    ref = RepositoryRef(
        source=f"https://github.com/{record['repo']}", commit=record["base_commit"]
    )
    checkout = materializer.materialize(ref)
    analysis = RepositoryAnalyzer().analyze(RepositorySpec(source=str(checkout)))
    install = record.get("install_config") or {}
    python = install.get("python")
    return BenchmarkTask(
        task_id=record["instance_id"],
        benchmark="swe-rebench",
        repository=ref,
        issue=_issue(record["problem_statement"]),
        expected_files=expected_files(record["patch"]),
        expected_symbols=expected_symbols(record["patch"], analysis),
        gold_patch=record["patch"],
        validation=ValidationCriteria(
            fail_to_pass=_tests(record.get("FAIL_TO_PASS")),
            pass_to_pass=_tests(record.get("PASS_TO_PASS"))[:2000],
            hidden_tests=hidden_tests(checkout, record["test_patch"]),
        ),
        expected_outcome=ExpectedOutcome.VALIDATED_REPAIR,
        environment=TaskEnvironment(
            image=image_for(python) if python else None,
            python=python,
            requirements=frozen_requirements(
                record.get("requirements") or "", install.get("pip_packages")
            ),
        ),
    )


def import_swerebench(
    records: list[dict],
    instance_ids: list[str],
    materializer: RepositoryMaterializer,
    image_for: ImageFor,
) -> tuple[BenchmarkSuite, dict[str, str]]:
    """Return the suite plus every skipped instance with its reason."""
    by_id = {record["instance_id"]: record for record in records}
    missing = [item for item in instance_ids if item not in by_id]
    if missing:
        raise BenchmarkError(f"Unknown SWE-rebench instance(s): {', '.join(missing)}")
    tasks, skipped = [], {}
    for item in instance_ids:
        try:
            tasks.append(rebench_task(by_id[item], materializer, image_for))
        except (RepoAgentError, OSError, UnicodeError, ValueError) as error:
            skipped[item] = f"{type(error).__name__}: {str(error)[:200]}"
    if not tasks:
        raise BenchmarkError("No SWE-rebench instance could be imported")
    suite = BenchmarkSuite(
        name="swe-rebench-repair",
        description="Real single-file bugs from unfamiliar repositories",
        source="nebius/SWE-rebench (filtered split)",
        tasks=tasks,
    )
    return suite, skipped
