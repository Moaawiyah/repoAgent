"""Check physical file length and strict, fresh statement coverage."""

import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check(root: Path) -> list[str]:
    failures = []
    files = sorted(
        path
        for folder in ("src", "tests", "scripts")
        for path in (root / folder).rglob("*.py")
    )
    lengths = {path: len(path.read_bytes().splitlines()) for path in files}
    for path, length in lengths.items():
        if length > 150:
            failures.append(f"{path.relative_to(root)}: {length} lines exceeds 150")
    print(f"Maximum Python file length: {max(lengths.values(), default=0)} lines")
    try:
        report = json.loads((root / "coverage.json").read_text())
        timestamp = datetime.fromisoformat(report["meta"]["timestamp"]).timestamp()
        if any(path.stat().st_mtime > timestamp for path in files):
            failures.append("Coverage is stale; rerun pytest after source/test edits")
        measured = set(report["files"])
        expected = {
            path.relative_to(root).as_posix()
            for path in files
            if path.relative_to(root).parts[0] in {"src", "scripts"}
        }
        if expected - measured:
            failures.append("Coverage is missing production files")
        totals = report["totals"]
        covered, total = totals["covered_lines"], totals["num_statements"]
        if (
            type(covered) is not int
            or type(total) is not int
            or not 0 <= covered <= total
            or total == 0
        ):
            failures.append("Coverage requires valid, nonempty statement counts")
        else:
            print(
                f"Statement coverage: {covered}/{total} = {100 * covered / total:.4f}%"
            )
            if 100 * covered <= 85 * total:
                failures.append("Statement coverage must be strictly above 85%")
    except (OSError, ValueError, KeyError, TypeError):
        failures.append("Coverage report is missing or invalid; run pytest first")
    return failures


def main() -> int:
    failures = check(ROOT)
    for failure in failures:
        print(f"FAIL: {failure}")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
