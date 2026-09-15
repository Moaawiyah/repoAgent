"""BugsInPy and SWE-bench importers producing RepoAgent benchmark suites.

Adapters only translate dataset metadata; they add no agent behavior.
Gold patches and tests remain evaluator-only fields.
"""

import json
import re
from pathlib import Path

from repoagent.benchmark.gold import expected_files
from repoagent.benchmark.loaders import BenchmarkError
from repoagent.benchmark.models import (
    BenchmarkSuite,
    BenchmarkTask,
    RepositoryRef,
    ValidationCriteria,
)

MAX_ISSUE = 6000
_INFO = re.compile(r'^\s*([A-Za-z_]+)\s*=\s*"?(.*?)"?\s*$')
_TEST = re.compile(
    r"((?:tests?|testing)[\w/.-]*\.py(?:::[\w\[\]-]+)*|(?:tests?)(?:\.\w+){2,})"
)


def _info(path: Path) -> dict[str, str]:
    pairs = (_INFO.match(line) for line in path.read_text().splitlines())
    return {m.group(1): m.group(2) for m in pairs if m}


def _issue(text: str) -> str:
    return text if len(text) <= MAX_ISSUE else text[: MAX_ISSUE - 20] + "\n[truncated]"


def import_bugsinpy(root: Path, bugs: list[str]) -> BenchmarkSuite:
    """``bugs`` entries look like ``PySnooper:1``; BugsInPy has no issue text."""
    tasks = []
    for selection in bugs:
        project, _, number = selection.partition(":")
        base = root / "projects" / project
        bug = base / "bugs" / number
        if not number.isdigit() or not bug.is_dir():
            raise BenchmarkError(f"Unknown BugsInPy bug: {selection}")
        url = _info(base / "project.info")["github_url"].rstrip("/")
        patch = (bug / "bug_patch.txt").read_text()
        tests = _TEST.findall((bug / "run_test.sh").read_text())
        names = ", ".join(dict.fromkeys(tests)) or _info(bug / "bug.info")["test_file"]
        tasks.append(
            BenchmarkTask(
                task_id=f"{project}-{number}",
                benchmark="bugsinpy",
                repository=RepositoryRef(
                    source=url, commit=_info(bug / "bug.info")["buggy_commit_id"]
                ),
                issue=_issue(
                    f"In {project}, these tests fail on the current revision: "
                    f"{names}. Find and fix the defect in the library code."
                ),
                issue_source="synthesized_from_failing_tests",
                expected_files=expected_files(patch),
                gold_patch=patch,
                validation=ValidationCriteria(fail_to_pass=list(dict.fromkeys(tests))),
            )
        )
    return BenchmarkSuite(
        name="bugsinpy", source="soarsmu/BugsInPy (local checkout)", tasks=tasks
    )


def _tests(value: object) -> list[str]:
    return list(json.loads(value) if isinstance(value, str) else value or [])


def import_swebench(
    records: list[dict], instance_ids: list[str], name: str, source: str
) -> BenchmarkSuite:
    by_id = {record["instance_id"]: record for record in records}
    missing = [item for item in instance_ids if item not in by_id]
    if missing:
        raise BenchmarkError(f"Unknown SWE-bench instance(s): {', '.join(missing)}")
    tasks = [
        BenchmarkTask(
            task_id=record["instance_id"],
            benchmark=name,
            repository=RepositoryRef(
                source=f"https://github.com/{record['repo']}",
                commit=record["base_commit"],
            ),
            issue=_issue(record["problem_statement"]),
            expected_files=expected_files(record["patch"]),
            gold_patch=record["patch"],
            validation=ValidationCriteria(
                fail_to_pass=_tests(record.get("FAIL_TO_PASS")),
                pass_to_pass=_tests(record.get("PASS_TO_PASS")),
            ),
        )
        for record in (by_id[item] for item in instance_ids or list(by_id))
    ]
    return BenchmarkSuite(name=name, source=source, tasks=tasks)
