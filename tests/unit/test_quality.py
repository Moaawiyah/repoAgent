"""Quality gates reject equality, stale/incomplete data, and oversized files."""

import json
import runpy
from datetime import datetime, timedelta
from pathlib import Path

import pytest

check = runpy.run_path(
    str(Path(__file__).resolve().parents[2] / "scripts/check_quality.py")
)["check"]


def report(root, covered=86, total=100, files=None, timestamp=None):
    root.joinpath("coverage.json").write_text(
        json.dumps(
            {
                "meta": {
                    "timestamp": timestamp
                    or (datetime.now() + timedelta(seconds=1)).isoformat()
                },
                "files": files or {},
                "totals": {"covered_lines": covered, "num_statements": total},
            }
        )
    )


@pytest.mark.parametrize("covered,passes", [(84, False), (85, False), (86, True)])
def test_strict_boundary(tmp_path, covered, passes):
    report(tmp_path, covered)
    assert (not check(tmp_path)) == passes


def test_empty_and_invalid_coverage(tmp_path):
    assert check(tmp_path)
    report(tmp_path, 0, 0)
    assert any("nonempty" in failure for failure in check(tmp_path))
    tmp_path.joinpath("coverage.json").write_text("invalid")
    assert check(tmp_path)


def test_physical_lines_include_final_unterminated_line(tmp_path):
    source = tmp_path / "src" / "module.py"
    source.parent.mkdir()
    source.write_text("# comment\n" * 150 + "x = 1")
    report(tmp_path, files={"src/module.py": {}})
    assert any("151 lines" in failure for failure in check(tmp_path))
    source.write_text("# comment\n" * 149 + "x = 1")
    report(tmp_path, files={"src/module.py": {}})
    assert not check(tmp_path)


def test_missing_source_and_stale_report(tmp_path):
    source = tmp_path / "src" / "module.py"
    source.parent.mkdir()
    source.write_text("x = 1\n")
    report(tmp_path, timestamp="2000-01-01T00:00:00")
    failures = check(tmp_path)
    assert any("stale" in failure for failure in failures)
    assert any("missing production" in failure for failure in failures)
